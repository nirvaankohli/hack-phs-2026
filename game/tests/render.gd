extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func shot(path: String) -> void:
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(path)

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	game.testing = true
	root.add_child(game)
	game.muted = true
	game.control_mode = "keyboard"
	game.set_process(false)
	await shot("/tmp/cloudbound-home.png")
	game.show_setup()
	await shot("/tmp/cloudbound-setup.png")
	var camera_test := Image.create(400, 300, false, Image.FORMAT_RGB8)
	camera_test.fill(Color("467a91"))
	game.preview.texture = ImageTexture.create_from_image(camera_test)
	await shot("/tmp/cloudbound-camera-mask.png")
	game.show_settings("home")
	await shot("/tmp/cloudbound-settings.png")
	game.show_wing_colors()
	game.on_hues(0, 200, PackedStringArray(), '{"colors":[{"color":"#00FF00","percent":32.5},{"color":"#FF2020","percent":21.0},{"color":"#2060FF","percent":12.0}]}'.to_utf8_buffer())
	await shot("/tmp/cloudbound-wing-colors.png")
	game.camera_on = true
	game.start_run()
	game.preview.texture = ImageTexture.create_from_image(camera_test)
	game.countdown = 0
	game.elapsed = 30
	for i in 6:
		game.spawn_hazard()
		game.obstacles[i].x = 530 + (i % 3) * 230
		game.obstacles[i].y = 230 + (i / 3) * 260
		if i > 0:
			game.obstacles[i].kind = "bird"
			game.obstacles[i].species = i - 1
	game.pickups.clear()
	game.pickups.append({"x": 425.0, "y": 375.0})
	game.avatar_y = 330
	game.queue_redraw()
	await shot("/tmp/cloudbound-flight.png")
	game.countdown = 2.0
	game.queue_redraw()
	await shot("/tmp/cloudbound-countdown.png")
	game.finish(true)
	game.queue_redraw()
	await shot("/tmp/cloudbound-results.png")
	quit()
