
import argparse
import re

import cv2
import numpy as np


def parse_hex(value):
    value = value.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("Use six hex digits, e.g. #00FF00")
    return "#" + value.upper()


def color_hsv(color):
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    return cv2.cvtColor(np.uint8([[rgb]]), cv2.COLOR_RGB2HSV)[0, 0]


def sample_color(frame, x, y):
    """Read a small patch of the raw camera frame, returning an RGB hex color."""
    if not (0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]):
        return None
    patch = frame[max(0, y - 2):y + 3, max(0, x - 2):x + 3]
    bgr = np.median(patch, axis=(0, 1)).astype(int)
    return "#%02X%02X%02X" % tuple(bgr[::-1])


def detect_points(frame, color, hue_tolerance=15, sv_tolerance=160, min_area=30):
    """Return significant color blobs, sorted by camera X, and the binary mask."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.int16)
    target = color_hsv(color).astype(np.int16)
    delta = np.abs(hsv[:, :, 0] - target[0])
    hue_matches = np.minimum(delta, 180 - delta) <= hue_tolerance
    # Hue is undefined for gray/white/black targets.
    if target[1] < 30:
        hue_matches = np.ones(frame.shape[:2], dtype=bool)
    matches = hue_matches & (np.abs(hsv[:, :, 1] - target[1]) <= sv_tolerance)
    matches &= np.abs(hsv[:, :, 2] - target[2]) <= sv_tolerance
    mask = matches.astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    points = []
    for contour in contours:
        if cv2.contourArea(contour) < min_area:
            continue
        m = cv2.moments(contour)
        if m["m00"]:
            points.append((m["m10"] / m["m00"], m["m01"] / m["m00"]))
    return sorted(points), mask


MEASUREMENT_KEYS = (
    "average_height",
    "left_distance_from_center",
    "right_distance_from_center",
    "left_height_relative_to_average",
    "right_height_relative_to_average",
)


def measurements(points):

    right_outer, right_inner, center, left_inner, left_outer = sorted(points)
    average_y = sum(p[1] for p in points) / 5
    return {
        "average_height": average_y,
        "left_distance_from_center": (left_inner[0] + left_outer[0]) / 2 - center[0],
        "right_distance_from_center": center[0] - (right_inner[0] + right_outer[0]) / 2,
        "left_height_relative_to_average": average_y - (left_inner[1] + left_outer[1]) / 2,
        "right_height_relative_to_average": average_y - (right_inner[1] + right_outer[1]) / 2,
    }
