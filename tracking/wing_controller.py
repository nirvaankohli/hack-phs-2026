"""Turn the cardboard wing into a controller for any flight game.

Put a dot on each wingtip (or use --dots 5 for the full 5-dot wing).
Tilt the wing to bank, raise or lower it to pitch, and swing it down sharply
to flap. Emulated input goes to whichever window has focus, so control starts
paused: hold the wing level, click into the game, then press F8 to calibrate
that pose as neutral and take control. F8 again pauses. Q/Esc in the tracker
window quits. Click a dot in the tracker window to pick its color. If it
sees dots that aren't there, press M to view the color mask and lower the sliders.

    python wing_controller.py                                    # GeoFS / flight sims
    python wing_controller.py --hotkey f11 --split               # YSFlight, side by side
    python wing_controller.py --gamepad                          # analog Xbox stick
"""

import argparse
import math
import threading
import time
from collections import deque

import cv2
import numpy as np

from test_wing_tracker import draw_tracking
from wing_tracker import color_hsv, detect_points, measurements, parse_hex, sample_color


def wing_pose(values):
    """Return (roll degrees, height px, span px). Positive roll = left wing up."""
    span = values["left_distance_from_center"] + values["right_distance_from_center"]
    rise = values["left_height_relative_to_average"] - values["right_height_relative_to_average"]
    return math.degrees(math.atan2(rise, span)), values["average_height"], span


def tip_pose(points):
    """Pose from just two wingtip dots, in the same form as wing_pose."""
    right, left = sorted(points)
    span = left[0] - right[0]
    # Camera Y grows downward, so a raised left tip has the smaller Y.
    return math.degrees(math.atan2(right[1] - left[1], span)), (left[1] + right[1]) / 2, span


def largest_dots(mask, min_area, count=5):
    """Return the `count` biggest blobs' centers sorted by X, plus how many blobs matched.

    Stray specks of a similar color are usually smaller than the real markers,
    so extra matches no longer break tracking.
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = []
    for contour in contours:
        m = cv2.moments(contour)
        if cv2.contourArea(contour) >= min_area and m["m00"]:
            blobs.append((cv2.contourArea(contour), m["m10"] / m["m00"], m["m01"] / m["m00"]))
    blobs.sort(reverse=True)
    return sorted((x, y) for _, x, y in blobs[:count]), len(blobs)


def shape(value, deadzone):
    """Clamp to [-1, 1] and rescale so the deadzone edge maps to zero."""
    magnitude = min(1.0, max(0.0, (abs(value) - deadzone) / (1 - deadzone)))
    return math.copysign(magnitude, value)


class KeyAxis:
    """Pulse one of two keys with a duty cycle proportional to the axis value.

    Keyboard-only games get an analog feel: half deflection holds the key on
    roughly every other frame, full deflection holds it continuously.
    """

    def __init__(self, negative, positive):
        self.keys = (negative, positive)
        self.level = 0.0

    def step(self, value):
        self.level += abs(value)
        if self.level >= 1:
            self.level -= 1
            return self.keys[value > 0]
        return None


def parse_key(name):
    from pynput.keyboard import Key
    name = name.strip().lower()
    if hasattr(Key, name):
        return getattr(Key, name)
    if len(name) == 1:
        return name
    raise argparse.ArgumentTypeError(f"Unknown key {name!r}; use e.g. left, space, w")


def parse_key_pair(value):
    names = value.split(",")
    if len(names) != 2:
        raise argparse.ArgumentTypeError("Use two comma-separated keys, e.g. left,right")
    return tuple(parse_key(name) for name in names)


class KeyboardOutput:
    def __init__(self, roll_keys, pitch_keys, flap_key):
        from pynput.keyboard import Controller
        self.keyboard = Controller()
        self.roll = KeyAxis(*roll_keys)
        self.pitch = KeyAxis(*pitch_keys)
        self.flap_key = flap_key
        self.held = set()

    def update(self, roll, pitch, flap):
        wanted = {key for key in (self.roll.step(roll), self.pitch.step(pitch)) if key}
        for key in self.held - wanted:
            self.keyboard.release(key)
        for key in wanted - self.held:
            self.keyboard.press(key)
        self.held = wanted
        if flap and self.flap_key:
            self.keyboard.tap(self.flap_key)
        return sorted(str(key).replace("Key.", "") for key in wanted)

    def release_all(self):
        for key in self.held:
            self.keyboard.release(key)
        self.held = set()


class GamepadOutput:
    """Virtual Xbox 360 pad; needs `pip install vgamepad` and the ViGEmBus driver."""

    def __init__(self):
        import vgamepad
        self.vgamepad = vgamepad
        self.pad = vgamepad.VX360Gamepad()
        self.flap_frames = 0

    def update(self, roll, pitch, flap):
        # Flight-sim convention: pull the stick back (down) to climb.
        self.pad.left_joystick_float(x_value_float=roll, y_value_float=-pitch)
        button = self.vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A
        if flap:
            self.pad.press_button(button=button)
            self.flap_frames = 3
        elif self.flap_frames:
            self.flap_frames -= 1
            if not self.flap_frames:
                self.pad.release_button(button=button)
        self.pad.update()
        return [f"stick {roll:+.2f} {-pitch:+.2f}"]

    def release_all(self):
        self.flap_frames = 0
        self.pad.reset()
        self.pad.update()


class FlapDetector:
    """Detect a sharp downward swing of the whole wing."""

    def __init__(self, drop, window=0.25, cooldown=0.35):
        self.drop, self.window, self.cooldown = drop, window, cooldown
        self.history = deque()
        self.ready_at = 0.0

    def update(self, now, height, span):
        self.history.append((now, height))
        while self.history[0][0] < now - self.window:
            self.history.popleft()
        # Camera Y grows downward, so a flap raises height above the window's minimum.
        if now >= self.ready_at and height - min(h for _, h in self.history) > self.drop * span:
            self.ready_at = now + self.cooldown
            self.history.clear()
            return True
        return False

    def reset(self):
        self.history.clear()


def work_area():
    """Usable screen rectangle (x, y, width, height), excluding the Windows taskbar."""
    import ctypes
    from ctypes import wintypes
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def draw_bar(panel, x, y, label, value):
    cv2.putText(panel, label, (x, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (235, 235, 235), 1, cv2.LINE_AA)
    left, width, middle = x + 70, 240, x + 70 + 120
    cv2.rectangle(panel, (left, y), (left + width, y + 20), (70, 70, 70), 1)
    cv2.rectangle(panel, (middle, y + 2), (middle + round(value * 118), y + 18),
                  (90, 210, 255), -1)
    cv2.line(panel, (middle, y - 3), (middle, y + 23), (235, 235, 235), 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--color", type=parse_hex, default="#7848C0",
                        help="Marker hex color (default: purple #7848C0)")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--hue-tolerance", type=int, default=8)
    parser.add_argument("--shade-tolerance", type=int, default=80)
    parser.add_argument("--min-area", type=int, default=30)
    parser.add_argument("--roll-keys", type=parse_key_pair, default="left,right",
                        help="Keys for bank left,bank right (default: left,right)")
    parser.add_argument("--pitch-keys", type=parse_key_pair, default="up,down",
                        help="Keys for nose down,nose up. Default up,down matches flight "
                             "sims like GeoFS and YSFlight")
    parser.add_argument("--flap-key", type=parse_key, default=None,
                        help="Key tapped on a flap, e.g. space (default: off)")
    parser.add_argument("--gamepad", action="store_true",
                        help="Emit a virtual Xbox stick instead of keys")
    parser.add_argument("--max-roll", type=float, default=30,
                        help="Wing tilt in degrees for full bank (default: 30)")
    parser.add_argument("--pitch-range", type=float, default=0.3,
                        help="Raise/lower distance for full pitch, as a fraction of "
                             "wingspan (default: 0.3)")
    parser.add_argument("--deadzone", type=float, default=0.15)
    parser.add_argument("--flap-drop", type=float, default=0.25,
                        help="Downward swing within 0.25 s that counts as a flap, as a "
                             "fraction of wingspan (default: 0.25)")
    parser.add_argument("--hotkey", type=parse_key, default="f8",
                        help="Global key that calibrates and starts/pauses (default: f8; "
                             "use f11 for YSFlight, which uses F8 for a camera view)")
    parser.add_argument("--split", action="store_true",
                        help="Dock the tracker window on the right half of the screen, "
                             "leaving the left half for the game")
    parser.add_argument("--dots", type=int, choices=(2, 5), default=2,
                        help="Markers on the wing: 2 (one per wingtip) or 5 (default: 2)")
    args = parser.parse_args()

    from pynput.keyboard import Listener

    if args.gamepad:
        output = GamepadOutput()
    else:
        output = KeyboardOutput(args.roll_keys, args.pitch_keys, args.flap_key)
    flaps = FlapDetector(args.flap_drop)
    toggle = threading.Event()
    # Global hotkey: the game, not the tracker window, has focus while flying.
    listener = Listener(on_press=lambda key: toggle.set() if key == args.hotkey else None)
    hotkey_name = str(args.hotkey).replace("Key.", "").upper()
    listener.start()

    window = "Wing controller"
    capture = cv2.VideoCapture(args.camera)
    raw_frame = None
    active = False
    neutral = None
    roll_axis = pitch_axis = 0.0
    flap_shown_until = 0.0
    # Clicking the button focuses this window, so START counts down to give
    # time to click back into the game before keys are sent.
    start_at = None
    button = {"rect": None, "clicked": False}

    def on_mouse(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        rect = button["rect"]
        if rect and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
            button["clicked"] = True
        elif raw_frame is not None:
            selected = sample_color(raw_frame, x, y)
            if selected:
                args.color = selected

    try:
        if not capture.isOpened():
            raise RuntimeError("Cannot open camera. Check permissions or try --camera 1.")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        if args.split:
            x, y, width, height = work_area()
            cv2.moveWindow(window, x + width // 2, y)
            cv2.resizeWindow(window, width // 2, height - 40)  # Leave room for the title bar.
        cv2.setMouseCallback(window, on_mouse)
        cv2.createTrackbar("Hue tolerance", window, args.hue_tolerance, 90, lambda _: None)
        cv2.createTrackbar("Shade tolerance", window, args.shade_tolerance, 255, lambda _: None)
        cv2.createTrackbar("Min dot area", window, args.min_area, 2000, lambda _: None)
        show_mask = False
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Camera stopped delivering frames. Check its connection.")
            raw_frame = frame.copy()
            now = time.monotonic()
            min_area = max(1, cv2.getTrackbarPos("Min dot area", window))
            _, mask = detect_points(frame, args.color,
                                    cv2.getTrackbarPos("Hue tolerance", window),
                                    cv2.getTrackbarPos("Shade tolerance", window), min_area)
            points, found = largest_dots(mask, min_area, args.dots)
            pose = None
            if len(points) == args.dots == 5:
                pose = wing_pose(measurements(points))
            elif len(points) == args.dots == 2:
                pose = tip_pose(points)
            if pose and pose[2] <= 0:
                pose = None

            if button["clicked"]:
                button["clicked"] = False
                if active or start_at:
                    active, start_at = False, None
                else:
                    start_at = now + 3
            if start_at and now >= start_at:
                start_at = None
                if pose:
                    toggle.set()
            if toggle.is_set():
                toggle.clear()
                start_at = None
                if active:
                    active = False
                elif pose:
                    neutral = pose
                    active = True
                    roll_axis = pitch_axis = 0.0
                    flaps.reset()

            pressed = []
            if active and pose:
                roll, height, _ = pose
                target_roll = shape((roll - neutral[0]) / args.max_roll, args.deadzone)
                target_pitch = shape((neutral[1] - height) / (neutral[2] * args.pitch_range),
                                     args.deadzone)
                # Light smoothing hides dot jitter without adding noticeable lag.
                roll_axis += 0.5 * (target_roll - roll_axis)
                pitch_axis += 0.5 * (target_pitch - pitch_axis)
                flap = flaps.update(now, height, neutral[2])
                if flap:
                    flap_shown_until = now + 0.4
                pressed = output.update(roll_axis, pitch_axis, flap)
            else:
                # Fail safe: never leave a key held while tracking is lost or paused.
                output.release_all()
                roll_axis = pitch_axis = 0.0
                flaps.reset()

            view = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) if show_mask else frame
            if pose and args.dots == 5:
                draw_tracking(view, points)
            elif pose:
                tips = [(round(x), round(y)) for x, y in points]
                cv2.line(view, *tips, (90, 210, 255), 2, cv2.LINE_AA)
                for point, label in zip(tips, ("R", "L")):
                    cv2.circle(view, point, 9, (255, 255, 255), 2, cv2.LINE_AA)
                    cv2.putText(view, label, (point[0] + 12, point[1] - 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
            else:
                for x, y in points:
                    cv2.circle(view, (round(x), round(y)), 9, (0, 210, 255), 2, cv2.LINE_AA)

            panel = np.full((175, max(800, view.shape[1]), 3), 24, np.uint8)
            if not pose:
                status, color = f"LOST: found {found} dots, need {args.dots} (input released)", (80, 80, 255)
            elif active:
                status, color = f"FLYING - click PAUSE or press {hotkey_name}", (120, 230, 120)
            elif start_at:
                status, color = (f"STARTING IN {math.ceil(start_at - now)} - click the game, hold wing level",
                                 (0, 210, 255))
            else:
                status, color = f"PAUSED - click START or press {hotkey_name}", (0, 210, 255)
            cv2.putText(panel, status, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
            draw_bar(panel, 16, 50, "Roll", roll_axis)
            draw_bar(panel, 16, 82, "Pitch", pitch_axis)
            if now < flap_shown_until:
                cv2.putText(panel, "FLAP!", (350, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                            (90, 210, 255), 2, cv2.LINE_AA)
            if found > args.dots:
                cv2.putText(panel, f"{found} blobs matched, using the {args.dots} biggest", (420, 66),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 210, 255), 1, cv2.LINE_AA)
            if color_hsv(args.color)[1] < 30:
                # detect_points ignores hue for grayish targets, so nearly everything matches.
                cv2.putText(panel, "Picked color is too gray - click the middle of a dot",
                            (420, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 80, 255), 1, cv2.LINE_AA)
            cv2.putText(panel, "Sending: " + (", ".join(pressed) or "-"), (16, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
            cv2.putText(panel, f"Color {args.color} (click a dot to pick) | M: mask | Q/Esc: quit",
                        (16, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1, cv2.LINE_AA)
            label, fill = (("PAUSE", (40, 40, 190)) if active else
                           ("CANCEL", (90, 90, 90)) if start_at else ("START", (40, 150, 40)))
            bx, by, bw, bh = panel.shape[1] - 180, 100, 160, 60
            cv2.rectangle(panel, (bx, by), (bx + bw, by + bh), fill, -1)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
            cv2.putText(panel, label, (bx + (bw - tw) // 2, by + (bh + th) // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
            # Clicks arrive in stacked-image coordinates, below the camera view.
            button["rect"] = (bx, view.shape[0] + by, bx + bw, view.shape[0] + by + bh)
            view = cv2.copyMakeBorder(view, 0, 0, 0, panel.shape[1] - view.shape[1],
                                      cv2.BORDER_CONSTANT)
            cv2.imshow(window, np.vstack((view, panel)))
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            if key in (ord("m"), ord("M")):
                show_mask = not show_mask
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        output.release_all()
        listener.stop()
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, cv2.error) as error:
        raise SystemExit(str(error)) from error
