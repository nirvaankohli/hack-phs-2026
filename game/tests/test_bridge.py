import unittest
from time import monotonic
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from game.bridge import FlightClassifier, app, camera, capture_frame, dominant_hues, three_point_measurements, highlight_hue, detect_game_points, DotMemory, Camera


def pose(span=200, height=0):
    return {'left_distance_from_center': span / 2, 'right_distance_from_center': span / 2,
            'left_height_relative_to_average': height, 'right_height_relative_to_average': height}


class TwoColorTests(unittest.TestCase):
    def test_two_colors_combine_into_three_markers_without_duplicates(self):
        import cv2
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        for x, color in [(80, (0, 255, 0)), (200, (0, 0, 255)), (320, (0, 255, 0))]:
            cv2.circle(frame, (x, 100), 15, color, -1)
        single, _ = detect_game_points(frame, '#00FF00', 15, 160, 30)
        combined, _ = detect_game_points(frame, '#00FF00', 15, 160, 30, '#FF0000')
        duplicate, _ = detect_game_points(frame, '#00FF00', 15, 160, 30, '#00FF00')
        self.assertEqual(len(single), 2)
        self.assertEqual(combined, [(80, 100), (200, 100), (320, 100)])
        self.assertEqual(duplicate, single)
        self.assertEqual(highlight_hue(frame, '#00FF00', second_color='#FF0000')[100, 200, 2], 255)

    def test_settings_and_preview_accept_optional_second_color(self):
        from tracking import api as tracking_api
        original, secondary = tracking_api.settings, camera.second_color
        try:
            client = TestClient(app)
            response = client.post('/camera/settings', json={'color': '#00FF00', 'second_color': '#FF0000'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(camera.second_color, '#FF0000')
            with patch.object(camera, 'snapshot', return_value=np.zeros((40, 40, 3), dtype=np.uint8)):
                self.assertEqual(client.get('/camera/frame', params={'color': '#00FF00', 'second_color': '#FF0000'}).status_code, 200)
                self.assertEqual(client.get('/camera/frame', params={'second_color': 'bad'}).status_code, 422)
            self.assertEqual(client.post('/camera/settings', json={'second_color': 'bad'}).status_code, 422)
            self.assertEqual(client.post('/camera/settings', json={'second_color': None}).status_code, 200)
            self.assertIsNone(camera.second_color)
        finally:
            tracking_api.settings, camera.second_color = original, secondary


class DotMemoryTests(unittest.TestCase):
    def test_one_missing_frame_holds_pose_but_second_loses_it(self):
        memory = DotMemory()
        points = [(100, 100), (200, 200), (300, 100)]
        self.assertEqual(memory.update(points), (points, False))
        self.assertEqual(memory.update(points[:2]), (points, True))
        self.assertEqual(memory.update([]), ([], False))
        self.assertEqual(memory.update([]), ([], False))
        self.assertEqual(memory.update(points), (points, False))
        self.assertEqual(memory.update([]), (points, True))

    def test_no_history_cannot_invent_positions(self):
        self.assertEqual(DotMemory().update([]), ([], False))

    def test_inset_marks_held_positions_without_changing_camera_image(self):
        cam = Camera()
        cam.frame = np.zeros((300, 400, 3), dtype=np.uint8)
        cam.frame_time = monotonic()
        cam.state = {'points': [(100, 100)], 'held': True}
        image = cam.snapshot(dots=True)
        self.assertEqual(tuple(image[100, 100]), (50, 195, 255))
        self.assertEqual(int(cam.frame.sum()), 0)
        cam.state = {'points': [], 'held': False}
        self.assertEqual(int(cam.snapshot(dots=True).sum()), 0)


class HuePreviewTests(unittest.TestCase):
    def test_minimum_dot_area_controls_preview(self):
        import cv2
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.circle(frame, (50, 50), 10, (0, 255, 0), -1)
        self.assertEqual(highlight_hue(frame, '#00FF00', min_dot_area=30)[50, 50, 1], 255)
        self.assertLess(highlight_hue(frame, '#00FF00', min_dot_area=500)[50, 50, 1], 80)
        with patch.object(camera, 'snapshot', return_value=frame):
            client = TestClient(app)
            self.assertEqual(client.get('/camera/frame', params={'color': '#00FF00', 'min_dot_area': 500}).status_code, 200)
            self.assertEqual(client.get('/camera/frame', params={'min_dot_area': 0}).status_code, 422)

    def test_preview_tolerances_are_live_without_changing_settings(self):
        from tracking import api as tracking_api
        config = tracking_api.settings
        frame = np.full((40, 40, 3), (0, 180, 0), dtype=np.uint8)
        strict = highlight_hue(frame, '#00FF00', 0, 10)
        loose = highlight_hue(frame, '#00FF00', 0, 100)
        self.assertLess(strict[20, 20, 1], 60)
        self.assertEqual(loose[20, 20, 1], 180)
        with patch.object(camera, 'snapshot', return_value=frame):
            client = TestClient(app)
            self.assertEqual(client.get('/camera/frame', params={'color': '#00FF00', 'hue_tolerance': 0, 'shade_tolerance': 100}).status_code, 200)
            self.assertEqual(client.get('/camera/frame', params={'hue_tolerance': 91}).status_code, 422)
            self.assertEqual(client.get('/camera/frame', params={'shade_tolerance': -1}).status_code, 422)
        self.assertEqual(tracking_api.settings, config)

    def test_preview_preserves_matches_and_dims_other_colors(self):
        import cv2
        frame = np.full((300, 400, 3), 120, dtype=np.uint8)
        cv2.circle(frame, (100, 150), 30, (0, 255, 0), -1)
        cv2.circle(frame, (300, 150), 30, (0, 0, 255), -1)
        before = frame.copy()
        result = highlight_hue(frame, '#00FF00')
        self.assertEqual(tuple(result[150, 100]), (0, 255, 0))
        self.assertLess(result[150, 300, 2], 80)
        np.testing.assert_array_equal(frame, before)
        with patch.object(camera, 'snapshot', return_value=frame):
            client = TestClient(app)
            response = client.get('/camera/frame', params={'color': '#00FF00'})
            self.assertEqual(response.status_code, 200)
            decoded = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
            self.assertGreater(decoded[150, 299, 1], 240)  # Mirrored like setup.
            self.assertEqual(client.get('/camera/frame').status_code, 200)
            self.assertEqual(client.get('/camera/frame', params={'color': 'invalid'}).status_code, 422)


class ThreePointTests(unittest.TestCase):
    def test_three_largest_dots_ignore_extra_matches(self):
        import cv2
        image = np.zeros((300, 400, 3), dtype=np.uint8)
        # Smaller distractors precede and follow the actual three markers.
        for x, y, radius in [(30, 60, 6), (100, 160, 18), (200, 200, 15), (300, 160, 21), (370, 60, 8)]:
            cv2.circle(image, (x, y), radius, (0, 255, 0), -1)
        points, contours = detect_game_points(image, '#00FF00', 15, 160, 30)
        self.assertEqual(points, [(100, 160), (200, 200), (300, 160)])
        self.assertEqual(len(contours), 3)
        self.assertIsNotNone(three_point_measurements(points))
        preview = highlight_hue(image, '#00FF00')
        self.assertEqual(preview[160, 100, 1], 255)
        self.assertLess(preview[60, 30, 1], 80)

    def test_equal_size_dots_have_stable_selection_and_missing_dots_fail(self):
        import cv2
        image = np.zeros((100, 400, 3), dtype=np.uint8)
        for x in [50, 150, 250, 350]:
            cv2.circle(image, (x, 50), 10, (0, 255, 0), -1)
        points, _ = detect_game_points(image, '#00FF00', 15, 160, 30)
        self.assertEqual(points, [(50, 50), (150, 50), (250, 50)])
        points, _ = detect_game_points(image[:, :200], '#00FF00', 15, 160, 30)
        self.assertEqual(len(points), 2)
        self.assertIsNone(three_point_measurements(points))

    def test_three_points_map_wings_and_center(self):
        values = three_point_measurements([(300, 175), (100, 180), (200, 200)])
        self.assertEqual(values['left_distance_from_center'], 100)
        self.assertEqual(values['right_distance_from_center'], 100)
        self.assertEqual(values['left_height_relative_to_average'], 25)
        self.assertEqual(values['right_height_relative_to_average'], 20)

    def test_body_translation_does_not_change_wing_heights(self):
        points = [(100, 180), (200, 200), (300, 175)]
        before = three_point_measurements(points)
        after = three_point_measurements([(x + 40, y + 70) for x, y in points])
        for name in before:
            if name != 'average_height':
                self.assertEqual(before[name], after[name])

    def test_missing_extra_or_ambiguous_points_are_rejected(self):
        for count in [0, 1, 2, 4, 5]:
            self.assertIsNone(three_point_measurements([(i * 50, 100) for i in range(count)]))
        self.assertIsNone(three_point_measurements([(100, 100), (100, 150), (300, 100)]))

    def test_one_wing_does_not_move_other_measurement(self):
        first = three_point_measurements([(100, 180), (200, 200), (300, 180)])
        second = three_point_measurements([(100, 140), (200, 200), (300, 180)])
        self.assertEqual(first['left_height_relative_to_average'], second['left_height_relative_to_average'])
        self.assertNotEqual(first['right_height_relative_to_average'], second['right_height_relative_to_average'])

    def test_real_detector_accepts_three_dots_for_game(self):
        import cv2
        from tracking.wing_tracker import detect_points
        frame = np.zeros((300, 400, 3), dtype=np.uint8)
        for point in [(100, 160), (200, 200), (300, 160)]:
            cv2.circle(frame, point, 9, (0, 255, 0), -1)
        points, _ = detect_points(frame, '#00FF00')
        self.assertEqual(len(points), 3)
        self.assertIsNotNone(three_point_measurements(points))
        client = TestClient(app)
        _, png = cv2.imencode('.png', frame)
        response = client.post('/tracking/track', files={'file': ('dots.png', png.tobytes(), 'image/png')})
        self.assertFalse(response.json()['tracking'])  # Original five-dot API is unchanged.


class HueTests(unittest.TestCase):
    def test_top_three_are_ranked_by_visible_coverage(self):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[:, :80] = (0, 0, 255)
        frame[:, 80:128] = (0, 255, 0)
        frame[:, 128:] = (255, 0, 0)
        colors = dominant_hues(frame)
        self.assertEqual([item['color'] for item in colors], ['#FF0000', '#00FF00', '#0000FF'])
        self.assertEqual([item['percent'] for item in colors], [50.0, 30.0, 20.0])

    def test_neutral_frames_have_no_hue(self):
        for value in [0, 100, 255]:
            self.assertEqual(dominant_hues(np.full((120, 160, 3), value, dtype=np.uint8)), [])

    def test_red_wraparound_is_one_suggestion(self):
        import cv2
        hsv = np.full((120, 160, 3), (0, 255, 255), dtype=np.uint8)
        hsv[:, 80:, 0] = 179
        colors = dominant_hues(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR))
        self.assertEqual(len(colors), 1)
        self.assertEqual(colors[0]['percent'], 100.0)


class CaptureTests(unittest.TestCase):
    def test_camera_capture_is_four_three_without_stretching(self):
        for height, width in [(480, 640), (720, 1280), (800, 600)]:
            original = np.arange(height * width * 3, dtype=np.uint8).reshape(height, width, 3)
            cropped = capture_frame(original)
            h, w = cropped.shape[:2]
            self.assertEqual(w * 3, h * 4)
            self.assertTrue(np.array_equal(cropped[h // 2, w // 2], original[height // 2, width // 2]))


class ClassifierTests(unittest.TestCase):
    def model(self):
        model = FlightClassifier()
        model.calibrate(pose(height=10))
        return model

    def test_both_wing_ys_must_keep_changing_to_flap(self):
        model = self.model()
        states = [model.update(pose(height=y), i * 0.1)
                  for i, y in enumerate([10, 18, 26, 18, 10, 2, 10, 18])]
        self.assertEqual(states[0], 'glide')
        self.assertEqual(states[-1], 'flap')
        for i in range(8, 18):
            state = model.update(pose(height=18), i * 0.1)
        self.assertEqual(state, 'glide')

    def test_single_lowering_is_not_flapping(self):
        model = self.model()
        for i, y in enumerate([10, 4, -2, -8, -14, -14, -14]):
            self.assertNotEqual(model.update(pose(height=y), i * 0.1), 'flap')

    def test_jitter_and_one_wing_motion_do_not_flap(self):
        for one_wing in [False, True]:
            model = self.model()
            for i in range(25):
                values = pose(height=10 + (12 if one_wing else 0.5) * (-1) ** i)
                if one_wing:
                    values['right_height_relative_to_average'] = 10
                self.assertEqual(model.update(values, i * 0.05), 'glide')

    def test_dive_requires_both_wings_below_center_regardless_of_span(self):
        cases = [(pose(span=80, height=10), 'glide'),
                 (pose(span=200, height=-14), 'dive'),
                 (pose(span=80, height=-14), 'dive'),
                 (pose(span=200, height=-4), 'glide'),
                 (pose(span=80, height=-4), 'glide')]
        one_lower = pose(span=80, height=-10)
        one_lower['right_height_relative_to_average'] = 10
        cases.append((one_lower, 'glide'))
        for values, expected in cases:
            model = self.model()
            for i in range(10):
                state = model.update(values, i * 0.1)
            self.assertEqual(state, expected)
            self.assertEqual(model.update(pose(height=10), 1.0), 'glide')

    def test_dive_uses_center_not_calibrated_wing_height(self):
        model = FlightClassifier()
        model.calibrate(pose(height=60))
        for i in range(6):
            self.assertEqual(model.update(pose(height=2), i * 0.1), 'glide')
        for i in range(6, 10):
            state = model.update(pose(height=-14), i * 0.1)
        self.assertEqual(state, 'dive')
        self.assertEqual(model.update(pose(height=-8), 1.0), 'dive')
        self.assertEqual(model.update(pose(height=-4), 1.1), 'glide')

    def test_flapping_takes_priority_over_transient_tuck(self):
        model = self.model()
        for i, y in enumerate([10, 20, 10, 0, -10, 0, -10, 0]):
            state = model.update(pose(span=100, height=y), i * 0.1)
        self.assertEqual(state, 'flap')

    def test_reacquisition_does_not_count_as_stroke(self):
        model = self.model()
        model.update(pose(height=40), 1)
        self.assertEqual(model.update(pose(height=-40), 3), 'glide')
        model.reset_motion()
        self.assertEqual(model.update(pose(height=40), 3.1), 'glide')

    def test_invalid_calibration(self):
        with self.assertRaises(ValueError):
            FlightClassifier().calibrate(pose(span=10))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        camera.frame = None
        camera.frame_time = 0
        camera.values = None
        camera.classifier = FlightClassifier()

    def test_no_camera_is_actionable_and_state_is_lost(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertEqual(self.client.get('/camera/frame').status_code, 503)
        self.assertEqual(self.client.get('/camera/hues').status_code, 503)
        self.assertEqual(self.client.post('/camera/capture').status_code, 503)
        self.assertEqual(self.client.post('/camera/calibrate').status_code, 422)
        self.assertEqual(self.client.get('/camera/state').json()['state'], 'lost')

    def test_preview_capture_and_calibration_contract(self):
        camera.frame = np.zeros((80, 100, 3), dtype=np.uint8)
        camera.frame_time = monotonic()
        camera.values = pose()
        self.assertEqual(self.client.get('/camera/hues').json(), {'colors': []})
        self.assertEqual(self.client.get('/camera/frame').headers['content-type'], 'image/jpeg')
        cutout = np.full((32, 32, 4), 255, dtype=np.uint8)
        with patch('game.bridge.crop_face', return_value=cutout):
            response = self.client.post('/camera/capture')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'\x89PNG'))
        self.assertEqual(self.client.post('/camera/calibrate').status_code, 200)

    def test_existing_apis_remain_mounted(self):
        self.assertEqual(self.client.get('/tracking/settings').status_code, 200)
        response = self.client.post('/tracking/track', files={'file': ('bad.png', b'bad', 'image/png')})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/face/crop', files={'file': ('bad.png', b'bad', 'image/png')})
        self.assertEqual(response.status_code, 400)

    def test_camera_start_requires_valid_index(self):
        self.assertEqual(self.client.post('/camera/start', json={'index': -1}).status_code, 422)
        with patch.object(camera, 'start') as start:
            self.assertEqual(self.client.post('/camera/start', json={'index': 0}).status_code, 200)
            start.assert_called_once_with(0)


if __name__ == '__main__':
    unittest.main()
