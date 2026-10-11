"""Run Skyborne on the Cloudbound camera bridge: python sim/server.py

Reuses game/bridge.py unchanged (camera thread, three-marker detection,
calibration, /tracking/settings) and adds two things on the same origin:
the sim's static files, and /pose, a Server-Sent Events stream of the
calibrated wing pose that sim/js/input.js turns into flight.

Markers: one on each wing and one on the body between them, all one color.
"""

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from threading import Lock
from time import monotonic

# On Windows, OpenCV's default Media Foundation backend takes 5-10 s to open a
# webcam; DirectShow takes about 1.5 s. Disable MSMF before cv2 is imported so
# the bridge's VideoCapture(index) picks DirectShow.
if sys.platform == "win32":
    os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_MSMF", "0")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.responses import StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import cv2  # noqa: E402

from game import bridge  # noqa: E402
from game.bridge import app, camera  # noqa: E402
from sim.markers import MarkerDetector  # noqa: E402
from tracking import api as tracking_api  # noqa: E402

# Marker settings tuned for the wing rig (Cloudbound's Wing color sliders:
# hue 346, saturation 53, brightness 77, hue tolerance 8, shade tolerance 114, min dot 1 px).
MARKERS = {"color": "#C45C75", "hue_tolerance": 8, "shade_tolerance": 114, "min_dot_area": 1}


def wing_pose(state, values, classifier, frame_time):
    """Pose relative to the calibrated spread-wing glide pose, in calibrated wingspans.

    left/right: each wing's height above its calibrated height (+ = raised),
    measured from the body marker, so moving the whole body doesn't count.
    roll: degrees, + = player's left wing up (banks right).
    span: current arm reach / calibrated wingspan. Reach is the straight-line distance
    from the body marker to each wing marker, so swinging the arms down to flap keeps it
    near 1 and only bending them in (a tuck) shrinks it.
    """
    base = {"calibrated": classifier.span is not None, "dots": state.get("dot_count", 0)}
    if not values or classifier.span is None:
        return base | {"active": False}
    span = classifier.span
    left = values["left_height_relative_to_average"] / span - classifier.neutral_y[0]
    right = values["right_height_relative_to_average"] / span - classifier.neutral_y[1]
    width = (values["left_distance_from_center"] + values["right_distance_from_center"]) / span
    ratio = (math.hypot(values["left_distance_from_center"], values["left_height_relative_to_average"])
             + math.hypot(values["right_distance_from_center"], values["right_height_relative_to_average"])) / span
    return base | {
        "active": True, "t": frame_time,
        "left": left, "right": right, "lift": (left + right) / 2, "span": ratio,
        "roll": math.degrees(math.atan2(left - right, max(width, 0.2))),
    }


@app.get("/pose")
async def pose():
    async def events():
        last, sent_at = None, 0.0
        while True:
            with camera.lock:
                data = wing_pose(camera.state, camera.values, camera.classifier, camera.frame_time)
                stale = monotonic() - camera.frame_time > 0.5
            if not camera.running or stale:
                data = {"active": False, "calibrated": data["calibrated"], "dots": 0}
            data["camera"] = camera.running
            message = json.dumps(data)
            now = monotonic()
            # New camera frames go out immediately; an unchanged state repeats twice a second.
            if message != last or now - sent_at > 0.5:
                yield f"data: {message}\n\n"
                last, sent_at = message, now
            await asyncio.sleep(1 / 60)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


def configure_markers(**overrides):
    tracking_api.settings = tracking_api.Settings(**(MARKERS | overrides))


def install_detector(**options):
    """Skip the head (lips, turban) and oversized blobs in the camera loop and the marker view."""
    bridge.detect_game_points = detector = MarkerDetector(**options)
    return detector


detector = install_detector()
_snapshot = camera.snapshot


def snapshot_with_head_zone(dots=False):
    """The live camera view, with the ignored head area outlined."""
    image = _snapshot(dots=dots)
    zone = detector.last_zone
    if dots and zone and camera.frame is not None:
        # Same centered 4:3 crop as bridge.capture_frame.
        height, width = camera.frame.shape[:2]
        unit = min(width // 4, height // 3)
        dx, dy = (width - unit * 4) // 2, (height - unit * 3) // 2
        left, top, right, bottom = (round(v) for v in zone)
        cv2.rectangle(image, (left - dx, top - dy), (right - dx, bottom - dy), (40, 40, 40), 4)
        cv2.rectangle(image, (left - dx, top - dy), (right - dx, bottom - dy), (60, 170, 255), 2)
    return image


camera.snapshot = snapshot_with_head_zone


def serialize_camera(cam, wait=5.0):
    """Never let a new capture open the webcam while the last one is still closing.

    bridge.Camera.stop marks the camera off at once but its thread can take a
    moment to release the device, and start only checks that flag. Refreshing
    the page stops and restarts the camera back to back, and two DirectShow
    captures of one webcam crash the whole process (0xc0000374). Start now
    waits for the old capture thread to finish.
    """
    lock = Lock()
    start, stop = cam.start, cam.stop

    def safe_start(index):
        with lock:
            if cam.running:
                return
            old = cam.thread
            if old is not None and old.is_alive():
                old.join(timeout=wait)
                if old.is_alive():
                    raise bridge.HTTPException(503, "The camera is still closing. Try again in a moment.")
            start(index)

    def safe_stop():
        with lock:
            stop()

    cam.start, cam.stop = safe_start, safe_stop


serialize_camera(camera)
configure_markers()


@app.middleware("http")
async def revalidate(request, call_next):
    """Make browsers check for edited sim files instead of running a stale cached copy."""
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-cache")
    return response


# Mounted last so the bridge's API routes and /pose take precedence.
app.mount("/", StaticFiles(directory=ROOT / "sim", html=True), name="sim")


def main():
    import uvicorn
    import webbrowser
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--color", default=MARKERS["color"], help="Marker hex color")
    parser.add_argument("--hue-tolerance", type=int, default=MARKERS["hue_tolerance"])
    parser.add_argument("--shade-tolerance", type=int, default=MARKERS["shade_tolerance"])
    parser.add_argument("--min-dot-area", type=int, default=MARKERS["min_dot_area"])
    parser.add_argument("--max-dot-area", type=int, default=4000,
                        help="Ignore blobs bigger than this many px² (default: 4000)")
    parser.add_argument("--keep-head", action="store_true",
                        help="Don't ignore marker-colored matches on and around the face")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    configure_markers(color=args.color, hue_tolerance=args.hue_tolerance,
                      shade_tolerance=args.shade_tolerance, min_dot_area=args.min_dot_area)
    global detector
    detector = install_detector(max_area=args.max_dot_area, ignore_head=not args.keep_head)
    url = f"http://localhost:{args.port}"
    print(f"Skyborne with camera tracking: {url}")
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
