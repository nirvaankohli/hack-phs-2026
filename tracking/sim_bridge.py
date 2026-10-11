"""Serve the Skyborne bird sim and stream the live wing pose to it.

wing_controller.py --sim uses this instead of emulating keys, so the bird's
wings can copy the wearer's arms exactly: the page subscribes to /pose
(Server-Sent Events) and receives every camera frame's roll and height.
Standard library only; listens on localhost.
"""

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SIM_DIR = Path(__file__).resolve().parent.parent / "sim"


class PoseStream:
    """Latest pose, with a way for listeners to wait for the next one."""

    def __init__(self):
        self.condition = threading.Condition()
        self.message = b'{"active": false}'
        self.sequence = 0

    def publish(self, data):
        with self.condition:
            self.message = json.dumps(data).encode()
            self.sequence += 1
            self.condition.notify_all()

    def wait(self, seen, timeout=1.0):
        """Return (sequence, message) once newer than `seen`, or the current one after `timeout`."""
        with self.condition:
            self.condition.wait_for(lambda: self.sequence != seen, timeout)
            return self.sequence, self.message


class SimHandler(SimpleHTTPRequestHandler):
    stream = None

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path != "/pose":
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        seen = -1
        try:
            while True:
                # Repeats the last pose about once a second while idle, which doubles as a keepalive.
                seen, message = self.stream.wait(seen)
                self.wfile.write(b"data: " + message + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def serve_sim(stream, port=8123, directory=SIM_DIR):
    """Serve `directory` and the pose stream on http://localhost:port in a background thread."""
    handler = type("BoundSimHandler", (SimHandler,), {"stream": stream})
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(handler, directory=str(directory)))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
