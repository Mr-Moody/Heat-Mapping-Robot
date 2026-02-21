"""
Point cloud processing: convert polar (angle, distance) to Cartesian (x, y, z).
Coordinate system: robot at origin, heading 0° = +Y (North), angles CW from forward.
Three.js mapping: X = East, Y = 0 (ground), Z = North.
"""

import math
from typing import List


def polar_to_cartesian(
    angle_deg: float,
    distance_cm: float,
    robot_x: float = 0.0,
    robot_y: float = 0.0,
    robot_heading_deg: float = 0.0,
) -> tuple[float, float, float]:
    """
    Convert polar reading to Cartesian (x, y, z) in world coordinates.
    - angle_deg: 0 = forward (robot heading), CW positive
    - distance_cm: distance in cm
    - Returns (x, y, z) in metres. Y = 0 (ground plane).
    """
    distance_m = distance_cm / 100.0
    # Sensor-relative: forward = 0°, so local x = sin(angle), local z = cos(angle)
    angle_rad = math.radians(angle_deg)
    local_x = distance_m * math.sin(angle_rad)
    local_z = distance_m * math.cos(angle_rad)
    # Rotate by robot heading (heading 0 = North = +Z, 90 = East = +X)
    heading_rad = -math.radians(robot_heading_deg)  # CW heading to CCW rotation
    cos_h = math.cos(heading_rad)
    sin_h = math.sin(heading_rad)
    world_x = local_x * cos_h - local_z * sin_h
    world_z = local_x * sin_h + local_z * cos_h
    world_x += robot_x
    world_z += robot_y  # path planner y = North = our Z
    return (world_x, 0.0, world_z)


def readings_to_points(
    readings: List[tuple[float, float]],
    robot_x: float,
    robot_y: float,
    robot_heading_deg: float,
) -> List[list[float]]:
    """Convert list of (angle_deg, distance_cm) to list of [x, y, z]."""
    points = []
    for angle_deg, distance_cm in readings:
        if distance_cm > 0 and distance_cm < 400:  # Sanity filter (4m max)
            x, y, z = polar_to_cartesian(
                angle_deg, distance_cm, robot_x, robot_y, robot_heading_deg
            )
            points.append([x, y, z])
    return points


def add_to_ring_buffer(
    buffer: List[list[float]],
    new_points: List[list[float]],
    max_size: int = 2000,
) -> List[list[float]]:
    """Append new points to buffer, cap at max_size (FIFO)."""
    combined = buffer + new_points
    if len(combined) <= max_size:
        return combined
    return combined[-max_size:]
