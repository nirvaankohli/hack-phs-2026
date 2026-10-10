"""Run from the project root: uvicorn face.api:app --port 8001"""

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

from .crop_face import crop_face


app = FastAPI(title="Face Cutout")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@app.post("/crop", response_class=Response,
          responses={200: {"content": {"image/png": {}}}})
def crop(file: UploadFile = File(...)):
    """Upload an image; return a transparent PNG with headwear and no neck."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image must be at most 10 MiB")
    try:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
    except cv2.error:
        image = None
    if image is None:
        raise HTTPException(400, "Upload a valid image")
    try:
        cutout = crop_face(image)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(503, "Face models are missing; see face/README.md") from error
    ok, png = cv2.imencode(".png", cutout)
    if not ok:
        raise HTTPException(500, "Could not encode the cutout")
    return Response(png.tobytes(), media_type="image/png",
                    headers={"Content-Disposition": 'inline; filename="face.png"'})
