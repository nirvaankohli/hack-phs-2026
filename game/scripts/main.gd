extends Node2D

const Flight = preload("res://scripts/flight.gd")
const Assets = preload("res://scripts/supplied_assets.gd")
const PIXEL_FONT = preload("res://assets/fonts/PixelifySans.ttf")
const SKY = preload("res://assets/sky.png")
const INK = Color("183e55")
const CREAM = Color("fff8e6")
const GOLD = Color("ffd16c")
const TEAL = Color("267f89")
const VIOLET = Color("595878")
const DURATION = 60.0

var screen := "home"
var previous_screen := "home"
var control_mode := "keyboard"
var muted := false
var reduced_motion := false
var api_url := "http://127.0.0.1:8002"
var best := 0
var clock := 0.0
var sky_scroll := 0.0
var sky_material: ShaderMaterial
var elapsed := 0.0
var avatar_y := 330.0
var velocity := 0.0
var flight_state := "glide"
var score := 0
var coins := 0
var hearts := 3
var hit_protection := 0.0
var countdown := 0.0
var spawn_timer := 0.0
var hazard_index := 0
var bird_bag: Array[int] = []
var obstacles: Array[Dictionary] = []
var pickups: Array[Dictionary] = []
var particles: Array[Dictionary] = []
var face: Texture2D
var camera_image: Texture2D
var tracked_state := "lost"
var tracking_ok := false
var calibrated := false
var last_tracking := -100.0
var poll_timer := 0.0
var preview_timer := 0.0
var camera_on := false
var capture_busy := false
var ui: Control
var status_label: Label
var preview: TextureRect
var flight_camera_label: Label
var marker_color := Color.GREEN
var second_marker_color := Color.RED
var second_color_enabled := false
var editing_color_slot := 0
var dropper_active := false
var dropper_image: Image
var dropper_button: Button
var hue_swatch: ColorRect
var hue_label: Label
var color_sliders: Dictionary = {}
var color_readouts: Dictionary = {}
var hue_tolerance := 15
var shade_tolerance := 160
var min_dot_area := 30
var preview_color := ""
var preview_screen := ""
var state_request: HTTPRequest
var preview_request: HTTPRequest
var action_request: HTTPRequest
var action_kind := ""
var status_text := "Your camera stays on this computer."
var sound: AudioStreamPlayer
var last_flap_sound := 0.0
var rng := RandomNumberGenerator.new()
var title_font: Font
var body_font: Font
var sprites: SuppliedAssets
var ui_theme: Theme
var touch_flap := false
var testing := false
var lost_pause := false
var run_won := false

func _ready() -> void:
	rng.seed = 2026
	title_font = PIXEL_FONT
	body_font = PIXEL_FONT
	sprites = Assets.new()
	load_settings()
	make_theme()
	var sky_layer := Sprite2D.new()
	sky_layer.texture = SKY
	sky_layer.centered = false
	var sky_scale := maxf(1280.0 / SKY.get_width(), 720.0 / SKY.get_height())
	sky_layer.scale = Vector2.ONE * sky_scale
	sky_layer.position = (Vector2(1280, 720) - SKY.get_size() * sky_scale) / 2.0
	sky_layer.z_index = -10
	sky_material = ShaderMaterial.new()
	sky_material.shader = preload("res://scripts/sky_parallax.gdshader")
	sky_layer.material = sky_material
	add_child(sky_layer)
	ui = Control.new()
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(ui)
	sound = AudioStreamPlayer.new()
	add_child(sound)
	state_request = HTTPRequest.new()
	state_request.timeout = 2.0
	add_child(state_request)
	state_request.request_completed.connect(on_state)
	preview_request = HTTPRequest.new()
	preview_request.timeout = 2.0
	add_child(preview_request)
	preview_request.request_completed.connect(on_preview)
	action_request = HTTPRequest.new()
	action_request.timeout = 20.0
	add_child(action_request)
	action_request.request_completed.connect(on_action)
	get_tree().auto_accept_quit = false
	show_home()

func style(color: Color, border: Color = Color.TRANSPARENT) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = color
	s.set_corner_radius_all(0)
	s.set_border_width_all(3)
	s.border_color = border
	s.content_margin_left = 22
	s.content_margin_right = 22
	s.content_margin_top = 12
	s.content_margin_bottom = 12
	return s

func make_theme() -> void:
	ui_theme = Theme.new()
	ui_theme.default_font = body_font
	ui_theme.default_font_size = 22
	ui_theme.set_stylebox("normal", "Button", style(CREAM, Color("c6dbd7")))
	ui_theme.set_stylebox("hover", "Button", style(Color("ffe8a6"), INK))
	ui_theme.set_stylebox("pressed", "Button", style(GOLD, INK))
	ui_theme.set_stylebox("focus", "Button", style(Color.TRANSPARENT, TEAL))
	ui_theme.set_stylebox("disabled", "Button", style(Color("d8e3dc")))
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		ui_theme.set_color(state, "Button", INK)
	ui_theme.set_color("font_color", "Label", INK)
	ui_theme.set_stylebox("normal", "LineEdit", style(CREAM, Color("a6c6cd")))
	ui_theme.set_stylebox("focus", "LineEdit", style(CREAM, TEAL))
	ui_theme.set_color("font_color", "LineEdit", INK)
	ui_theme.set_color("caret_color", "LineEdit", INK)

func clear_ui() -> void:
	queue_redraw()
	touch_flap = false
	for child in ui.get_children():
		ui.remove_child(child)
		child.queue_free()
	hue_swatch = null
	hue_label = null
	color_sliders.clear()
	color_readouts.clear()
	status_label = null
	preview = null
	dropper_active = false
	dropper_image = null
	dropper_button = null
	flight_camera_label = null

func label(text: String, pos: Vector2, font_size: int = 20, color: Color = INK, width: float = 600.0, bold: bool = false) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	l.size.x = width
	l.add_theme_font_override("font", title_font if bold else body_font)
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(l)
	return l

func button(text: String, rect: Rect2, callback: Callable, primary: bool = false) -> Button:
	var b := Button.new()
	b.text = text
	b.position = rect.position
	b.size = rect.size
	b.theme = ui_theme
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	if primary:
		b.add_theme_stylebox_override("normal", style(GOLD, Color("e2af4b")))
	b.pressed.connect(func():
		chirp(540, 0.06)
		callback.call())
	ui.add_child(b)
	return b

func panel(rect: Rect2) -> void:
	var p := Panel.new()
	p.position = rect.position
	p.size = rect.size
	var s := style(CREAM, Color("b3d7dc"))
	s.shadow_color = Color(0.09, 0.24, 0.31, 0.12)
	s.shadow_size = 14
	s.shadow_offset = Vector2(0, 8)
	p.add_theme_stylebox_override("panel", s)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(p)

func show_home() -> void:
	screen = "home"
	clear_ui()
	var heading := label("CLOUDBOUND", Vector2(0, 171), 112, INK, 1280, true)
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_color_override("font_shadow_color", CREAM)
	heading.add_theme_constant_override("shadow_offset_x", 5)
	heading.add_theme_constant_override("shadow_offset_y", 5)
	var play := button("Play", Rect2(465, 345, 350, 76), show_setup, true)
	play.add_theme_font_size_override("font_size", 36)
	play.grab_focus()
	var settings := button("Settings", Rect2(465, 439, 350, 68), func(): show_settings("home"))
	settings.add_theme_font_size_override("font_size", 30)

func show_setup() -> void:
	screen = "setup"
	clear_ui()
	panel(Rect2(58, 46, 1164, 624))
	label("YOUR FLIGHT PORTRAIT", Vector2(92, 73), 14, TEAL, 550, true)
	label("Choose your face", Vector2(90, 103), 42, INK, 900, true)
	label("Capture a photo to use as your character.", Vector2(92, 166), 20)
	var camera_back := Panel.new()
	camera_back.position = Vector2(142, 227)
	camera_back.size = Vector2(400, 300)
	var camera_style := style(Color("d6ebea"), Color("a3c8cd"))
	camera_style.set_corner_radius_all(18)
	camera_back.add_theme_stylebox_override("panel", camera_style)
	ui.add_child(camera_back)
	label("Camera preview", Vector2(237, 355), 22, TEAL, 340, true)
	label("Enable camera to capture your face.", Vector2(164, 391), 16, INK, 460)
	preview = TextureRect.new()
	preview.position = Vector2(142, 227)
	preview.size = Vector2(400, 300)
	preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var camera_material := ShaderMaterial.new()
	camera_material.shader = preload("res://scripts/camera_frame.gdshader")
	preview.material = camera_material
	preview.texture = camera_image
	ui.add_child(preview)
	label("01   FRAME YOUR FACE", Vector2(92, 538), 13, TEAL, 500, true)
	add_portrait(Vector2(876, 353), 1.3)
	label("02   READY FOR TAKEOFF", Vector2(718, 449), 13, TEAL, 400, true)
	label("Flap to rise.\nGlide or dive to descend.", Vector2(718, 476), 19, INK, 440)
	button("Enable camera" if not camera_on else "Refresh camera", Rect2(92, 579, 192, 49), enable_camera)
	button("Capture face", Rect2(300, 579, 190, 49), capture_face, true)
	button("Take flight   >", Rect2(718, 570, 250, 58), start_run, true)
	button("Back", Rect2(990, 576, 120, 49), show_home)
	status_label = label(status_text, Vector2(92, 193), 14, TEAL, 1020)
	button("Controls & calibration", Rect2(718, 215, 318, 45), func(): show_settings("setup"))

func show_settings(from: String) -> void:
	previous_screen = from
	screen = "settings"
	clear_ui()
	panel(Rect2(202, 38, 876, 646))
	label("FLIGHT DECK", Vector2(244, 62), 14, TEAL, 700, true)
	label("Settings", Vector2(242, 91), 35, INK, 790, true)
	label("CONTROLS", Vector2(246, 154), 13, TEAL, 700, true)
	button(("> " if control_mode == "keyboard" else "") + "Keyboard", Rect2(246, 182, 238, 52), func(): set_control("keyboard"), control_mode == "keyboard")
	button(("> " if control_mode == "wings" else "") + "Physical wings", Rect2(498, 182, 282, 52), func(): set_control("wings"), control_mode == "wings")
	label("SPACE / UP   Flap       RELEASE   Glide       DOWN / S   Dive", Vector2(246, 250), 18, INK, 800)
	label("Move both wings: flap. Near center: glide. Both below center: dive.", Vector2(246, 280), 17, INK, 800)
	label("LOCAL CAMERA BRIDGE", Vector2(246, 331), 13, TEAL, 700, true)
	var field := LineEdit.new()
	field.position = Vector2(246, 359)
	field.size = Vector2(482, 48)
	field.text = api_url
	field.theme = ui_theme
	field.placeholder_text = "http://127.0.0.1:8002"
	field.text_changed.connect(func(value): api_url = value.strip_edges().trim_suffix("/"))
	ui.add_child(field)
	button("Connect", Rect2(744, 359, 286, 48), enable_camera)
	button("Calibrate spread wings", Rect2(246, 420, 306, 48), calibrate_wings)
	label("Hold all 3 markers in view, wings open.", Vector2(570, 431), 16, INK, 450)
	button("Sound: " + ("off" if muted else "on"), Rect2(246, 497, 240, 48), func(): muted = not muted; save_settings(); show_settings(previous_screen))
	button("Ambient motion: " + ("reduced" if reduced_motion else "on"), Rect2(502, 497, 344, 48), func(): reduced_motion = not reduced_motion; save_settings(); show_settings(previous_screen))
	button("Wing color", Rect2(862, 497, 168, 48), show_wing_colors)
	status_label = label(status_text, Vector2(246, 558), 14, TEAL, 786)
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	button("Done   >", Rect2(820, 612, 210, 47), close_settings, true)

func show_wing_colors() -> void:
	screen = "wing_colors"
	clear_ui()
	panel(Rect2(100, 20, 1080, 684))
	label("WING DOT TRACKING", Vector2(144, 48), 14, TEAL)
	label("Choose your wing color", Vector2(144, 78), 34)
	button("Color 1", Rect2(144, 116, 204, 44), func(): editing_color_slot = 0; show_wing_colors(), editing_color_slot == 0)
	button("Color 2", Rect2(368, 116, 204, 44), func(): editing_color_slot = 1; second_color_enabled = true; show_wing_colors(), editing_color_slot == 1)
	button("Two colors: " + ("ON" if second_color_enabled else "OFF"), Rect2(680, 116, 300, 44), func(): second_color_enabled = not second_color_enabled; show_wing_colors())
	panel(Rect2(144, 174, 480, 360))
	label("Connect camera to preview", Vector2(174, 337), 20, TEAL, 420, true)
	preview = TextureRect.new()
	preview.position = Vector2(144, 174)
	preview.size = Vector2(480, 360)
	preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var camera_material := ShaderMaterial.new()
	camera_material.shader = preload("res://scripts/camera_frame.gdshader")
	camera_material.set_shader_parameter("frame_size", Vector2(480, 360))
	preview.material = camera_material
	ui.add_child(preview)
	label("The 3 largest matches stay bright and outlined.", Vector2(144, 548), 16, TEAL, 800)
	hue_label = label("", Vector2(680, 174), 18, INK, 300)
	hue_swatch = ColorRect.new()
	hue_swatch.position = Vector2(1092, 175)
	hue_swatch.size = Vector2(44, 20)
	ui.add_child(hue_swatch)
	add_color_slider("Hue", 212, 359, roundi(editing_marker_color().h * 360))
	add_color_slider("Saturation", 260, 100, roundi(editing_marker_color().s * 100))
	add_color_slider("Brightness", 308, 100, roundi(editing_marker_color().v * 100))
	add_color_slider("Hue tolerance", 356, 90, hue_tolerance)
	add_color_slider("Shade tolerance", 404, 255, shade_tolerance)
	add_color_slider("Minimum dot size", 452, 100000, min_dot_area)
	button("Apply", Rect2(680, 518, 214, 48), apply_marker_color, true)
	button("Connect", Rect2(922, 518, 214, 48), enable_camera)
	dropper_button = button("Pick from camera", Rect2(144, 592, 312, 48), toggle_dropper, true)
	label("Select Color 1 or 2, then pick its dot in the camera.", Vector2(484, 596), 18, INK, 650)
	label("The picker samples the original image. Apply when ready.", Vector2(484, 624), 15, TEAL, 650)
	preview.gui_input.connect(on_dropper_input)
	status_label = label("Connect the camera to pick a color.", Vector2(144, 670), 14, TEAL, 960)
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	button("Back", Rect2(966, 48, 170, 48), func(): show_settings(previous_screen))
	preview_timer = 0
	update_hue_preview()

func editing_marker_color() -> Color:
	return second_marker_color if editing_color_slot == 1 else marker_color

func set_editing_marker_color(value: Color) -> void:
	if editing_color_slot == 1: second_marker_color = value
	else: marker_color = value

func add_color_slider(title: String, y: float, maximum: int, value: int) -> void:
	var readout := label("", Vector2(680, y), 17, INK, 456)
	var slider := HSlider.new()
	slider.position = Vector2(680, y + 23)
	slider.size = Vector2(456, 24)
	slider.max_value = maximum
	slider.step = 1
	if title == "Minimum dot size":
		slider.min_value = 1
		slider.exp_edit = true
	slider.value = value
	slider.theme = ui_theme
	color_sliders[title] = slider
	color_readouts[title] = readout
	slider.value_changed.connect(func(_value):
		set_editing_marker_color(Color.from_hsv(color_sliders["Hue"].value / 360.0, color_sliders["Saturation"].value / 100.0, color_sliders["Brightness"].value / 100.0))
		hue_tolerance = int(color_sliders["Hue tolerance"].value)
		shade_tolerance = int(color_sliders["Shade tolerance"].value)
		min_dot_area = int(color_sliders["Minimum dot size"].value)
		update_hue_preview())
	ui.add_child(slider)

func update_hue_preview() -> void:
	preview_timer = 0
	for title in color_sliders:
		var suffix := "%" if title in ["Saturation", "Brightness"] else ""
		if title == "Minimum dot size": suffix = " px²"
		color_readouts[title].text = "%s   %d%s" % [title, color_sliders[title].value, suffix]
	if is_instance_valid(hue_swatch): hue_swatch.color = editing_marker_color()
	if is_instance_valid(hue_label): hue_label.text = "COLOR %d  #%s" % [editing_color_slot + 1, editing_marker_color().to_html(false).to_upper()]

func hue_preview_query() -> String:
	if dropper_active: return ""
	var query := "?color=%%23%s&hue_tolerance=%d&shade_tolerance=%d&min_dot_area=%d" % [marker_color.to_html(false), hue_tolerance, shade_tolerance, min_dot_area]
	if second_color_enabled: query += "&second_color=%23" + second_marker_color.to_html(false)
	return query

func toggle_dropper() -> void:
	dropper_active = not dropper_active
	dropper_image = null
	preview_timer = 0
	preview.mouse_default_cursor_shape = Control.CURSOR_CROSS if dropper_active else Control.CURSOR_ARROW
	dropper_button.text = "Cancel picker" if dropper_active else "Pick from camera"
	set_status("Click the wing dot to sample Color %d." % (editing_color_slot + 1) if dropper_active else "Adjust the sliders, then Apply.")

func on_dropper_input(event: InputEvent) -> void:
	if not dropper_active or dropper_image == null: return
	if not event is InputEventMouseButton or event.button_index != MOUSE_BUTTON_LEFT or not event.pressed: return
	var image_size := Vector2(dropper_image.get_size())
	var scale_v := minf(preview.size.x / image_size.x, preview.size.y / image_size.y)
	var displayed := image_size * scale_v
	var point: Vector2 = (event.position - (preview.size - displayed) * 0.5) / scale_v
	if point.x < 0 or point.y < 0 or point.x >= image_size.x or point.y >= image_size.y: return
	# Median of a 5x5 patch reduces camera noise without sampling the overlay.
	var reds: Array[float] = []
	var greens: Array[float] = []
	var blues: Array[float] = []
	for y in range(maxi(0, int(point.y) - 2), mini(dropper_image.get_height(), int(point.y) + 3)):
		for x in range(maxi(0, int(point.x) - 2), mini(dropper_image.get_width(), int(point.x) + 3)):
			var pixel := dropper_image.get_pixel(x, y)
			reds.append(pixel.r)
			greens.append(pixel.g)
			blues.append(pixel.b)
	reds.sort()
	greens.sort()
	blues.sort()
	var middle := int(reds.size() / 2)
	set_editing_marker_color(Color(reds[middle], greens[middle], blues[middle]))
	color_sliders["Hue"].set_value_no_signal(roundi(editing_marker_color().h * 360))
	color_sliders["Saturation"].set_value_no_signal(roundi(editing_marker_color().s * 100))
	color_sliders["Brightness"].set_value_no_signal(roundi(editing_marker_color().v * 100))
	toggle_dropper()
	update_hue_preview()
	set_status("Color %d sampled. Check the highlighted dots, then Apply." % (editing_color_slot + 1))
	preview.accept_event()

func apply_marker_color() -> void:
	send_action("color", "/camera/settings", JSON.stringify({"color": "#" + marker_color.to_html(false), "hue_tolerance": hue_tolerance, "shade_tolerance": shade_tolerance, "min_dot_area": min_dot_area, "second_color": "#" + second_marker_color.to_html(false) if second_color_enabled else null}))

func set_control(value: String) -> void:
	control_mode = value
	save_settings()
	show_settings(previous_screen)

func close_settings() -> void:
	save_settings()
	if previous_screen == "setup": show_setup()
	elif previous_screen == "pause": show_pause(false)
	else: show_home()

func start_run() -> void:
	if control_mode == "wings" and (not tracking_ok or not calibrated or clock - last_tracking > 0.6):
		status_text = "Connect the camera and calibrate your spread wings before takeoff."
		show_settings("setup")
		return
	clear_ui()
	screen = "play"
	elapsed = 0
	avatar_y = 330
	velocity = 0
	score = 0
	coins = 0
	hearts = 3
	hit_protection = 0.0
	hazard_index = 0
	bird_bag.clear()
	spawn_timer = 1.8
	countdown = 3.0
	obstacles.clear()
	pickups.clear()
	particles.clear()
	rng.seed = 2026
	flight_state = "glide"
	lost_pause = false
	add_pause_button()
	add_flight_camera()

func show_pause(tracking_lost: bool) -> void:
	screen = "pause"
	lost_pause = tracking_lost
	clear_ui()
	panel(Rect2(380, 162, 520, 401))
	label("CLOUDBOUND", Vector2(419, 190), 13, TEAL, 470, true)
	label("Wings can't be seen" if tracking_lost else "Paused", Vector2(417, 225), 34, INK, 480, true)
	label("Restore tracking or switch to keyboard." if tracking_lost else "Resume when you are ready.", Vector2(419, 287), 18, INK, 450)
	button("Resume flight   >", Rect2(420, 340, 440, 55), resume_run, true).grab_focus()
	button("Settings", Rect2(420, 410, 211, 48), func(): show_settings("pause"))
	button("End flight", Rect2(648, 410, 212, 48), show_home)
	status_label = label("", Vector2(420, 485), 15, TEAL, 435)
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_flight_camera()

func resume_run() -> void:
	if control_mode == "wings" and (not tracking_ok or not calibrated or clock - last_tracking > 0.6):
		status_label.text = "Still waiting for calibrated wings. Settings has keyboard mode."
		return
	screen = "play"
	clear_ui()
	countdown = 2.0
	add_pause_button()
	add_flight_camera()

func finish(won: bool) -> void:
	screen = "results"
	run_won = won
	if won: score += 100
	best = maxi(best, score)
	save_settings()
	clear_ui()
	panel(Rect2(345, 87, 590, 550))
	label("FLIGHT COMPLETE" if won else "FLIGHT ENDED", Vector2(391, 116), 13, TEAL, 520, true)
	label("You earned your wings." if won else "Game over", Vector2(389, 150), 35, INK, 540, true)
	label("%04d" % score, Vector2(391, 225), 72, INK, 440, true)
	add_portrait(Vector2(801, 281), 0.92)
	label("FLIGHT SCORE", Vector2(394, 320), 13, TEAL, 400, true)
	label("%d coins     /     %ds in the sky     /     Best %d" % [coins, int(elapsed), best], Vector2(393, 386), 17, INK, 530)
	button("Fly again   >", Rect2(391, 445, 497, 59), start_run, true).grab_focus()
	button("New face", Rect2(391, 520, 239, 49), show_setup)
	button("Home", Rect2(648, 520, 240, 49), show_home)
	chirp(780 if won else 180, 0.25)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			if screen == "play": show_pause(false)
			elif screen == "pause": resume_run()
			elif screen == "settings": close_settings()
			elif screen == "wing_colors": show_settings(previous_screen)
			elif screen != "home": show_home()
			get_viewport().set_input_as_handled()
	if event is InputEventScreenTouch:
		touch_flap = event.pressed
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		touch_flap = event.pressed

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and screen == "play": show_pause(false)
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		if camera_on:
			action_request.cancel_request()
			action_request.request(api_url + "/camera/stop", [], HTTPClient.METHOD_POST)
			await get_tree().create_timer(0.2).timeout
		get_tree().quit()

func _process(delta: float) -> void:
	clock += delta
	update_parallax(delta)
	poll_camera(delta)
	if screen == "play":
		if control_mode == "wings" and (not tracking_ok or clock - last_tracking > 0.65):
			show_pause(true)
		elif countdown > 0:
			countdown = maxf(0, countdown - delta)
		else:
			step_game(minf(delta, 0.05))
	for i in range(particles.size() - 1, -1, -1):
		particles[i].life -= delta
		particles[i].p += particles[i].v * delta
		if particles[i].life <= 0: particles.remove_at(i)
	queue_redraw()

func step_game(delta: float) -> void:
	hit_protection = maxf(0.0, hit_protection - delta)
	elapsed += delta
	if control_mode == "keyboard":
		if Input.is_physical_key_pressed(KEY_DOWN) or Input.is_physical_key_pressed(KEY_S): flight_state = "dive"
		elif Input.is_physical_key_pressed(KEY_SPACE) or Input.is_physical_key_pressed(KEY_UP) or Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) or touch_flap: flight_state = "flap"
		else: flight_state = "glide"
	else:
		flight_state = tracked_state
	velocity = Flight.next_velocity(velocity, flight_state, delta)
	avatar_y += velocity * delta
	if avatar_y < 104:
		avatar_y = 104
		velocity = maxf(velocity, 0)
	if avatar_y > 660:
		take_hit()
		if screen == "play":
			avatar_y = 330
			velocity = 0
		return
	if flight_state == "flap" and clock - last_flap_sound > 0.34:
		last_flap_sound = clock
		chirp(350, 0.045, 0.035)
		burst(Vector2(276, avatar_y + 15), 2)
	var speed := hazard_speed()
	spawn_timer -= delta
	if spawn_timer <= 0 and elapsed < 57:
		spawn_hazard()
		spawn_timer = spawn_interval()
	for i in range(obstacles.size() - 1, -1, -1):
		var o: Dictionary = obstacles[i]
		o.x -= (speed + o.extra_speed) * delta
		o.y = o.base_y + sin(elapsed * o.frequency + o.phase) * o.amplitude
		if not o.passed and o.x + o.radius.x < 278:
			o.passed = true
			score += 10
		var separation: Vector2 = (Vector2(300, avatar_y) - Vector2(o.x, o.y)) / (o.radius + Vector2(20, 20))
		if separation.length_squared() < 1.0 and hit_protection <= 0:
			obstacles.remove_at(i)
			take_hit()
			return
		if o.x < -180: obstacles.remove_at(i)
	for i in range(pickups.size() - 1, -1, -1):
		pickups[i].x -= speed * delta
		var p := Vector2(pickups[i].x, pickups[i].y)
		if p.distance_to(Vector2(300, avatar_y)) < 42:
			score += 5
			coins += 1
			burst(p, 9)
			chirp(960, 0.1)
			pickups.remove_at(i)
		elif p.x < -40: pickups.remove_at(i)
	if elapsed >= DURATION: finish(true)

func take_hit() -> void:
	if hit_protection > 0 or screen != "play": return
	hearts = maxi(0, hearts - 1)
	burst(Vector2(300, avatar_y), 24)
	chirp(140, 0.16)
	if hearts == 0:
		finish(false)
	else:
		hit_protection = 1.5

func hazard_speed() -> float:
	return 300.0 + minf(elapsed, 60.0) * 2.4

func spawn_interval() -> float:
	return lerpf(1.45, 0.85, minf(elapsed / 50.0, 1.0))

func next_bird() -> int:
	if bird_bag.is_empty():
		bird_bag.assign([0, 1, 2, 3, 4])
		for i in range(4, 0, -1):
			var j := rng.randi_range(0, i)
			var swap := bird_bag[i]
			bird_bag[i] = bird_bag[j]
			bird_bag[j] = swap
	return bird_bag.pop_back()

func spawn_hazard() -> void:
	# Separate moving silhouettes, with open air above and below every hazard.
	var lanes := [330.0, 160.0, 490.0, 250.0, 570.0, 390.0, 180.0, 470.0, 300.0, 600.0]
	var y: float = lanes[hazard_index % lanes.size()]
	var is_cloud := hazard_index % 3 == 0
	var species := -1 if is_cloud else next_bird()
	var radius := Vector2(73, 37) if is_cloud else (Vector2(59, 29) if species == 2 else Vector2(34, 25))
	obstacles.append({"kind": "cloud" if is_cloud else "bird", "x": 1380.0,
		"y": y, "base_y": y, "species": species, "passed": false, "radius": radius,
		"extra_speed": 0.0 if is_cloud else 45.0, "frequency": 1.3 if is_cloud else 2.7,
		"amplitude": 14.0 if is_cloud else 27.0, "phase": float(hazard_index) * 1.7})
	if hazard_index % 2 == 0:
		pickups.append({"x": 1380.0, "y": y + (120 if y < 390 else -120)})
	hazard_index += 1

func burst(pos: Vector2, count: int) -> void:
	for i in count:
		particles.append({"p": pos, "v": Vector2(rng.randf_range(-90, 75), rng.randf_range(-80, 90)), "life": rng.randf_range(0.3, 0.8)})

func update_parallax(delta: float) -> void:
	sky_material.set_shader_parameter("motion_amount", 0.0 if reduced_motion else 1.0)
	if reduced_motion: return
	if screen == "home":
		sky_scroll += delta * 18.0 / 1280.0
	elif screen == "play" and countdown <= 0:
		sky_scroll += delta * 32.0 / 1280.0
	else:
		return # Freeze the backdrop on pause and in setup/settings.
	sky_scroll = fposmod(sky_scroll, 0.88)
	sky_material.set_shader_parameter("scroll", sky_scroll)

func _draw() -> void:
	var storm := clampf((elapsed - 23) / 17, 0, 1) if screen in ["play", "pause", "results"] else 0.0
	if elapsed > 45: storm *= clampf((58 - elapsed) / 13, 0, 1)
	draw_rect(Rect2(0, 0, 1280, 720), Color(0.38, 0.32, 0.55, storm * 0.25))
	if screen in ["play", "pause", "results"] and elapsed > 45:
		draw_rect(Rect2(0, 0, 1280, 720), Color(1.0, 0.77, 0.39, clampf((elapsed - 45) / 15, 0, 1) * 0.22))
	draw_sun(Vector2(1148, 190 if screen in ["play", "pause", "results"] else 142), 0.82)
	if screen == "home":
		pass
	elif screen == "setup":
		# Avatar is rendered by a foreground canvas so it appears above the panel.
		pass
	elif screen in ["play", "pause", "results"] or (screen == "settings" and previous_screen == "pause"):
		for o in obstacles:
			if o.kind == "cloud":
				draw_texture_rect(sprites.storm_cloud, Rect2(Vector2(o.x, o.y) - Vector2(86, 49), Vector2(172, 98)), false)
			else: draw_bird(Vector2(o.x, o.y), clock + o.phase, o.species)
		for p in pickups: draw_coin(Vector2(p.x, p.y), 44.0)
		if hit_protection <= 0 or reduced_motion or int(hit_protection * 10) % 2 == 0:
			draw_avatar(Vector2(300, avatar_y), 0.83, flight_state)
		for p in particles:
			draw_rect(Rect2(p.p, Vector2(5, 5)), Color(1, 0.9, 0.58, minf(p.life * 2, 1)))
		if screen == "play": draw_hud()
		if screen == "pause" or screen == "results": draw_rect(Rect2(0, 0, 1280, 720), Color(0.07, 0.19, 0.29, 0.23))
	if ui.has_node("PortraitOverlay"): ui.get_node("PortraitOverlay").queue_redraw()

func add_portrait(pos: Vector2, size_v: float) -> void:
	var overlay := Node2D.new()
	overlay.name = "PortraitOverlay"
	ui.add_child(overlay)
	overlay.draw.connect(func(): draw_portrait_on(overlay, pos, size_v))

func draw_sun(pos: Vector2, s: float) -> void:
	draw_texture_rect(sprites.sun, Rect2(pos - Vector2(87, 86) * s, Vector2(174, 172) * s), false)

func draw_avatar(pos: Vector2, s: float, mode: String) -> void:
	draw_avatar_on(self, pos, s, mode)

func draw_portrait_on(canvas: Node2D, pos: Vector2, s: float) -> void:
	draw_avatar_on(canvas, pos, s, "glide")

func draw_avatar_on(canvas: Node2D, pos: Vector2, s: float, mode: String) -> void:
	var tilt := -0.09 if mode == "flap" else (0.32 if mode == "dive" else 0.06)
	canvas.draw_set_transform(pos, tilt, Vector2(s, s))
	var frame := 0
	if mode == "flap": frame = [0, 1, 2, 3, 4, 5][int(clock * 13) % 6]
	elif mode == "dive": frame = 3
	var wings: Texture2D = sprites.wing_frames[frame]
	var half := wings.get_width() / 2.0
	var wing_height := wings.get_height() * 2.1
	var wing_width := half * 2.1
	canvas.draw_texture_rect_region(wings, Rect2(-12-wing_width, -25, wing_width, wing_height), Rect2(0, 0, half, wings.get_height()))
	canvas.draw_texture_rect_region(wings, Rect2(12, -25, wing_width, wing_height), Rect2(half, 0, half, wings.get_height()))
	if face:
		var size_v := face.get_size()
		var fit := 76.0 / maxf(size_v.x, size_v.y)
		canvas.draw_texture_rect(face, Rect2(-size_v * fit / 2, size_v * fit), false)
	else:
		canvas.draw_circle(Vector2.ZERO, 33, Color("d79155"))
		canvas.draw_circle(Vector2(0,-3), 30, Color("ffda91"))
		canvas.draw_rect(Rect2(-16,-8,6,10), INK)
		canvas.draw_rect(Rect2(10,-8,6,10), INK)
		canvas.draw_polyline(PackedVector2Array([Vector2(-9,9),Vector2(-5,14),Vector2(6,14),Vector2(11,9)]),INK,3)
		canvas.draw_rect(Rect2(-24,7,9,5),Color("eea279"))
		canvas.draw_rect(Rect2(17,7,9,5),Color("eea279"))
	canvas.draw_set_transform(pos + Vector2(0,-52*s), 0, Vector2(s,s*0.28))
	canvas.draw_arc(Vector2.ZERO, 23, 0, TAU, 32, GOLD, 7)
	canvas.draw_set_transform(Vector2.ZERO)

func draw_bird(pos: Vector2, time: float, species: int) -> void:
	var frames: Array = sprites.bird_species[species]
	var texture: Texture2D = frames[int(time * 9) % frames.size()]
	var width := 140.0 if species == 2 else 88.0
	var height := width * texture.get_height() / texture.get_width()
	draw_texture_rect(texture, Rect2(pos + Vector2(width / 2, -height / 2), Vector2(-width, height)), false)

func draw_coin(pos: Vector2, size_v: float = 40.0) -> void:
	var frame := int(clock * 10) % sprites.coin_frames.size()
	draw_texture_rect(sprites.coin_frames[frame], Rect2(pos - Vector2.ONE * size_v / 2, Vector2.ONE * size_v), false)

func hud_panel(rect: Rect2) -> void:
	var box := style(CREAM, Color("b0d2d8"))
	box.set_corner_radius_all(12)
	box.set_border_width_all(2)
	box.shadow_color = Color(0.08, 0.25, 0.34, 0.13)
	box.shadow_offset = Vector2(0, 4)
	box.shadow_size = 2
	draw_style_box(box, rect)

func centered_text(text: String, rect: Rect2, font_size: int, color: Color = INK) -> void:
	draw_string(body_font, Vector2(rect.position.x, rect.position.y + font_size), text, HORIZONTAL_ALIGNMENT_CENTER, rect.size.x, font_size, color)

func add_flight_camera() -> void:
	if not camera_on: return
	panel(Rect2(998, 469, 262, 231))
	flight_camera_label = label("Tracking dots" if tracking_ok else "Wings can't be seen", Vector2(1010, 480), 14, TEAL, 240)
	preview = TextureRect.new()
	preview.position = Vector2(1010, 506)
	preview.size = Vector2(240, 180)
	preview.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	preview.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var material_v := ShaderMaterial.new()
	material_v.shader = preload("res://scripts/camera_frame.gdshader")
	material_v.set_shader_parameter("frame_size", Vector2(240, 180))
	material_v.set_shader_parameter("radius", 12.0)
	preview.material = material_v
	ui.add_child(preview)
	preview_timer = 0

func add_pause_button() -> void:
	var pause_button := button("PAUSE", Rect2(1114, 24, 132, 64), func(): show_pause(false))
	pause_button.tooltip_text = "Pause flight (Esc)"
	for state in ["normal", "hover", "pressed", "focus"]:
		var box := pause_button.get_theme_stylebox(state).duplicate() as StyleBoxFlat
		box.set_corner_radius_all(12)
		box.set_border_width_all(2)
		pause_button.add_theme_stylebox_override(state, box)

func text_at(text: String, pos: Vector2, size_v: int, color: Color = INK) -> void:
	draw_string(body_font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, size_v, color)

func draw_heart(pos: Vector2, filled: bool) -> void:
	var pixels := ["0110110", "1111111", "1111111", "0111110", "0011100", "0001000"]
	var color := Color("dd5a73") if filled else Color("d4dfd8")
	for y in pixels.size():
		for x in pixels[y].length():
			if pixels[y][x] == "1": draw_rect(Rect2(pos + Vector2(x, y) * 4, Vector2(4, 4)), color)

func draw_hud() -> void:
	hud_panel(Rect2(274, 24, 156, 80))
	text_at("HEARTS", Vector2(292, 48), 14, TEAL)
	for i in 3: draw_heart(Vector2(292 + i * 40, 62), i < hearts)
	hud_panel(Rect2(30, 24, 224, 80))
	text_at("SCORE", Vector2(48, 48), 14, TEAL)
	text_at("%04d" % score, Vector2(48, 84), 34)
	draw_line(Vector2(157, 41), Vector2(157, 88), Color("c9dedb"), 2)
	draw_coin(Vector2(181, 51), 30)
	centered_text(str(coins), Rect2(162, 66, 66, 28), 22)
	hud_panel(Rect2(455, 24, 370, 80))
	text_at("GOLDEN SKY", Vector2(475, 50), 18)
	draw_string(body_font, Vector2(655, 50), "%02d / 60s" % int(elapsed), HORIZONTAL_ALIGNMENT_RIGHT, 150, 18, TEAL)
	var track := style(Color("dce8df"))
	track.set_corner_radius_all(5)
	track.set_border_width_all(0)
	draw_style_box(track, Rect2(475, 68, 330, 14))
	var progress := clampf(elapsed / DURATION, 0, 1)
	if progress > 0:
		var fill := track.duplicate() as StyleBoxFlat
		fill.bg_color = Color("f0b849")
		draw_style_box(fill, Rect2(475, 68, maxf(4, 330 * progress), 14))
	for mark in [0.25, 0.5, 0.75]:
		draw_line(Vector2(475 + mark * 330, 70), Vector2(475 + mark * 330, 80), CREAM, 2)
	hud_panel(Rect2(30, 620, 374, 66))
	var help := "SPACE / UP: rise   DOWN / S: dive" if control_mode == "keyboard" else "Near center: glide   /   Lower: dive"
	text_at(flight_state.to_upper(), Vector2(49, 647), 22, TEAL)
	text_at(help, Vector2(49, 673), 15)
	if countdown > 0:
		hud_panel(Rect2(510, 242, 260, 226))
		centered_text("TAKEOFF IN", Rect2(510, 263, 260, 24), 20, TEAL)
		centered_text(str(ceili(countdown)), Rect2(510, 292, 260, 85), 84)
		for i in 3:
			draw_circle(Vector2(618 + i * 22, 398), 5, GOLD if i < ceili(countdown) else Color("d3e0d7"))
		centered_text("Flap to climb" if control_mode == "wings" else "Hold SPACE to climb", Rect2(510, 426, 260, 20), 17)
	elif elapsed < 5:
		centered_text("Flap to rise. Spread to glide." if control_mode == "wings" else "Hold to flap. Release to glide.", Rect2(400, 568, 480, 30), 22)
	elif elapsed > 54:
		centered_text("The golden sky is yours.", Rect2(400, 568, 480, 30), 22)

func enable_camera() -> void:
	send_action("start", "/camera/start", '{"index":0}')

func capture_face() -> void:
	if not camera_on:
		set_status("Enable the camera first, then capture your face.")
		return
	if capture_busy: return
	capture_busy = true
	set_status("Finding your face and fitting your wings…")
	send_action("capture", "/camera/capture")

func calibrate_wings() -> void:
	if not camera_on:
		set_status("Connect the camera first, then spread your wings.")
		return
	send_action("calibrate", "/camera/calibrate")

func send_action(kind: String, path: String, body: String = "") -> void:
	if action_kind != "":
		set_status("Finishing the previous camera action…")
		return
	action_kind = kind
	var error := action_request.request(api_url + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, body)
	if error != OK:
		action_kind = ""
		capture_busy = false
		set_status("Could not connect. Check the bridge address.")

func on_action(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var kind := action_kind
	action_kind = ""
	capture_busy = false
	if code != 200:
		var message := "Bridge unavailable. Start the camera bridge, then Connect."
		var parser := JSON.new()
		var data = parser.data if parser.parse(body.get_string_from_utf8()) == OK else null
		if data is Dictionary: message = str(data.get("detail", message))
		set_status(message)
		return
	if kind == "start":
		camera_on = true
		set_status("Camera connected. Capture your face, or spread wings and calibrate.")
		apply_marker_color()
	elif kind == "color":
		calibrated = false
		save_settings()
		set_status("Tracking settings applied. Spread your wings and recalibrate.")
	elif kind == "capture":
		var img := Image.new()
		if img.load_png_from_buffer(body) == OK:
			face = ImageTexture.create_from_image(img)
			set_status("Looking good. Your wings are ready.")
		else: set_status("Could not read the portrait. Please capture again.")
	elif kind == "calibrate":
		calibrated = true
		set_status("Calibrated. Flap to rise, hold near center to glide, lower both to dive.")

func poll_camera(delta: float) -> void:
	if not camera_on: return
	poll_timer -= delta
	preview_timer -= delta
	if poll_timer <= 0 and state_request.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED:
		poll_timer = 0.08
		state_request.request(api_url + "/camera/state")
	if screen in ["setup", "wing_colors", "play", "pause"] and preview_timer <= 0 and preview_request.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED:
		preview_timer = 0.15
		preview_screen = screen
		preview_color = hue_preview_query() if screen == "wing_colors" else ""
		var query := "?dots=true" if screen in ["play", "pause"] else preview_color
		preview_request.request(api_url + "/camera/frame" + query)

func on_state(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if code != 200:
		tracking_ok = false
		return
	var data = JSON.parse_string(body.get_string_from_utf8())
	if not data is Dictionary: return
	tracking_ok = data.get("tracking", false)
	calibrated = data.get("calibrated", false)
	tracked_state = data.get("state", "lost")
	last_tracking = clock
	if is_instance_valid(flight_camera_label):
		flight_camera_label.text = ("Last frame / holding" if data.get("held", false) else "3 dots / " + tracked_state.to_upper()) if tracking_ok else "Wings can't be seen"
	if screen == "settings" and camera_on and action_kind == "":
		var variables = data.get("variables")
		if calibrated and tracking_ok and variables is Dictionary and data.get("span_ratio") != null:
			set_status("3/3 markers / %s / Left Y %.1f / Right Y %.1f / Span %.0f%%" % [tracked_state.to_upper(), variables.get("left_height_relative_to_average", 0), variables.get("right_height_relative_to_average", 0), float(data.span_ratio) * 100])
		else:
			set_status("%s / %s / %s" % [str(data.get("dot_count", 0)) + "/3 markers", tracked_state.to_upper(), "calibrated" if calibrated else "spread wings and calibrate"])

func on_preview(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if screen != preview_screen: return
	if screen == "wing_colors" and preview_color != hue_preview_query(): return
	if code != 200:
		if action_kind == "":
			var detail := "Camera preview unavailable (HTTP %d). Reconnect to retry." % code
			var error_data = JSON.parse_string(body.get_string_from_utf8())
			if error_data is Dictionary: detail = str(error_data.get("detail", detail))
			set_status(detail)
		return
	var img := Image.new()
	if img.load_jpg_from_buffer(body) == OK:
		var texture := ImageTexture.create_from_image(img)
		if screen == "wing_colors" and dropper_active: dropper_image = img
		if screen == "setup": camera_image = texture
		if is_instance_valid(preview): preview.texture = texture
		if screen == "wing_colors" and not dropper_active and action_kind == "" and status_text.begins_with("Camera preview unavailable"):
			set_status("Live preview / Adjust the sliders, then Apply.")

func set_status(message: String) -> void:
	status_text = message
	if is_instance_valid(status_label): status_label.text = message

func load_settings() -> void:
	var config := ConfigFile.new()
	if config.load("user://cloudbound.cfg") == OK:
		control_mode = config.get_value("game", "controls", "keyboard")
		muted = config.get_value("game", "muted", false)
		reduced_motion = config.get_value("game", "reduced_motion", false)
		api_url = config.get_value("game", "api_url", api_url)
		marker_color = Color(config.get_value("game", "marker_color", "#00ff00"))
		hue_tolerance = clampi(config.get_value("game", "hue_tolerance", 15), 0, 90)
		shade_tolerance = clampi(config.get_value("game", "shade_tolerance", 160), 0, 255)
		min_dot_area = clampi(config.get_value("game", "min_dot_area", 30), 1, 100000)
		second_marker_color = Color(config.get_value("game", "second_marker_color", "#ff0000"))
		second_color_enabled = config.get_value("game", "second_color_enabled", false)
		best = config.get_value("game", "best", 0)

func save_settings() -> void:
	if testing: return
	var config := ConfigFile.new()
	config.set_value("game", "controls", control_mode)
	config.set_value("game", "muted", muted)
	config.set_value("game", "reduced_motion", reduced_motion)
	config.set_value("game", "api_url", api_url)
	config.set_value("game", "best", best)
	config.set_value("game", "marker_color", "#" + marker_color.to_html(false))
	config.set_value("game", "hue_tolerance", hue_tolerance)
	config.set_value("game", "shade_tolerance", shade_tolerance)
	config.set_value("game", "min_dot_area", min_dot_area)
	config.set_value("game", "second_marker_color", "#" + second_marker_color.to_html(false))
	config.set_value("game", "second_color_enabled", second_color_enabled)
	config.save("user://cloudbound.cfg")

func chirp(frequency: float, duration: float, volume: float = 0.10) -> void:
	if muted: return
	var wave := AudioStreamWAV.new()
	wave.format = AudioStreamWAV.FORMAT_16_BITS
	wave.mix_rate = 22050
	var count := int(22050 * duration)
	var data := PackedByteArray()
	data.resize(count * 2)
	for i in count:
		var t := float(i) / 22050
		var envelope := sin(PI * float(i) / count)
		var value := int(sin(TAU * frequency * t * (1.0 + t)) * envelope * volume * 32767)
		data.encode_s16(i * 2, value)
	wave.data = data
	sound.stream = wave
	sound.play()
