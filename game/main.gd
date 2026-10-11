extends Node2D

const SIZE := Vector2(1152, 648)
const PLAYER_X := 240.0
const RADIUS := 17.0
const SKY_TOP := 95.0
const SEA_Y := 558.0
const GOLD := Color("ffd18a")
const MINT := Color("a8e5df")
const INK := Color("101e32")
const FlightController := preload("res://flight_controller.gd")
var player_y := 340.0
var velocity := 0.0
var elapsed := 0.0
var distance := 0.0
var score := 0.0
var sunlight_score := 0.0
var recovery_count := 0
var best := 0
var highest_altitude := 0.0
var state := "ready"
var flight_angle_degrees := 0.0
var flight = FlightController.new()
var font: Font = ThemeDB.fallback_font
var clouds: Array[Dictionary] = []
var trail: Array[Vector2] = []
var particles: Array[Dictionary] = []
var cloud_index := 0
var next_cloud_distance := 880.0
var in_cloud := false
var recovery_armed := false
var bonus_flash := 0.0
var particle_timer := 0.0

func _ready() -> void:
	seed_clouds()

# Shared pose interface; changing angle alone never creates a flap.
func set_flight_angle(degrees: float) -> void:
	if is_finite(degrees):
		flight_angle_degrees = clampf(degrees, -60.0, 0.0)

func _unhandled_key_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_ENTER or event.keycode == KEY_SPACE:
		if state == "ready" or state == "over":
			start_run()
		if event.keycode == KEY_SPACE and state == "playing":
			flight.flap()
	if event.keycode == KEY_R:
		start_run()
	if event.keycode == KEY_ESCAPE:
		if state == "playing":
			state = "paused"
		elif state == "paused":
			state = "playing"

func start_run() -> void:
	player_y = 340.0
	velocity = 0.0
	elapsed = 0.0
	distance = 0.0
	score = 0.0
	sunlight_score = 0.0
	recovery_count = 0
	highest_altitude = 0.0
	flight.reset()
	flight_angle_degrees = 0.0
	in_cloud = false
	recovery_armed = false
	bonus_flash = 0.0
	particle_timer = 0.0
	trail.clear()
	particles.clear()
	seed_clouds()
	state = "playing"

func seed_clouds() -> void:
	clouds.clear()
	cloud_index = 0
	clouds.append({"x": 650.0, "y": 370.0, "width": 800.0, "height": 125.0})
	clouds.append({"x": 1530.0, "y": 425.0, "width": 800.0, "height": 125.0})
	next_cloud_distance = 880.0

func altitude() -> float:
	return clampf((SEA_Y - RADIUS - player_y) / (SEA_Y - RADIUS - SKY_TOP), 0.0, 1.0)

func cloud_contains_player() -> bool:
	for cloud in clouds:
		var offset := Vector2(PLAYER_X - float(cloud["x"]), player_y - float(cloud["y"]))
		if pow(offset.x / (float(cloud["width"]) * 0.5), 2) + pow(offset.y / (float(cloud["height"]) * 0.5), 2) <= 1.0:
			return true
	return false

func update_rewards(delta: float) -> void:
	var gain := 10.0 * altitude() * altitude() * delta
	sunlight_score += gain
	score += gain
	highest_altitude = maxf(highest_altitude, altitude())
	if flight.heat >= 0.75:
		recovery_armed = true
	if recovery_armed and in_cloud and flight.heat <= 0.25:
		recovery_count += 1
		score += 100.0
		recovery_armed = false
		bonus_flash = 2.5

func _physics_process(delta: float) -> void:
	if state != "playing":
		queue_redraw()
		return
	elapsed += delta
	bonus_flash = maxf(0.0, bonus_flash - delta)
	adjust_angle(delta, float(Input.is_physical_key_pressed(KEY_UP)) - float(Input.is_physical_key_pressed(KEY_DOWN)))
	in_cloud = cloud_contains_player()
	if flight.heat >= 0.75:
		recovery_armed = true
	flight.update_heat(delta, altitude(), in_cloud)
	flight.update(delta, flight_angle_degrees)
	velocity = flight.vertical_speed
	player_y = maxf(SKY_TOP, player_y + velocity * delta)
	if player_y == SKY_TOP:
		flight.flap_lift = minf(flight.flap_lift, 85.0 * flight.heat * flight.heat)
	distance += flight.forward_speed * delta
	for cloud in clouds:
		cloud["x"] -= flight.forward_speed * delta
	if distance >= next_cloud_distance:
		var heights := [350.0, 405.0, 375.0, 430.0]
		clouds.append({"x": 1530.0, "y": heights[cloud_index % heights.size()], "width": 800.0, "height": 125.0})
		cloud_index += 1
		next_cloud_distance += 880.0
	clouds = clouds.filter(func(c: Dictionary) -> bool: return float(c["x"]) > -450.0)
	in_cloud = cloud_contains_player()
	update_rewards(delta)
	for i in range(trail.size()):
		trail[i].x -= flight.forward_speed * delta
	trail.append(Vector2(PLAYER_X, player_y))
	if trail.size() > 40:
		trail.pop_front()
	update_particles(delta)
	if player_y + RADIUS >= SEA_Y:
		finish_run()
	queue_redraw()

func update_particles(delta: float) -> void:
	particle_timer -= delta
	if flight.heat > 0.45 and particle_timer <= 0.0:
		particle_timer = lerpf(0.5, 0.12, flight.heat)
		particles.append({"position": Vector2(PLAYER_X - 8.0, player_y + 8.0), "life": 1.5, "feather": int(elapsed * 10) % 3 == 0})
	for particle in particles:
		particle["life"] -= delta
		particle["position"] += Vector2(-130.0, 65.0) * delta
	particles = particles.filter(func(p: Dictionary) -> bool: return float(p["life"]) > 0.0)

func adjust_angle(delta: float, direction: float) -> void:
	if Input.is_physical_key_pressed(KEY_LEFT) or Input.is_physical_key_pressed(KEY_RIGHT):
		set_flight_angle(0.0)
	else:
		set_flight_angle(flight_angle_degrees + direction * 40.0 * delta)

func finish_run() -> void:
	state = "over"
	best = maxi(best, int(score))

func text_at(value: String, at: Vector2, size: int, color: Color = Color.WHITE) -> void:
	draw_string(font, at, value, HORIZONTAL_ALIGNMENT_LEFT, -1, size, color)

func _draw() -> void:
	draw_sky()
	for cloud in clouds:
		draw_cloud(cloud)
	for i in range(trail.size()):
		draw_circle(trail[i], 2.0, Color(GOLD, float(i) / 90.0))
	for particle in particles:
		var p: Vector2 = particle["position"]
		var color := Color(GOLD, float(particle["life"]) / 1.5)
		if particle["feather"]:
			draw_line(p - Vector2(7, 3), p + Vector2(7, 3), color, 3.0, true)
		else:
			draw_circle(p, 2.5, color)
	draw_icarus()
	draw_hud()
	if state != "playing":
		draw_overlay()

func draw_sky() -> void:
	for y in range(0, int(SEA_Y), 6):
		var blend := pow(1.0 - float(y) / SEA_Y, 1.8)
		draw_rect(Rect2(0, y, SIZE.x, 6), Color("426779").lerp(Color("d98c60"), blend))
	var sun := Vector2(925, 120)
	for radius in [145.0, 110.0, 78.0]:
		draw_circle(sun, radius, Color(1.0, 0.77, 0.45, 0.07))
	draw_circle(sun, 46, Color("ffe2a4"))
	text_at("THE SUN GIVES. THE SUN TAKES.", Vector2(716, 211), 15, Color(GOLD, 0.75))
	var danger_y := SEA_Y - RADIUS - 0.65 * (SEA_Y - RADIUS - SKY_TOP)
	draw_dashed_line(Vector2(0, danger_y), Vector2(SIZE.x, danger_y), Color(GOLD, 0.18), 1.0, 14.0)
	draw_rect(Rect2(0, SEA_Y, SIZE.x, SIZE.y - SEA_Y), Color("102c43"))
	for row in range(4):
		var points := PackedVector2Array()
		for x in range(-20, 1180, 12):
			points.append(Vector2(x, SEA_Y + row * 19 + sin(float(x) * 0.018 + distance * 0.009 + row) * 4))
		draw_polyline(points, Color(Color("528292"), 0.5 - row * 0.09), 1.5, true)

func draw_cloud(cloud: Dictionary) -> void:
	var center := Vector2(float(cloud["x"]), float(cloud["y"]))
	var width: float = cloud["width"]
	var height: float = cloud["height"]
	draw_set_transform(center, 0.0, Vector2(width / height, 1.0))
	draw_circle(Vector2.ZERO, height * 0.5, Color(0.78, 0.92, 0.94, 0.15))
	draw_set_transform(Vector2.ZERO)
	for i in range(11):
		var p := center + Vector2((i - 5) * width / 12.0, sin(i * 1.7) * 15.0)
		draw_circle(p, 32.0 + sin(i * 2.3) * 8.0, Color(0.82, 0.94, 0.95, 0.13))
	text_at("COOLING CLOUD", center + Vector2(-67, 7), 15, Color(MINT, 0.8))

func draw_icarus() -> void:
	var p := Vector2(PLAYER_X, player_y)
	draw_set_transform(p, clampf(atan2(velocity, flight.forward_speed), -0.55, 0.65))
	var spread: float = 44.0 * flight.wing_condition()
	var stroke := sin((0.4 - flight.flap_flash) * 13.0) * 18.0 if flight.flap_flash > 0.0 else 0.0
	var wing_color := GOLD.lerp(Color("c57b5d"), flight.heat)
	for side in [-1.0, 1.0]:
		var tip := Vector2(-18.0, side * spread - stroke)
		draw_colored_polygon(PackedVector2Array([Vector2(4, 0), Vector2(-14, side * 10), tip, Vector2(15, side * spread * 0.5 - stroke)]), wing_color)
		for feather in range(4):
			var base := tip.lerp(Vector2(15, side * spread * 0.5 - stroke), feather / 4.0)
			draw_line(base, base + Vector2(-12, side * 6), wing_color, 4.0, true)
	draw_line(Vector2(-13, 0), Vector2(12, 0), INK, 8.0, true)
	draw_circle(Vector2(17, -2), 6.5, INK)
	draw_line(Vector2(-10, 0), Vector2(-24, 9), INK, 3.0, true)
	draw_set_transform(Vector2.ZERO)
	if flight.flap_flash > 0.0:
		draw_arc(p, 30 + (0.4 - flight.flap_flash) * 45, 0, TAU, 40, Color(GOLD, flight.flap_flash), 2, true)
	if in_cloud:
		text_at("WINGS COOLING", p + Vector2(-63, -65), 16, MINT)
	elif flight.heat >= 0.75:
		text_at("WAX MELTING - DESCEND", p + Vector2(-99, -65), 16, GOLD)
	if bonus_flash > 0.0:
		text_at("+100  SUN SURVIVOR", Vector2(425, 295), 26, MINT)

func draw_hud() -> void:
	draw_rect(Rect2(0, 0, SIZE.x, 74), Color(INK, 0.94))
	text_at("I C A R U S", Vector2(28, 36), 27, GOLD)
	text_at("RISK THE SUN / HACKPHS 2026", Vector2(29, 58), 12, MINT)
	text_at("SUNLIGHT  %04d" % int(score), Vector2(425, 44), 25, GOLD)
	text_at("BEST  %04d" % best, Vector2(760, 44), 20, MINT)
	text_at("%02d:%02d" % [int(elapsed / 60), int(elapsed) % 60], Vector2(1030, 44), 20)
	draw_rect(Rect2(24, 90, 269, 108), Color(INK, 0.82))
	text_at("WING HEAT  %d%%" % int(flight.heat * 100), Vector2(38, 115), 16, GOLD)
	draw_rect(Rect2(38, 127, 237, 7), Color("344956"))
	draw_rect(Rect2(38, 127, 237 * flight.heat, 7), MINT.lerp(Color("f39767"), flight.heat))
	draw_line(Vector2(38 + 237 * 0.75, 124), Vector2(38 + 237 * 0.75, 138), GOLD, 1)
	text_at("LIFT %d%%   /   WINGS %+.0f deg" % [int(flight.wing_condition() * 100), flight_angle_degrees], Vector2(38, 158), 14, MINT)
	text_at("SPACE: ready" if flight.cooldown <= 0.0 else "SPACE: recharging", Vector2(38, 183), 14, MINT)
	text_at("HIGHER FLIGHT = MORE POINTS", Vector2(777, 529), 15, GOLD)
	draw_rect(Rect2(0, 609, SIZE.x, 39), Color(INK, 0.95))
	text_at("SPACE  Flap     UP / DOWN  Wing angle     LEFT / RIGHT  Level     ESC  Pause     R  Retry", Vector2(30, 634), 16, MINT)

func draw_overlay() -> void:
	draw_rect(Rect2(0, 74, SIZE.x, 535), Color(0.03, 0.08, 0.14, 0.45))
	draw_rect(Rect2(316, 217, 580, 282), Color(INK, 0.97))
	draw_rect(Rect2(316, 217, 580, 282), Color(GOLD, 0.6), false, 1)
	var title := "HOW CLOSE WILL YOU FLY?"
	if state == "over":
		title = "THE SEA REMEMBERS"
	elif state == "paused":
		title = "REST YOUR WINGS"
	text_at(title, Vector2(346, 270), 29, GOLD)
	if state == "over":
		text_at("SUNLIGHT  %d   +   SAVES  %d x 100" % [int(sunlight_score), recovery_count], Vector2(346, 316), 21, MINT)
		text_at("SCORE  %d     /     BEST  %d" % [int(score), best], Vector2(346, 360), 27, GOLD)
		text_at("Highest flight %d%%   /   %.1f seconds aloft" % [int(highest_altitude * 100), elapsed], Vector2(346, 399), 18)
	else:
		text_at("Flap toward the sun. Earn more the higher you fly.", Vector2(346, 315), 20)
		text_at("Heat melts your wings. Clouds restore their lift.", Vector2(346, 352), 20, MINT)
		text_at("Survive dangerous heat and cool off: +100 points.", Vector2(346, 389), 19, GOLD)
		text_at("DOWN to descend. LEFT / RIGHT to level wings.", Vector2(346, 422), 17, MINT)
	var prompt := "ENTER / SPACE  Fly    /    R  Retry"
	if state == "paused":
		prompt = "ESC  Resume    /    R  Retry"
	text_at(prompt, Vector2(346, 458), 21, MINT)
