# Cloudbound

A native Godot 4 game: your captured face gets angel wings and flies through a 60-second pixel sky. Dodge storm clouds and birds, collect gold coins, and reach the golden sky. The sunglasses sun is decorative and has no collision.

## Run

On this Mac, double-click **launch.command** in this folder. It starts the local camera bridge and Godot together. Camera access begins only after you press **Enable camera** or **Connect** in the game.

Alternatively, from the repository root:

```sh
.venv/bin/python -m uvicorn game.bridge:app --host 127.0.0.1 --port 8002
```

Then import `game/project.godot` in Godot 4 and press F6/F5 to run, or:

```sh
/Applications/Godot.app/Contents/MacOS/Godot --path game
```

Keyboard play works without the bridge. To set up a fresh Python environment, install `face/requirements.txt` and `tracking/requirements.txt` into the same environment. The face models already live in `face/models`. The launcher accepts `GODOT_BIN` and `CLOUDBOUND_PYTHON` overrides.

## Controls

| State | Keyboard | Physical wings | Flight |
| --- | --- | --- | --- |
| Flap | Hold Space or ↑; holding click/touch also works | Repeated up/down changes in both wing Ys | Accelerate upward |
| Glide | Release flap and dive | Hold wings near center height | Descend slowly |
| Dive | Hold ↓ or S | Lower both wings below the center dot and hold briefly | Descend quickly |
| Pause | Escape or pause button | Pause button | Freeze the run |

Dive takes priority if both keyboard controls are held. The hitbox covers only the face, never the wings or halo. The ceiling is forgiving. Each flight starts with three hearts. Obstacles or falling below the lower boundary cost one heart, followed by 1.5 seconds of invulnerability. Falling returns the avatar to center height. The third hit ends the flight. Dive speed is 240 pixels/second (glide is 62). Retry keeps the captured face.

## Incoming hazards

Individual clouds and animated birds approach from the right with open air around each one. All five supplied bird types appear exactly once per shuffled five-bird cycle. Clouds drift gently; birds move faster and bob vertically. Hazard speed rises from 300 to 444 pixels per second (birds add 45), and spawns tighten from 1.45 to 0.85 seconds over the run. Each hazard dodged scores 10 points.

The wings sit closer behind the face. The preview is 400 by 300 pixels (4:3), and both preview and capture use the same centered 4:3 camera crop. The extracted transparent face remains tightly cropped to the head.

## Camera and tracking setup

1. Choose **Play → Enable camera** and allow camera access if macOS asks.
2. Frame your face, choose **Capture face**, and check the winged portrait. Capture again to retake it.
3. In **Controls & calibration**, choose **Physical wings**.
4. Keep all three colored markers visible, spread your wings in a comfortable neutral pose, and press **Calibrate spread wings**.
5. Check the live marker count and FLAP / GLIDE / DIVE readout. Start flying when all three markers are stable.

In **Settings → Wing color**, select **Color 1** or **Color 2** to edit its hue, saturation, and brightness. Enable **Two colors** to detect both at once; the three largest blobs across the combined color mask are used, with overlapping matches counted once. Tolerance and minimum dot size are shared. Choose **Pick from camera**, then click a wing dot in the preview to sample its original color into the selected slot. The picker uses a small median patch to reduce camera noise and never samples the dimmed tracking overlay. Press **Apply** to save both colors. The selection is saved and reapplied when connecting. Recalibrate after changing color. The existing tracker defaults to green `#00FF00`. Its original settings API is available at `http://127.0.0.1:8002/tracking/settings`; use it to change marker color and tolerances for your hardware. The bridge uses those settings immediately. Three marker blobs must remain distinct, including while tucking. Camera index defaults to zero; another index can be selected through `POST /camera/start` after `POST /camera/stop`.

Tracking runs in a background thread and the game polls state independently of rendering. A stale or lost signal pauses the run; resume explicitly after recovery or switch to keyboard in settings. Calibrate while holding your gliding pose with wings spread. The classifier saves the spread wingspan as its distance scale. Place one dot on each wing and one on the body between them; keep the center dot horizontally between the wing dots. In the game bridge, each wing Y is measured relative to the center dot, increases upward, and excludes whole-body translation. The legacy `*_height_relative_to_average` field names are retained for API compatibility, but contain these center-relative heights in the game. Both wings must show significant changing Y values with at least two direction reversals inside a 700 ms window to flap. Small jitter and one-wing movement are ignored. When movement stops, wing height selects glide or dive. Both wing dots more than 5% of the calibrated span below the center dot for 180 ms trigger dive, regardless of current wingspan. Closer to center, level, or higher wings glide. Dive exits when either wing comes within 3% of the calibrated span below center. This small hysteresis prevents flickering; repeated flapping takes priority. Tracking loss clears motion history.

Settings displays live left Y, right Y, and span percentage after calibration. These are also returned as `variables` and `span_ratio` from `/camera/state`. The actual wing rig and lighting still need a hands-on calibration check.

## Local API

The bridge reuses the existing face-cropping and marker-detection implementations. It also mounts their original FastAPI applications without changing them. The game uses its own three-point measurement adapter; `/tracking` is unchanged and its original `/tracking/track` endpoint still expects five markers. The game selects the three largest matching blobs by contour area and ignores smaller matches. It orders the selected dots from left to right to identify the wings and center; fewer than three distinct dots still pauses tracking. The preview highlights only the selected dots.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Bridge health |
| `POST /camera/start` with `{"index":0}` | Explicitly start webcam |
| `POST /camera/stop` | Release webcam and clear calibration |
| `GET /camera/frame` | Mirrored JPEG preview |
| `POST /camera/capture` | Fresh transparent face PNG using `face.crop_face` |
| `POST /camera/calibrate` | Store current spread-wing span |
| `GET /camera/hues` | Top three distinct chromatic hues in the visible camera crop |
| `GET /camera/state` | Tracking validity, calibration, marker count, flight state |
| `/face/crop` | Existing multipart face API |
| `/tracking/track`, `/tracking/settings` | Existing tracking API |

The default bridge binds only to localhost. Portrait and frame data stay in memory, and are not written to disk by the game. Settings and best score are saved in Godot's standard user-data directory. The launcher stops the bridge it started when the game closes.

## Verification

From the repository root:

```sh
.venv/bin/python -m unittest game.tests.test_bridge -v
/Applications/Godot.app/Contents/MacOS/Godot --headless --path game --script tests/smoke.gd
```

`tests/render.gd` renders the home, setup, settings, flight, and results screens to `/tmp/cloudbound-*.png` when run with Godot's graphical renderer. Test scripts suppress saving settings and best scores.

## Assets and implementation

- `assets/sky.png`: supplied sky background, used unchanged.
- Wings, sun, birds, and storm clouds: sprite regions from the exact user-supplied images in `assets/source/`. Original source files remain unchanged; the sprite loader makes flat preview backgrounds transparent in memory.
- All game text uses the bundled [Pixelify Sans](https://github.com/google/fonts/tree/main/ofl/pixelifysans) font; its OFL license is included in `assets/fonts/OFL.txt`.
- Halo, and the optional fallback face remain code-drawn. The title screen contains only Cloudbound, Play, and Settings over the supplied sky and decorative sun.
- Coins: six animation frames from the user-supplied coin sprite sheet in `assets/source/coins.png`.
- Sound effects: synthesized locally; no external audio assets.
- `scripts/main.gd`: game, menus, rendering, and API client.
- `scripts/flight.gd`: shared three-state movement model.
- `scripts/supplied_assets.gd`: supplied sprite-sheet regions and transparent texture loading.
- `bridge.py`: webcam lifecycle and calibrated flight-state classification.

Built with AI assistance. The approved concept's single-flap controls were updated to sustained flap, glide, and dive states at the user's request. No unrelated face or tracking code was changed.

With the bridge running, `tests/network.gd` also verifies native Godot HTTP requests, flight-state JSON, and a real transparent face crop using the repository's existing test photo. It saves the resulting winged portrait screen to `/tmp/cloudbound-real-face.png`. This check does not activate the webcam.
