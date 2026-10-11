"""Local webcam bridge. Run from repo root: python -m uvicorn game.bridge:app --port 8002."""
from collections import deque
from contextlib import asynccontextmanager
from threading import Lock, Thread
from time import monotonic, sleep

import numpy as np
import cv2
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from face.api import app as face_app
from face.crop_face import crop_face
from tracking.api import app as tracking_app
from tracking import api as tracking_api
from tracking.wing_tracker import detect_points


def largest_dot_contours(mask, min_area):
    """Pick three by area, with position as a stable tie-breaker."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = [c for c in contours if cv2.contourArea(c) >= min_area]
    return sorted(candidates, key=lambda c: (-cv2.contourArea(c), *cv2.boundingRect(c)[:2]))[:3]


def detect_game_points(frame, color, hue_tolerance, shade_tolerance, min_area, second_color=None):
    # Reuse the tracker's color mask; choose blobs only in the game adapter.
    _, mask = detect_points(frame, color, hue_tolerance, shade_tolerance, min_area)
    if second_color is not None:
        _, second_mask = detect_points(frame, second_color, hue_tolerance, shade_tolerance, min_area)
        mask = cv2.bitwise_or(mask, second_mask)
    selected = largest_dot_contours(mask, min_area)
    points = []
    for contour in selected:
        moments = cv2.moments(contour)
        if moments['m00']:
            points.append((moments['m10'] / moments['m00'], moments['m01'] / moments['m00']))
    return sorted(points), selected


def three_point_measurements(points):
    """Game-only adapter: camera-left wing, body center, camera-right wing.

    Keep the existing API field names, but anchor each wing Y to the center
    marker so moving one wing cannot look like motion in the other wing.
    Camera-right is the player's left, matching the original tracker's labels.
    """
    if len(points) != 3:
        return None
    right, center, left = sorted(points)
    if not right[0] < center[0] < left[0]:
        return None
    return {
        'average_height': (right[1] + center[1] + left[1]) / 3,
        'left_distance_from_center': left[0] - center[0],
        'right_distance_from_center': center[0] - right[0],
        'left_height_relative_to_average': center[1] - left[1],
        'right_height_relative_to_average': center[1] - right[1],
    }


class FlightClassifier:
    """Both wing Ys oscillate to flap; both below the center dot means dive."""
    WINDOW = 0.70
    MOTION_STEP = 0.012  # Fraction of calibrated spread-wing span; rejects jitter.
    MOTION_RANGE = 0.030

    def __init__(self):
        self.span = None
        self.reset_motion()

    def reset_motion(self):
        self.samples = deque()
        self.events = (deque(), deque())
        self.anchors = None
        self.last_time = None
        self.flap_until = 0.0
        self.diving = False
        self.lowered_since = None

    def calibrate(self, values):
        span = values['left_distance_from_center'] + values['right_distance_from_center']
        if span < 30:
            raise ValueError('Spread both wings so all three markers are separated.')
        self.span = span
        self.reset_motion()

    def update(self, values, now):
        if self.span is None:
            return 'uncalibrated'
        if self.last_time is not None and (now <= self.last_time or now - self.last_time > 0.25):
            self.reset_motion()
        self.last_time = now
        ys = (values['left_height_relative_to_average'] / self.span,
              values['right_height_relative_to_average'] / self.span)
        self.samples.append((now, *ys))
        while self.samples and now - self.samples[0][0] > self.WINDOW:
            self.samples.popleft()
        if self.anchors is None:
            self.anchors = list(ys)
        active = []
        for side, y in enumerate(ys):
            change = y - self.anchors[side]
            if abs(change) >= self.MOTION_STEP:
                self.events[side].append((now, 1 if change > 0 else -1))
                self.anchors[side] = y
            events = self.events[side]
            while events and now - events[0][0] > self.WINDOW:
                events.popleft()
            heights = [sample[side + 1] for sample in self.samples]
            reversals = sum(events[i][1] != events[i - 1][1] for i in range(1, len(events)))
            active.append(bool(events) and now - events[-1][0] < 0.22
                          and reversals >= 2 and max(heights) - min(heights) >= self.MOTION_RANGE)
        if all(active):
            self.flap_until = now + 0.18

        # Relative Y is positive above the body dot, negative below it.
        # Scale the small dead zone with calibrated span, independent of tuck.
        drop = 0.03 if self.diving else 0.05
        lowered = all(y < -drop for y in ys)
        if now < self.flap_until:
            self.lowered_since = None
            self.diving = False
            return 'flap'
        if lowered:
            if self.lowered_since is None:
                self.lowered_since = now
            self.diving = now - self.lowered_since >= 0.18
        else:
            self.lowered_since = None
            self.diving = False
        return 'dive' if self.diving else 'glide'


def dominant_hues(frame):
    """Three distinct chromatic hue peaks; ignore gray, white, and dark pixels."""
    sample = cv2.resize(frame, (160, 120), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
    valid = (hsv[:, :, 1] >= 60) & (hsv[:, :, 2] >= 45)
    hues = hsv[:, :, 0].astype(int)
    histogram = np.bincount(hues[valid], minlength=180)
    scores = sum(np.roll(histogram, shift) for shift in range(-5, 6))
    available = np.ones(180, dtype=bool)
    result = []
    for _ in range(3):
        ranked = np.where(available, scores, -1)
        candidates = np.flatnonzero(ranked == ranked.max())
        peak = int(candidates[np.argmax(histogram[candidates])])
        if ranked[peak] < 20:
            break
        distance = np.minimum(abs(hues - peak), 180 - abs(hues - peak))
        members = valid & (distance <= 5)
        saturation, value = np.median(hsv[members, 1:3], axis=0).astype(int)
        rgb = cv2.cvtColor(np.uint8([[[peak, saturation, value]]]), cv2.COLOR_HSV2RGB)[0, 0]
        result.append({'hue': peak * 2, 'color': '#%02X%02X%02X' % tuple(rgb),
                       'percent': round(float(members.sum()) / valid.size * 100, 1)})
        circular_distance = np.minimum(abs(np.arange(180) - peak), 180 - abs(np.arange(180) - peak))
        available[circular_distance <= 15] = False
    return result


def capture_frame(frame):
    """Match the 4:3 preview and capture without stretching a camera feed."""
    height, width = frame.shape[:2]
    unit = min(width // 4, height // 3)
    crop_width, crop_height = unit * 4, unit * 3
    left, top = (width - crop_width) // 2, (height - crop_height) // 2
    return frame[top:top + crop_height, left:left + crop_width].copy()


class DotMemory:
    """Hold one complete pose for one missing frame, never chain held poses."""
    def __init__(self):
        self.previous = []

    def update(self, points):
        if three_point_measurements(points) is not None:
            self.previous = list(points)
            return list(points), False
        held = self.previous
        self.previous = []
        return held, bool(held)


class Camera:
    def __init__(self):
        self.lock = Lock()
        self.running = False
        self.thread = None
        self.second_color = None
        self.frame = None
        self.frame_time = 0.0
        self.values = None
        self.classifier = FlightClassifier()
        self.dot_memory = DotMemory()
        self.state = {'tracking': False, 'state': 'lost', 'message': 'Camera is off.'}

    def start(self, index):
        if self.running:
            return
        self.running = True
        self.thread = Thread(target=self.loop, args=(index,), daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
        with self.lock:
            self.frame = None
            self.values = None
            self.classifier = FlightClassifier()
            self.dot_memory = DotMemory()
            self.state = {'tracking': False, 'state': 'lost', 'message': 'Camera is off.'}

    def loop(self, index):
        cap = cv2.VideoCapture(index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        last_config = None
        try:
            while self.running:
                ok, frame = cap.read()
                if not ok:
                    with self.lock:
                        self.dot_memory = DotMemory()
                        self.state = {'tracking': False, 'state': 'lost', 'message': 'Cannot read camera. Check camera permission and device index.'}
                    sleep(0.15)
                    continue
                with self.lock:
                    config = tracking_api.settings
                    secondary = self.second_color
                points, _ = detect_game_points(frame, config.color, config.hue_tolerance,
                                           config.shade_tolerance, config.min_dot_area, secondary)
                now = monotonic()
                with self.lock:
                    if (config, secondary) != last_config:
                        self.classifier = FlightClassifier()
                        self.dot_memory = DotMemory()
                        last_config = (config, secondary)
                    if now - self.frame_time > 0.25:
                        self.dot_memory = DotMemory()
                    self.frame = frame
                    self.frame_time = now
                    effective_points, held = self.dot_memory.update(points)
                    self.values = three_point_measurements(effective_points)
                    flight = (self.state.get('state', 'glide') if held else self.classifier.update(self.values, now)) if self.values else 'lost'
                    if not self.values:
                        self.classifier.reset_motion()
                    self.state = {
                        'tracking': self.values is not None,
                        'calibrated': self.classifier.span is not None,
                        'state': flight, 'dot_count': len(points), 'color': config.color,
                        'points': effective_points, 'held': held,
                        'variables': dict(self.values) if self.values else None,
                        'span_ratio': ((self.values['left_distance_from_center'] + self.values['right_distance_from_center']) / self.classifier.span
                                       if self.values and self.classifier.span else None),
                        'message': ('Using previous frame.' if held else 'Using the three largest markers.') if self.values else "Wings can't be seen.",
                    }
                sleep(0.025)
        finally:
            cap.release()

    def snapshot(self, dots=False):
        with self.lock:
            if self.frame is None or monotonic() - self.frame_time > 1:
                raise HTTPException(503, 'No fresh camera image. Enable the camera and check permissions.')
            image = self.frame.copy()
            if dots:
                tint = (50, 195, 255) if self.state.get('held') else (220, 255, 255)
                for x, y in self.state.get('points', []):
                    point = (round(x), round(y))
                    cv2.circle(image, point, 11, (35, 40, 25), 5)
                    cv2.circle(image, point, 11, tint, 2)
                    cv2.circle(image, point, 3, tint, -1)
            return capture_frame(image)


camera = Camera()


@asynccontextmanager
async def lifespan(_app):
    yield
    camera.stop()


app = FastAPI(title='Cloudbound camera bridge', lifespan=lifespan)
# Preserve the existing APIs, with their existing schemas and settings.
app.mount('/face', face_app)
app.mount('/tracking', tracking_app)


class CameraSettings(BaseModel):
    index: int = Field(default=0, ge=0, le=10)


class GameTrackingSettings(tracking_api.Settings):
    second_color: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')


@app.post('/camera/settings')
def set_game_tracking(settings: GameTrackingSettings):
    with camera.lock:
        tracking_api.settings = tracking_api.Settings(**settings.model_dump(exclude={'second_color'}))
        camera.second_color = settings.second_color
    return settings.model_dump()


@app.get('/health')
def health():
    return {'ok': True, 'camera': camera.running}


@app.post('/camera/start')
def start(settings: CameraSettings):
    camera.start(settings.index)
    return {'ok': True}


@app.post('/camera/stop')
def stop():
    camera.stop()
    return {'ok': True}


def highlight_hue(frame, color, hue_tolerance=None, shade_tolerance=None, min_dot_area=None, second_color=None):
    """Dim nonmatches and outline significant blobs using the tracker itself."""
    config = tracking_api.settings
    _, selected = detect_game_points(frame, color,
                                     config.hue_tolerance if hue_tolerance is None else hue_tolerance,
                                     config.shade_tolerance if shade_tolerance is None else shade_tolerance,
                                     config.min_dot_area if min_dot_area is None else min_dot_area, second_color)
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.drawContours(mask, selected, -1, 255, cv2.FILLED)
    result = (frame * 0.28).astype(np.uint8)
    result[mask > 0] = frame[mask > 0]
    for contour in selected:
        cv2.drawContours(result, [contour], -1, (35, 40, 25), 5)
        cv2.drawContours(result, [contour], -1, (220, 255, 255), 2)
    return result


@app.get('/camera/frame')
def frame(color: str | None = Query(default=None, pattern=r'^#[0-9a-fA-F]{6}$'),
          hue_tolerance: int | None = Query(default=None, ge=0, le=90),
          shade_tolerance: int | None = Query(default=None, ge=0, le=255),
          min_dot_area: int | None = Query(default=None, ge=1, le=100000),
          dots: bool = False,
          second_color: str | None = Query(default=None, pattern=r'^#[0-9a-fA-F]{6}$')):
    image = camera.snapshot(dots=True) if dots else camera.snapshot()
    if color is not None:
        image = highlight_hue(image, color, hue_tolerance, shade_tolerance, min_dot_area, second_color)
    ok, data = cv2.imencode('.jpg', cv2.flip(image, 1), [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise HTTPException(500, 'Could not encode camera image.')
    return Response(data.tobytes(), media_type='image/jpeg', headers={'Cache-Control': 'no-store'})


@app.post('/camera/capture')
def capture():
    try:
        result = crop_face(cv2.flip(camera.snapshot(), 1))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(503, 'Face models are missing. See face/README.md.') from error
    ok, data = cv2.imencode('.png', result)
    if not ok:
        raise HTTPException(500, 'Could not encode face.')
    return Response(data.tobytes(), media_type='image/png', headers={'Cache-Control': 'no-store'})


@app.post('/camera/calibrate')
def calibrate():
    with camera.lock:
        if camera.values is None or camera.state.get('held') or monotonic() - camera.frame_time > 0.5:
            raise HTTPException(422, 'Keep all three markers visible and spread your wings.')
        try:
            camera.classifier.calibrate(camera.values)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    return {'ok': True}


@app.get('/camera/state')
def state():
    with camera.lock:
        if monotonic() - camera.frame_time > 0.5:
            return {'tracking': False, 'state': 'lost', 'message': 'Waiting for a fresh camera image.'}
        return dict(camera.state)


@app.get('/camera/hues')
def hues():
    return {'colors': dominant_hues(camera.snapshot())}
