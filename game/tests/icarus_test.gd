extends SceneTree

func _initialize() -> void:
	var controller = load("res://flight_controller.gd").new()
	controller.update_heat(2.0, 0.65, false)
	assert(controller.heat == 0.0)
	controller.update_heat(10.0, 1.0, false)
	assert(is_equal_approx(controller.heat, 0.95))
	controller.heat = 1.0
	controller.update_heat(3.0, 1.0, true)
	assert(controller.heat == 0.0, "Three seconds in a cloud fully restores wings")
	controller.flap()
	var cold_lift: float = controller.flap_lift
	controller.reset()
	controller.heat = 1.0
	controller.flap()
	assert(controller.flap_lift < cold_lift)
	for i in range(120):
		controller.update(1.0 / 60.0, 0.0)
		if controller.cooldown <= 0.0:
			controller.flap()
	assert(controller.vertical_speed < 0.0, "Repeated flaps can save fully overheated wings")
	controller.update_heat(1.0, 0.4, false)
	assert(controller.heat < 1.0)
	var game = load("res://icarus.tscn").instantiate()
	game.start_run()
	game.player_y = game.SKY_TOP
	game.update_rewards(1.0)
	assert(is_equal_approx(game.score, 10.0))
	game.flight.heat = 0.8
	game.update_rewards(0.0)
	game.flight.heat = 0.2
	game.in_cloud = false
	game.update_rewards(0.0)
	assert(game.recovery_count == 0, "Bonus requires cooling inside a cloud")
	game.in_cloud = true
	game.update_rewards(0.0)
	assert(game.recovery_count == 1 and game.score == 110.0)
	game.update_rewards(0.0)
	assert(game.recovery_count == 1, "Cloud camping cannot repeat a bonus")
	game.flight.heat = 0.8
	game.update_rewards(0.0)
	game.flight.heat = 0.2
	game.update_rewards(0.0)
	assert(game.recovery_count == 2)
	game.state = "paused"
	var frozen_score: float = game.score
	var frozen_cloud: float = game.clouds[0]["x"]
	game._physics_process(1.0)
	assert(game.score == frozen_score and game.elapsed == 0.0)
	assert(game.clouds[0]["x"] == frozen_cloud and game.flight.heat == 0.2)
	game.finish_run()
	assert(game.best == 210)
	game.start_run()
	assert(game.score == 0.0 and game.flight.heat == 0.0 and game.best == 210)
	assert(game.recovery_count == 0 and not game.recovery_armed)
	assert(game.trail.is_empty() and game.particles.is_empty())
	var encountered := false
	for i in range(600):
		game._physics_process(1.0 / 60.0)
		encountered = encountered or game.in_cloud
	assert(encountered, "First cloud is reachable within ten seconds")
	game.player_y = game.SKY_TOP - 20.0
	game._physics_process(1.0 / 60.0)
	assert(game.player_y >= game.SKY_TOP and game.state == "playing")
	game.player_y = game.SEA_Y
	game._physics_process(1.0 / 60.0)
	assert(game.state == "over", "Sea collision ends the run")
	game.free()
	print("PASS: heat, lift, recovery, scoring, bonus cycles, pause, retry, clouds, sea")
	quit()
