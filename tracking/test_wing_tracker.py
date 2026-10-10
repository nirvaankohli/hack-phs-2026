

import argparse
import re
import sys
import unittest

import cv2
import numpy as np

from wing_tracker import MEASUREMENT_KEYS, detect_points, measurements


def parse_hex(value):
    value = value.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise argparse.ArgumentTypeError("Use six hex digits, e.g. #00FF00")
    return "#" + value.upper()


def sample_color(frame, x, y):
    """Read a small patch of the raw camera frame, returning an RGB hex color."""
    if not (0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]):
        return None
    patch = frame[max(0, y - 2):y + 3, max(0, x - 2):x + 3]
    bgr = np.median(patch, axis=(0, 1)).astype(int)
    return "#%02X%02X%02X" % tuple(bgr[::-1])



def common_hues(frame, tolerance=15):

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    pixels = hsv[(hsv[:, :, 1] >= 40) & (hsv[:, :, 2] >= 40)]
    if not len(pixels):
        return []
    hues = pixels[:, 0].astype(int)
    counts = np.bincount(hues, minlength=180)
    bins = np.arange(180)
    distances = np.abs(bins[:, None] - bins[None, :])
    bands = np.minimum(distances, 180 - distances) <= tolerance
    groups = []
    for _ in range(3):
        center = int(np.argmax(bands @ counts))
        included = bands[center] & (counts > 0)
        count = int(counts[included].sum())
        if not count:
            break
        selected = pixels[included[hues]]
        # Circular averaging keeps reds at 359 and 1 degrees together at 0.
        angles = selected[:, 0].astype(float) * (2 * np.pi / 180)
        hue = float(np.arctan2(np.sin(angles).mean(), np.cos(angles).mean())
                    % (2 * np.pi) * 180 / (2 * np.pi))
        average = np.uint8([[[round(hue) % 180,
                             round(float(selected[:, 1].mean())),
                             round(float(selected[:, 2].mean()))]]])
        bgr = tuple(int(v) for v in cv2.cvtColor(average, cv2.COLOR_HSV2BGR)[0, 0])
        groups.append({"hue": hue * 2, "percent": count / len(pixels) * 100,
                       "bgr": bgr, "hex": "#%02X%02X%02X" % bgr[::-1]})
        counts[included] = 0
    return groups


def preview_hues():
    parser = argparse.ArgumentParser(description="Live top 3 grouped camera hues")
    parser.add_argument("--hues", action="store_true")
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    window = "Most common hues"
    capture = cv2.VideoCapture(args.camera)
    try:
        if not capture.isOpened():
            raise RuntimeError("Cannot open camera. Check permissions or try --camera 1.")
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.createTrackbar("Group radius (degrees)", window, 30, 90, lambda _: None)
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Camera stopped delivering frames.")
            radius = cv2.getTrackbarPos("Group radius (degrees)", window)
            # Sample a smaller image to keep live analysis lightweight.
            sample = cv2.resize(frame, (320, max(1, round(320 * frame.shape[0] / frame.shape[1]))))
            groups = common_hues(sample, radius / 2)
            panel = np.full((185, max(800, frame.shape[1]), 3), 24, np.uint8)
            cv2.putText(panel, "Top hues | share of colored pixels | Q/Esc: quit", (15, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)
            for index in range(3):
                y = 40 + index * 45
                label = f"{index + 1}. No other hue detected"
                if index < len(groups):
                    group = groups[index]
                    cv2.rectangle(panel, (15, y), (65, y + 30), group["bgr"], -1)
                    label = (f"{index + 1}. {group['hex']}   Hue {group['hue']:.0f} deg"
                             f"   {group['percent']:.1f}%")
                cv2.putText(panel, label, (80, y + 23), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, (240, 240, 240), 1, cv2.LINE_AA)
            view = cv2.copyMakeBorder(frame, 0, 0, 0, panel.shape[1] - frame.shape[1],
                                      cv2.BORDER_CONSTANT)
            cv2.imshow(window, np.vstack((view, panel)))
            if cv2.waitKey(1) & 0xFF in (27, ord("q"), ord("Q")):
                break
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()


def draw_tracking(frame, points):
    points = [tuple(round(v) for v in p) for p in points]
    center = points[2]
    # Each wing forms a triangle: center to both markers, plus marker to marker.
    for indexes, color in (((0, 1), (255, 200, 80)), ((3, 4), (90, 210, 255))):
        cv2.polylines(frame, [np.array([center, points[indexes[0]], points[indexes[1]]])],
                      True, color, 2, cv2.LINE_AA)
    for point, label in zip(points, ("R2", "R1", "CENTER", "L1", "L2")):
        cv2.circle(frame, point, 9, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, label, (point[0] + 12, point[1] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)


def preview_wings():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Run the webcam demo")
    parser.add_argument("--color", type=parse_hex, default="#034E57",
                        help="Marker hex color (default: teal from the screenshot)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    args = parser.parse_args()
    window = "Wing tracker"
    capture = cv2.VideoCapture(args.camera)
    editing = None
    show_mask = False
    raw_frame = None

    def pick_color(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and raw_frame is not None:
            selected = sample_color(raw_frame, x, y)
            if selected:
                args.color = selected

    try:
        if not capture.isOpened():
            raise RuntimeError("Cannot open camera. Check camera permissions or try --camera 1.")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.createTrackbar("Hue tolerance", window, 15, 90, lambda _: None)
        # Ink saturation varies substantially with lighting and paper texture.
        cv2.createTrackbar("Shade tolerance", window, 160, 255, lambda _: None)
        cv2.createTrackbar("Min dot area", window, 30, 1000, lambda _: None)
        cv2.setMouseCallback(window, pick_color)
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Camera stopped delivering frames. Check its connection.")
            raw_frame = frame.copy()
            points, mask = detect_points(
                frame, args.color,
                cv2.getTrackbarPos("Hue tolerance", window),
                cv2.getTrackbarPos("Shade tolerance", window),
                max(1, cv2.getTrackbarPos("Min dot area", window)),
            )
            view = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) if show_mask else frame
            valid = len(points) == 5
            if valid:
                draw_tracking(view, points)
                values = [f"{name.replace('_', ' ').title()}: {value:.1f} px" for name, value in measurements(points).items()]
            else:
                for x, y in points:
                    cv2.circle(view, (round(x), round(y)), 9, (0, 210, 255), 2, cv2.LINE_AA)
                values = [f"{name.replace('_', ' ').title()}: --" for name in MEASUREMENT_KEYS]
            status = "TRACKING 5/5" if valid else f"Found {len(points)} dots - need exactly 5"
            color_line = (f"New hex: #{editing}_  (6 digits, Enter to apply, Esc to cancel)"
                          if editing is not None else f"Color: {args.color}  |  C: change color  M: mask  Q/Esc: quit")
            lines = [status] + values + [color_line, "Click the middle of a dot to pick its camera color"]
            # Separate panel keeps the measurements from covering the camera image.
            panel = np.full((250, max(800, view.shape[1]), 3), 24, dtype=np.uint8)
            for i, line in enumerate(lines):
                cv2.putText(panel, line, (16, 27 + i * 29), cv2.FONT_HERSHEY_SIMPLEX,
                            0.57, (235, 235, 235), 1, cv2.LINE_AA)
            view = cv2.copyMakeBorder(view, 0, 0, 0, panel.shape[1] - view.shape[1],
                                      cv2.BORDER_CONSTANT)
            cv2.imshow(window, np.vstack((view, panel)))
            key = cv2.waitKey(1) & 0xFF
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
            if editing is not None:
                if key == 27:
                    editing = None
                elif key in (8, 127):
                    editing = editing[:-1]
                elif key in (10, 13) and len(editing) == 6:
                    args.color = parse_hex(editing)
                    editing = None
                elif chr(key) in "0123456789abcdefABCDEF" and len(editing) < 6:
                    editing += chr(key).upper()
            elif key in (27, ord("q"), ord("Q")):
                break
            elif key in (ord("c"), ord("C")):
                editing = ""
            elif key in (ord("m"), ord("M")):
                show_mask = not show_mask
    finally:
        capture.release()
        cv2.destroyAllWindows()



class TrackerTests(unittest.TestCase):
    points = [(40, 60), (100, 100), (200, 160), (260, 120), (340, 80)]

    def frame(self, color, points=None):
        frame = np.zeros((240, 400, 3), dtype=np.uint8)
        for point in self.points if points is None else points:
            cv2.circle(frame, point, 9, color, -1)
        return frame

    def test_green_detection_and_measurements(self):
        frame = self.frame((77, 63, 31))  # OpenCV uses BGR; hex uses RGB.
        cv2.circle(frame, (20, 200), 2, (77, 63, 31), -1)  # Ignore tiny noise.
        points, _ = detect_points(frame, "#034E57")
        self.assertEqual(points, self.points)
        self.assertEqual(measurements(points), {
            "left_distance_from_center": 100,
            "right_distance_from_center": 130,
            "average_height": 104,
            "left_height_relative_to_average": 4,
            "right_height_relative_to_average": 24,
        })
        draw_tracking(frame, points)

    def test_body_movement_preserves_relative_measurements(self):
        original = measurements(self.points)
        moved = measurements([(x + 30, y + 20) for x, y in self.points])
        for name in ("left_distance_from_center", "right_distance_from_center", "left_height_relative_to_average", "right_height_relative_to_average"):
            self.assertEqual(original[name], moved[name])
        self.assertEqual(moved["average_height"], original["average_height"] + 20)

    def test_side_heights_above_and_below_average(self):
        values = measurements([(40, 60), (100, 60), (200, 100), (260, 140), (340, 140)])
        self.assertEqual(values["average_height"], 100)
        self.assertEqual(values["left_height_relative_to_average"], -40)
        self.assertEqual(values["right_height_relative_to_average"], 40)

    def test_teal_markers_with_lighting_variation(self):
        # HSV samples from the five ink dots in the reported camera screenshot.
        samples = [(102, 121, 80), (99, 110, 96), (100, 164, 84),
                   (99, 160, 95), (101, 156, 70)]
        frame = np.full((240, 400, 3), 180, np.uint8)
        for point, hsv in zip(self.points, samples):
            bgr = cv2.cvtColor(np.uint8([[hsv]]), cv2.COLOR_HSV2BGR)[0, 0]
            cv2.circle(frame, point, 9, tuple(int(v) for v in bgr), -1)
        points, _ = detect_points(frame, "#034E57")
        self.assertEqual(points, self.points)

    def test_new_color_and_red_hue_wrap(self):
        frame = self.frame((255, 0, 255))
        self.assertEqual(len(detect_points(frame, "#FF00FF")[0]), 5)
        self.assertEqual(len(detect_points(frame, "#00FF00")[0]), 0)
        red = cv2.cvtColor(np.uint8([[[179, 255, 255]]]), cv2.COLOR_HSV2BGR)[0, 0]
        frame = self.frame(tuple(int(v) for v in red))
        self.assertEqual(len(detect_points(frame, "#FF0000")[0]), 5)

    def test_missing_and_extra_markers_are_not_hidden(self):
        for points in (self.points[:4], self.points + [(380, 200)]):
            detected, _ = detect_points(self.frame((0, 255, 0), points), "#00FF00")
            self.assertEqual(len(detected), len(points))
            self.assertNotEqual(len(detected), 5)

    def test_hex_validation(self):
        self.assertEqual(parse_hex("aB12fF"), "#AB12FF")
        for value in ("green", "#GG0000", "123", "1234567"):
            with self.assertRaises(argparse.ArgumentTypeError):
                parse_hex(value)

    def test_camera_color_picker_uses_rgb_and_ignores_panel(self):
        frame = np.full((20, 20, 3), (77, 63, 31), dtype=np.uint8)
        self.assertEqual(sample_color(frame, 10, 10), "#1F3F4D")
        self.assertEqual(sample_color(frame, 0, 0), "#1F3F4D")
        self.assertIsNone(sample_color(frame, 10, 25))

    def test_similar_greens_group_and_rank_together(self):
        hsv = np.uint8([[[h, 255, 255] for h in ([55] * 30 + [65] * 30
                                                 + [110] * 25 + [0] * 15)]])
        groups = common_hues(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR))
        self.assertEqual(len(groups), 3)
        self.assertAlmostEqual(groups[0]["hue"], 120, delta=1)
        self.assertEqual([g["percent"] for g in groups], [60, 25, 15])

    def test_red_wrap_and_neutral_background(self):
        hsv = np.uint8([[[179, 255, 255], [1, 255, 255], [0, 0, 255], [0, 0, 0]]])
        groups = common_hues(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR))
        self.assertEqual(len(groups), 1)
        self.assertLess(min(groups[0]["hue"], 360 - groups[0]["hue"]), 2)
        self.assertEqual(groups[0]["percent"], 100)
        self.assertEqual(common_hues(np.zeros((10, 10, 3), np.uint8)), [])


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv.remove("--test")
        unittest.main()
    else:
        try:
            preview_hues() if "--hues" in sys.argv else preview_wings()
        except (RuntimeError, cv2.error) as error:
            raise SystemExit(str(error)) from error
