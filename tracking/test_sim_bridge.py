import json
import threading
import time
import unittest
import urllib.request

from sim_bridge import PoseStream, serve_sim


class SimBridgeTests(unittest.TestCase):
    def test_wait_returns_newer_pose(self):
        stream = PoseStream()
        seen, _ = stream.wait(-1, timeout=0)
        threading.Timer(0.05, stream.publish, [{"active": True, "roll": 12}]).start()
        sequence, message = stream.wait(seen, timeout=2)
        self.assertNotEqual(sequence, seen)
        self.assertEqual(json.loads(message)["roll"], 12)

    def test_wait_times_out_with_current_pose(self):
        stream = PoseStream()
        start = time.monotonic()
        sequence, message = stream.wait(stream.sequence, timeout=0.05)
        self.assertGreaterEqual(time.monotonic() - start, 0.04)
        self.assertEqual(json.loads(message), {"active": False})

    def test_serves_page_and_pose_events(self):
        stream = PoseStream()
        server = serve_sim(stream, port=0)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with urllib.request.urlopen(base + "/index.html", timeout=5) as page:
            self.assertIn(b"Skyborne", page.read())
        stream.publish({"active": True, "lift": 0.2})
        with urllib.request.urlopen(base + "/pose", timeout=5) as events:
            self.assertEqual(events.headers["Content-Type"], "text/event-stream")
            line = events.readline()
        self.assertEqual(json.loads(line.removeprefix(b"data: ")), {"active": True, "lift": 0.2})


if __name__ == "__main__":
    unittest.main()
