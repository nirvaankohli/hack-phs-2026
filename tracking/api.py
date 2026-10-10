"""Run w: uvicorn tracking.api:app --reload"""

from threading import Lock

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from .wing_tracker import MEASUREMENT_KEYS, detect_points, measurements


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    color: str = Field(default="#00FF00", pattern=r"^#[0-9a-fA-F]{6}$")
    hue_tolerance: int = Field(default=15, ge=0, le=90, strict=True)
    shade_tolerance: int = Field(default=160, ge=0, le=255, strict=True)
    min_dot_area: int = Field(default=30, ge=1, le=1000000, strict=True)


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    hue_tolerance: int | None = Field(default=None, ge=0, le=90, strict=True)
    shade_tolerance: int | None = Field(default=None, ge=0, le=255, strict=True)
    min_dot_area: int | None = Field(default=None, ge=1, le=1000000, strict=True)


app = FastAPI(title="Wing Tracker")
settings = Settings()
settings_lock = Lock()


@app.get("/settings", response_model=Settings)
def get_settings():
    return settings


@app.post("/settings", response_model=Settings)
def set_settings(update: SettingsUpdate):

    global settings
    changes = update.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(422, "Settings cannot be null")
    with settings_lock:
        settings = Settings(**(settings.model_dump() | changes))
        return settings


@app.post("/track")
def track(file: UploadFile = File(...)):

    config = settings  # Immutable snapshot for this request.
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image must be at most 10 MiB")
    try:
        frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
    except cv2.error:
        frame = None
    if frame is None:
        raise HTTPException(400, "Upload a valid image")
    points, _ = detect_points(frame, config.color, config.hue_tolerance,
                              config.shade_tolerance, config.min_dot_area)
    valid = len(points) == 5
    values = measurements(points) if valid else dict.fromkeys(MEASUREMENT_KEYS)
    labels = ("right_1", "right_2", "center", "left_1", "left_2")
    return {
        "tracking": valid,
        "dot_count": len(points),
        "variables": values,
        "dots": [{"x": x, "y": y, "label": labels[i] if valid else None}
                 for i, (x, y) in enumerate(points)],
        "image": {"width": frame.shape[1], "height": frame.shape[0]},
        "settings": config.model_dump(),
    }
