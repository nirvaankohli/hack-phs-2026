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
	check(Flight.next_velocity(0, "dive", 1) > Flight.next_velocity(0, "glide", 1) * 4, "Dive must fall much faster")
	game.marker_color = Color.GREEN
	game.hue_tolerance = 15
	game.shade_tolerance = 160
	game.min_dot_area = 30
	check(game.hue_preview_query() == "?color=%2300ff00&hue_tolerance=15&shade_tolerance=160&min_dot_area=30", "Preview URL must encode the color without interpreting percent as formatting")
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
	check(game.screen == "results", "Cloud contact ends run")
	game.start_run()
	check(game.score == 0 and game.elapsed == 0 and game.obstacles.is_empty(), "Retry clears previous run")
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
