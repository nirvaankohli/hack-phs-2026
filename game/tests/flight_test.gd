extends SceneTree

func _initialize() -> void:
	var controller = load("res://flight_controller.gd").new()
	controller.update(0.016, 20.0)
	controller.update(0.016, 0.0)
	assert(controller.flap_count == 0, "Angle changes must not flap")
	controller.flap()
	assert(controller.vertical_speed < 0.0, "A flap must gain upward momentum")
	for i in range(120):
		controller.update(0.016, 0.0)
	assert(controller.flap_count == 1, "Holding neutral must not repeat flaps")
	controller.update(0.016, 20.0)
	controller.update(0.016, 0.0)
	assert(controller.flap_count == 1, "Angle changes must not repeat flaps")
	controller.reset()
	for i in range(120):
		controller.update(0.016, 20.0 + sin(i) * 2.0)
	assert(controller.flap_count == 0, "Jitter must not trigger a stroke")
	controller.reset()
	controller.update(0.016, 20.0)
	for i in range(50):
		controller.update(0.016, 19.0)
	controller.update(0.016, 0.0)
	assert(controller.flap_count == 0, "A slow pose change must not trigger a stroke")
	controller.reset()
	for i in range(40):
		controller.update(0.016, -45.0)
	assert(controller.forward_speed == 230.0 and controller.vertical_speed > 0.0)
	var dive_velocity: float = controller.vertical_speed
	controller.update(0.016, -20.0)
	controller.update(0.016, 0.0)
	assert(controller.vertical_speed == 0.0 and controller.vertical_speed < dive_velocity)
	controller.reset()
	controller.update(0.016, 0.0)
	assert(controller.vertical_speed == 0.0, "Neutral wings must fly level")
	controller.update(0.016, -22.0)
	assert(controller.vertical_speed > 20.0 and controller.vertical_speed < 30.0)
	controller.update(0.016, -60.0)
	assert(controller.vertical_speed == 70.0, "Steepest input must still descend gently")
	assert(controller.forward_speed == 230.0, "Lowering wings must not accelerate the world")
	controller.update(0.016, -30.0)
	var before_threshold: float = controller.vertical_speed
	controller.update(0.016, -31.0)
	assert(controller.vertical_speed - before_threshold < 4.0, "No dive speed cliff")
	controller.update(0.016, 0.0)
	assert(controller.vertical_speed == 0.0, "Leveling must stop descent immediately")
	var game = load("res://main.tscn").instantiate()
	var space := InputEventKey.new()
	space.keycode = KEY_SPACE
	space.pressed = true
	game._unhandled_key_input(space)
	assert(game.state == "playing" and game.flight.flap_count == 1)
	assert(game.flight.vertical_speed < 0.0)
	space.echo = true
	game._unhandled_key_input(space)
	assert(game.flight.flap_count == 1, "Holding Space must not repeat flaps")
	space.echo = false
	game.flight.update(0.33, 0.0)
	game._unhandled_key_input(space)
	assert(game.flight.flap_count == 2, "Space during play must flap")
	game.state = "paused"
	game.flight.cooldown = 0.0
	game._unhandled_key_input(space)
	assert(game.flight.flap_count == 2, "Space must not flap while paused")
	game.adjust_angle(0.5, -1.0)
	assert(game.flight_angle_degrees == -20.0)
	game.adjust_angle(0.5, 1.0)
	assert(game.flight_angle_degrees == 0.0)
	game.adjust_angle(2.0, 1.0)
	assert(game.flight_angle_degrees == 0.0)
	game.adjust_angle(3.0, -1.0)
	assert(game.flight_angle_degrees == -60.0)
	assert(game.flight.flap_count == 2)
	game.free()
	print("PASS: Space flap, arrow angles, limits, no angle flaps, dive, pull-up, pause")
	quit()
