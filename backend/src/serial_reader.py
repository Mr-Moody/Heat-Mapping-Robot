"""
USB Serial reader for Arduino communication.
Reads JSON lines from serial port and feeds into the same pipeline as HTTP POST.
Handles disconnects, Arduino resets, and Windows ClearCommError by reconnecting.
"""

import json
import logging
import threading
from queue import Queue

from .models import ArduinoReadingsPayload

logger = logging.getLogger(__name__)

RECONNECT_DELAY = 2.0
MAX_RECONNECT_ATTEMPTS = 10

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
    Handles SerialException (disconnect, Arduino reset, Windows ClearCommError)
    by closing and reconnecting. Stops when stop_event is set.
    """
    try:
        import serial
        from serial import SerialException
    except ImportError:
        logger.error("pyserial not installed. Run: pip install pyserial")
        return

    ser = None
    buffer = ""
    msg_count = 0
    reconnect_attempt = 0

    while not stop_event.is_set():
        # Open or reopen serial
        if ser is None or not ser.is_open:
            try:
                ser = serial.Serial(port, baud_rate, timeout=0.1)
                logger.info("Serial connected on %s at %d baud", port, baud_rate)
                reconnect_attempt = 0
            except SerialException as e:
                reconnect_attempt += 1
                logger.warning("Serial open failed (attempt %d/%d): %s", reconnect_attempt, MAX_RECONNECT_ATTEMPTS, e)
                if reconnect_attempt >= MAX_RECONNECT_ATTEMPTS:
                    logger.error("Giving up after %d reconnect attempts", MAX_RECONNECT_ATTEMPTS)
                    return
                stop_event.wait(RECONNECT_DELAY)
                continue
            except Exception as e:
                logger.error("Failed to open serial port %s: %s", port, e)
                return

        try:
            if stop_event.is_set():
                break
            # in_waiting can raise SerialException on disconnect or Windows ClearCommError
            try:
                n = ser.in_waiting if ser.in_waiting else 256
            except (SerialException, OSError):
                raise SerialException("Port disconnected during in_waiting")
            chunk = ser.read(min(n, 4096))
            if not chunk:
                continue
            buffer += chunk.decode("utf-8", errors="ignore")

            while "\n" in buffer:
                line, _, buffer = buffer.partition("\n")
                line = line.strip().rstrip("\r")
                if not line or not line.startswith("{"):
                    continue

                logger.info("<- Serial received: %s", line)

                try:
                    data = json.loads(line)
                    payload = ArduinoReadingsPayload(**data)
                    update = connection.receive_readings(payload)
                    update_queue.put(update.model_dump_json())
                    cmd = connection.pop_pending_motor_cmd()
                    if cmd:
                        try:
                            ser.write(cmd.encode() + b"\n")
                        except (SerialException, OSError):
                            raise SerialException("Port disconnected during write")
                        msg_count += 1
                        if msg_count <= 5 or msg_count % 20 == 0:
                            logger.info("-> Arduino cmd #%d: %s", msg_count, cmd)
                except json.JSONDecodeError as e:
                    pos = getattr(e, "pos", None)
                    ctx = ""
                    if pos is not None and 0 <= pos < len(line):
                        start = max(0, pos - 3)
                        end = min(len(line), pos + 4)
                        ctx = repr(line[start:end])
                    logger.warning(
                        "Serial parse error: %s | len=%d | at pos %s: %s | line: %s",
                        e, len(line), pos, ctx, line[:200] + ("..." if len(line) > 200 else ""),
                    )
                except (TypeError, ValueError) as e:
                    logger.warning("Serial parse error: %s (line: %s...)", e, line[:80])
                except Exception as e:
                    logger.exception("Error processing serial payload")

        except SerialException as e:
            logger.warning("Serial error (will reconnect): %s", e)
            try:
                if ser:
                    ser.close()
            except Exception:
                pass
            ser = None
            stop_event.wait(RECONNECT_DELAY)
        except Exception as e:
            logger.exception("Unexpected serial error: %s", e)
            try:
                if ser:
                    ser.close()
            except Exception:
                pass
            ser = None
            stop_event.wait(RECONNECT_DELAY)

    try:
        if ser and ser.is_open:
            ser.close()
            logger.info("Serial port closed")
    except Exception:
        pass
