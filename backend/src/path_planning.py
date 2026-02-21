"""
ThermalScout — Path Planning Simulator
───────────────────────────────────────────────────────────────────────────────
Simulates the robot's decision-making using fake sensor data.
No hardware needed — run this while the Arduino update installs.

When the Arduino is ready, replace FakeSensorReader with a real one
that reads from your FastAPI /data endpoint. The planner logic is unchanged.

Run:
    python path_planner.py

───────────────────────────────────────────────────────────────────────────────
"""

import time
import math
import random
from dataclasses import dataclass, field
from typing import List




@dataclass
class SensorReading:
    """One snapshot of all sensor data."""
    forward_cm:   float          # Distance directly ahead (HC-SR04)
    sweep_cm:     List[float]    # 12 distances around 360°, index 0 = forward
    temperature:  float          # DHT11 air temp °C
    humidity:     float          # DHT11 humidity %
    timestamp_ms: int            # ms since robot started

    @property
    def left_cm(self):
        """Sweep index 3 ≈ 90° left."""
        return self.sweep_cm[3]

    @property
    def right_cm(self):
        """Sweep index 9 ≈ 270° = 90° right."""
        return self.sweep_cm[9]

    @property
    def rear_cm(self):
        """Sweep index 6 ≈ 180° = directly behind."""
        return self.sweep_cm[6]


@dataclass
class RobotState:
    """Tracks the robot's current position and heading in the simulation."""
    x: float = 0.0          # metres from start
    y: float = 0.0
    heading_deg: float = 0.0 # 0 = north, 90 = east
    speed: float = 0.0       # 0.0 to 1.0
    action: str = "IDLE"
    distance_travelled: float = 0.0


# ── FAKE SENSOR READER ────────────────────────────────────────────────────────

class FakeSensorReader:
    """
    Simulates a corridor environment with walls, a hot spot, and a doorway.
    Replace this class with a real reader that hits your FastAPI /data endpoint.

    Corridor layout (top-down):
        Left wall  ~30cm away
        Right wall ~30cm away
        Obstacle   placed at x=2.0m (simulates a bin or door frame)
        Hot spot   at x=1.5m (simulates a stuck radiator valve)
    """

    def __init__(self):
        self.start_time = time.time()
        self._step = 0

    def read(self, robot: RobotState) -> SensorReading:
        self._step += 1
        elapsed_ms = int((time.time() - self.start_time) * 1000)

        # Simulate corridor walls — left and right ~30cm
        left_wall   = 30.0 + random.uniform(-2, 2)
        right_wall  = 30.0 + random.uniform(-2, 2)
        rear_clear  = 120.0

        # Obstacle at x=2.0m — narrows forward reading as robot approaches
        obstacle_dist = max(5.0, (2.0 - robot.x) * 100)  # cm
        forward = min(obstacle_dist, 150.0) + random.uniform(-3, 3)

        # Build 12-point sweep (every 30°)
        # Index 0=forward, 3=left, 6=rear, 9=right
        sweep = [
            forward,                          # 0° forward
            min(forward + 20, 150),           # 30°
            min(forward + 40, 150),           # 60°
            left_wall,                         # 90° left
            min(left_wall + 20, 150),          # 120°
            rear_clear,                        # 150°
            rear_clear,                        # 180° rear
            rear_clear,                        # 210°
            min(right_wall + 20, 150),         # 240°
            right_wall,                        # 270° right
            min(forward + 40, 150),            # 300°
            min(forward + 20, 150),            # 330°
        ]
        sweep = [round(d + random.uniform(-1, 1), 1) for d in sweep]

        # Hot spot at x=1.0–2.0m raises temperature
        base_temp = 19.0
        if 1.0 <= robot.x <= 2.0:
            base_temp = 26.0  # Stuck radiator valve zone
        temperature = round(base_temp + random.uniform(-0.3, 0.3), 1)
        humidity    = round(55.0 + random.uniform(-2, 2), 1)

        return SensorReading(
            forward_cm=round(forward, 1),
            sweep_cm=sweep,
            temperature=temperature,
            humidity=humidity,
            timestamp_ms=elapsed_ms,
        )


# ── PATH PLANNER ──────────────────────────────────────────────────────────────

class PathPlanner:
    """
    Three-layer planning:
      1. Obstacle avoidance  — hard stop if forward < OBSTACLE_THRESHOLD
      2. Wall following      — maintain target distance from left wall
      3. 360° sweep logic    — if stuck, do a full sweep and pick best direction
    """

    OBSTACLE_THRESHOLD_CM = 25.0   # Stop and turn if closer than this
    WALL_TARGET_CM        = 30.0   # Ideal distance from left wall
    WALL_TOLERANCE_CM     = 8.0    # Acceptable deviation before correcting
    STUCK_THRESHOLD_CM    = 15.0   # Forward distance that triggers full sweep
    SPEED_NORMAL          = 1.0
    SPEED_TURNING         = 0.6
    STEP_SIZE_M           = 0.05   # How far robot moves per step (metres)

    def __init__(self):
        self.consecutive_obstacles = 0
        self.last_action = "IDLE"

    def decide(self, reading: SensorReading, state: RobotState) -> tuple[str, float, float]:
        """
        Returns (action, speed, turn_angle_deg).
        turn_angle_deg: positive = turn right, negative = turn left
        """

        # ── Layer 1: Full sweep if very stuck ────────────────────────────────
        if reading.forward_cm < self.STUCK_THRESHOLD_CM:
            self.consecutive_obstacles += 1
            if self.consecutive_obstacles >= 3:
                best_dir = self._sweep_best_direction(reading.sweep_cm)
                self.consecutive_obstacles = 0
                return ("SWEEP_TURN", self.SPEED_TURNING, best_dir)
        else:
            self.consecutive_obstacles = 0

        # ── Layer 2: Obstacle avoidance ───────────────────────────────────────
        if reading.forward_cm < self.OBSTACLE_THRESHOLD_CM:
            # Turn toward whichever side has more space
            if reading.left_cm > reading.right_cm:
                return ("AVOID_TURN_LEFT", self.SPEED_TURNING, -45.0)
            else:
                return ("AVOID_TURN_RIGHT", self.SPEED_TURNING, 45.0)

        # ── Layer 3: Wall following (left wall) ───────────────────────────────
        error = reading.left_cm - self.WALL_TARGET_CM  # +ve = too far, −ve = too close

        if abs(error) > self.WALL_TOLERANCE_CM:
            if error > 0:
                # Drifted too far from left wall — steer left
                return ("WALL_CORRECT_LEFT", self.SPEED_NORMAL, -15.0)
            else:
                # Too close to left wall — steer right
                return ("WALL_CORRECT_RIGHT", self.SPEED_NORMAL, 15.0)

        # All clear — drive straight
        return ("FORWARD", self.SPEED_NORMAL, 0.0)

    def _sweep_best_direction(self, sweep_cm: List[float]) -> float:
        """
        Finds the direction with the most open space from a 360° sweep.
        Returns the turn angle in degrees.
        """
        best_idx   = sweep_cm.index(max(sweep_cm))
        best_angle = best_idx * 30.0  # Each index = 30°
        # Convert to turn angle: 0=forward, 90=right, 180=back, 270=left
        if best_angle > 180:
            best_angle -= 360  # Normalise to -180..180
        return best_angle


# ── SIMULATION RUNNER ─────────────────────────────────────────────────────────

def run_simulation(steps: int = 60, step_delay: float = 0.3):
    """
    Runs the robot simulation for `steps` steps, printing decisions to terminal.
    step_delay: seconds between steps (0.3 = readable in real time)
    """

    robot   = RobotState()
    sensor  = FakeSensorReader()
    planner = PathPlanner()

    print("=" * 65)
    print("  ThermalScout — Path Planning Simulation")
    print("  Corridor: walls ~30cm each side | Obstacle at x=2.0m")
    print("  Hot spot: x=1.0–2.0m (stuck radiator, ~26°C)")
    print("=" * 65)
    print(f"  {'Step':>4}  {'X':>5}  {'Fwd':>5}  {'L':>5}  {'R':>5}  {'Temp':>5}  Action")
    print("-" * 65)

    hot_zones = []  # Track positions where temp > 22°C for summary

    for step in range(1, steps + 1):
        reading = sensor.read(robot)
        action, speed, turn = planner.decide(reading, robot)

        # Update simulated position
        robot.heading_deg = (robot.heading_deg + turn) % 360
        rad = math.radians(robot.heading_deg)
        move = PathPlanner.STEP_SIZE_M * speed
        robot.x += move * math.cos(math.radians(90 - robot.heading_deg))
        robot.y += move * math.sin(math.radians(90 - robot.heading_deg))
        robot.distance_travelled += move
        robot.action = action
        robot.speed  = speed

        # Flag hot zones
        if reading.temperature > 22.0:
            hot_zones.append((round(robot.x, 2), reading.temperature))
            temp_flag = f"{reading.temperature}°C ⚠"
        else:
            temp_flag = f"{reading.temperature}°C"

        # Print step
        print(
            f"  {step:>4}  "
            f"{robot.x:>4.1f}m  "
            f"{reading.forward_cm:>4.0f}cm  "
            f"{reading.left_cm:>4.0f}cm  "
            f"{reading.right_cm:>4.0f}cm  "
            f"{temp_flag:<10}  "
            f"{action}"
            + (f"  ({turn:+.0f}°)" if turn != 0 else "")
        )

        time.sleep(step_delay)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 65)
    print(f"  Run complete. Distance travelled: {robot.distance_travelled:.2f}m")
    print(f"  Final position: x={robot.x:.2f}m, y={robot.y:.2f}m")

    if hot_zones:
        print(f"\n  HOT ZONES DETECTED ({len(hot_zones)} readings above 22°C):")
        # Deduplicate nearby positions
        seen = set()
        for (x, temp) in hot_zones:
            bucket = round(x * 2) / 2  # Group by 0.5m buckets
            if bucket not in seen:
                seen.add(bucket)
                print(f"     x ≈ {x:.1f}m  →  {temp}°C")
    else:
        print("  No significant hot zones detected.")

    print("=" * 65)

if __name__ == "__main__":
    run_simulation(steps=60, step_delay=0.3)