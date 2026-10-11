extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var request := HTTPRequest.new()
	request.timeout = 25
	root.add_child(request)
	request.request("http://127.0.0.1:8002/health")
	var health: Array = await request.request_completed
	if health[1] != 200:
		push_error("Bridge health failed")
		quit(1)
		return
	request.request("http://127.0.0.1:8002/camera/state")
	var state: Array = await request.request_completed
	if state[1] != 200:
		push_error("Flight state endpoint failed")
		quit(1)
		return
	var boundary := "cloudbound-test-boundary"
	var image_path := ProjectSettings.globalize_path("res://") + "../face/test_photos/photo_001.png"
	var content := ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"portrait.png\"\r\nContent-Type: image/png\r\n\r\n").to_utf8_buffer()
	content.append_array(FileAccess.get_file_as_bytes(image_path))
	content.append_array(("\r\n--" + boundary + "--\r\n").to_utf8_buffer())
	request.request_raw("http://127.0.0.1:8002/face/crop", ["Content-Type: multipart/form-data; boundary=" + boundary], HTTPClient.METHOD_POST, content)
	var crop: Array = await request.request_completed
	var image := Image.new()
	if crop[1] != 200 or image.load_png_from_buffer(crop[3]) != OK:
		push_error("Real face crop request failed: " + str(crop[1]))
		quit(1)
		return
	var game = load("res://main.tscn").instantiate()
	game.testing = true
	root.add_child(game)
	game.face = ImageTexture.create_from_image(image)
	game.show_setup()
	game.set_process(false)
	await process_frame
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("/tmp/cloudbound-real-face.png")
	print("GODOT API INTEGRATION: PASS (health, state, real face PNG, winged portrait)")
	quit()
