"""
USB Serial reader for Arduino communication.
Reads JSON lines from serial port and feeds into the same pipeline as HTTP POST.
"""

import json
import logging
import threading
from queue import Queue

from .models import ArduinoReadingsPayload

logger = logging.getLogger(__name__)

# Arduino Uno VID/PID: official (2341:0043), CH340 clones (1A86:7523, 1A86:5523)
ARDUINO_UNO_IDS = [
    (0x2341, 0x0043),  # Arduino Uno (official)
    (0x2341, 0x0001),  # Arduino Uno (older)
    (0x1A86, 0x7523),  # CH340
    (0x1A86, 0x5523),  # CH340 variant
    (0x10C4, 0xEA60),  # CP2102
]


def find_arduino_uno_port() -> str | None:
    """Scan COM ports for Arduino Uno. Returns port name or None if not found."""
    try:
        import serial.tools.list_ports as list_ports
    except ImportError:
        logger.warning("pyserial not installed, cannot scan for Arduino")
        return None

    for port in list_ports.comports():
        if port.vid is not None and port.pid is not None:
            if (port.vid, port.pid) in ARDUINO_UNO_IDS:
                logger.info("Found Arduino Uno on %s (VID:PID %04X:%04X)", port.device, port.vid, port.pid)
                return port.device
        # Fallback: match "Arduino" or "CH340" in description
        if port.description and ("Arduino" in port.description or "CH340" in port.description):
            logger.info("Found Arduino-like device on %s (%s)", port.device, port.description)
            return port.device

    return None


def run_serial_reader(
    port: str,
    baud_rate: int,
    connection,
    update_queue: Queue,
    stop_event: threading.Event,
) -> None:
    """
    Run in a background thread. Reads JSON lines from serial, parses,
    feeds to connection, and puts FrontendUpdate JSON on queue for broadcast.
    Stops when stop_event is set.
    """
    try:
        import serial
    except ImportError:
        logger.error("pyserial not installed. Run: pip install pyserial")
        return

    try:
        ser = serial.Serial(port, baud_rate, timeout=0.1)
        logger.info("Serial connected on %s at %d baud", port, baud_rate)
    except Exception as e:
        logger.error("Failed to open serial port %s: %s", port, e)
        return

    buffer = ""
    while not stop_event.is_set():
        try:
            if stop_event.is_set():
                break
            chunk = ser.read(ser.in_waiting or 1)
            if not chunk:
                continue
            buffer += chunk.decode("utf-8", errors="ignore")

            while "\n" in buffer or "\r" in buffer:
                sep = "\n" if "\n" in buffer else "\r"
                line, _, buffer = buffer.partition(sep)
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue

                try:
                    data = json.loads(line)
                    payload = ArduinoReadingsPayload(**data)
                    update = connection.receive_readings(payload)
                    update_queue.put(update.model_dump_json())
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    logger.debug("Serial parse error: %s", e)
                except Exception as e:
                    logger.exception("Error processing serial payload: %s", e)

        except Exception as e:
            logger.exception("Serial read error: %s", e)
            try:
                ser.close()
            except Exception:
                pass
            break
