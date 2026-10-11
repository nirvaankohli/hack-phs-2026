extends SceneTree
# Integration check against an already-connected local camera bridge.
func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var game = load("res://main.tscn").instantiate()
	game.testing = true
	root.add_child(game)
	game.set_process(false)
	game.camera_on = true
	game.show_wing_colors()
	for i in 100:
		game.poll_camera(0.05)
		await create_timer(0.05).timeout
		if game.preview.texture != null: break
	if game.preview.texture == null:
		push_error("Camera preview never received a texture: " + game.status_text)
		quit(1)
		return
	var first = game.preview.texture
	game.color_sliders["Hue"].value = 30
	for i in 100:
		game.poll_camera(0.05)
		await create_timer(0.05).timeout
		if game.preview.texture != first: break
	if game.preview.texture == first:
		push_error("Camera preview stopped updating after a slider change")
		quit(1)
		return
	print("LIVE CAMERA PREVIEW: PASS (decoded texture, continued frames after hue adjustment)")
	quit()
