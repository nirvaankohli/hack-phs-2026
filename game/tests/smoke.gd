extends SceneTree

const Flight = preload("res://scripts/flight.gd")
var failures := 0

func check(value: bool, message: String) -> void:
	if not value:
		push_error(message)
		failures += 1

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	game.testing = true
	root.add_child(game)
	game.set_process(false)
	game.muted = true
	game.control_mode = "keyboard"
	check(Flight.next_velocity(0, "flap", 1) < 0, "Flap must climb")
	check(Flight.next_velocity(0, "glide", 1) > 0, "Glide must descend")
	check(Flight.next_velocity(0, "dive", 1) > Flight.next_velocity(0, "glide", 1) * 3, "Dive stays faster than glide")
	game.second_color_enabled = false
	game.marker_color = Color.GREEN
	game.hue_tolerance = 15
	game.shade_tolerance = 160
	game.min_dot_area = 30
	check(game.hue_preview_query() == "?color=%2300ff00&hue_tolerance=15&shade_tolerance=160&min_dot_area=30", "Preview URL must encode the color without interpreting percent as formatting")
	game.show_wing_colors()
	game.editing_color_slot = 1
	game.second_color_enabled = true
	game.set_editing_marker_color(Color.RED)
	check(game.marker_color == Color.GREEN, "Editing color 2 preserves color 1")
	check(game.hue_preview_query().ends_with("&second_color=%23ff0000"), "Preview combines both selected colors")
	game.toggle_dropper()
	check(game.hue_preview_query() == "", "Eyedropper requests original camera pixels")
	var sample_image := Image.create(400, 300, false, Image.FORMAT_RGB8)
	sample_image.fill(Color.GREEN)
	sample_image.fill_rect(Rect2i(200, 0, 200, 300), Color.BLUE)
	game.dropper_image = sample_image
	var pick := InputEventMouseButton.new()
	pick.button_index = MOUSE_BUTTON_LEFT
	pick.pressed = true
	pick.position = Vector2(360, 180)
	game.on_dropper_input(pick)
	check(game.second_marker_color == Color.BLUE, "Eyedropper samples the clicked image location into color 2")
	check(game.marker_color == Color.GREEN, "Eyedropper leaves color 1 unchanged")
	check(not game.dropper_active, "Eyedropper returns to highlighted preview after picking")
	game.second_color_enabled = false
	game.editing_color_slot = 0
	game.show_setup()
	check(game.screen == "setup", "Portrait setup opens")
	game.show_settings("setup")
	game.close_settings()
	check(game.screen == "setup", "Settings returns to setup")
	game.camera_on = true
	game.start_run()
	check(game.preview != null and game.preview.size == Vector2(240, 180), "Flight has a 4:3 corner camera preview")
	game.camera_on = false
	check(game.score == 0 and game.obstacles.is_empty(), "New run resets score and hazards")
	game.pickups.append({"x": 300.0, "y": 330.0})
	game.step_game(0.016)
	check(game.coins == 1 and game.score == 5, "Coin pickup updates the counter and score")
	game.start_run()
	game.spawn_hazard()
	check(game.obstacles.size() == 1 and game.pickups.size() == 1, "Individual cloud and collectible spawn")
	game.obstacles[0].x = 290.0
	game.avatar_y = 500.0
	game.step_game(0.016)
	check(game.screen == "play", "Open air below a cloud is safe")
	game.avatar_y = game.obstacles[0].y
	game.step_game(0.016)
	check(game.screen == "play" and game.hearts == 2, "Cloud contact costs one heart")
	game.take_hit()
	check(game.hearts == 2, "Protection prevents consecutive damage")
	game.hit_protection = 0
	game.take_hit()
	check(game.hearts == 1 and game.screen == "play", "Second hit leaves one heart")
	game.hit_protection = 0
	game.take_hit()
	check(game.hearts == 0 and game.screen == "results", "Third hit ends run")
	game.start_run()
	check(game.score == 0 and game.elapsed == 0 and game.obstacles.is_empty() and game.hearts == 3, "Retry resets run and all hearts")
	game.avatar_y = 670
	game.step_game(0.016)
	check(game.hearts == 2 and game.avatar_y == 330 and game.screen == "play", "Falling costs a heart and returns player to safe height")
	game.start_run()
	game.elapsed = 59.99
	game.avatar_y = 350
	game.step_game(0.02)
	check(game.screen == "results" and game.run_won and game.score == 100, "Finish grants completion bonus")
	game.start_run()
	game.show_pause(false)
	game.resume_run()
	check(game.screen == "play" and game.countdown == 2, "Resume gives countdown")
	game.control_mode = "wings"
	game.tracking_ok = false
	game.start_run()
	check(game.screen == "settings", "Uncalibrated physical controls cannot start")
	game.control_mode = "keyboard"
	game.start_run()
	game.control_mode = "wings"
	game._process(0.02)
	check(game.screen == "pause" and game.lost_pause, "Tracking loss pauses")
	game.control_mode = "keyboard"
	game.start_run()
	var counts := [0, 0, 0, 0, 0]
	for i in 50: counts[game.next_bird()] += 1
	check(counts == [10, 10, 10, 10, 10], "Every bird species has equal frequency")
	game.elapsed = 0
	var first_speed: float = game.hazard_speed()
	var first_interval: float = game.spawn_interval()
	game.elapsed = 50
	check(game.hazard_speed() > first_speed and game.spawn_interval() < first_interval, "Difficulty ramps in speed and density")
	for i in 30: game.spawn_hazard()
	for hazard in game.obstacles:
		check(hazard.kind in ["cloud", "bird"], "No pipe obstacles")
		check(hazard.radius.y < 50, "Hazards leave vertical room to dodge")
	game.queue_free()
	await process_frame
	print("CLOUDBOUND SMOKE: ", "PASS" if failures == 0 else str(failures) + " FAILURES")
	quit(failures)
