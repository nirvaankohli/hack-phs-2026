extends RefCounted

var wing_angle := 0.0
var vertical_speed := 0.0
var flap_lift := 0.0
var forward_speed := 230.0
var cooldown := 0.0
var flap_flash := 0.0
var flap_count := 0
var flap_strength := 0.0
var diving := false
var pullup_flash := 0.0
var pullup_ready := false
var heat := 0.0

func update_heat(delta: float, altitude: float, in_cloud: bool) -> void:
	if in_cloud:
		heat -= delta / 3.0
	elif altitude > 0.65:
		heat += delta * lerpf(0.025, 0.095, clampf((altitude - 0.65) / 0.35, 0.0, 1.0))
	else:
		heat -= delta * 0.035
	heat = clampf(heat, 0.0, 1.0)

func wing_condition() -> float:
	return 1.0 - heat * 0.65

func reset() -> void:
	heat = 0.0
	wing_angle = 0.0
	vertical_speed = 0.0
	flap_lift = 0.0
	forward_speed = 230.0
	cooldown = 0.0
	flap_flash = 0.0
	flap_count = 0
	flap_strength = 0.0
	diving = false
	pullup_flash = 0.0
	pullup_ready = false

func update(delta: float, angle: float) -> void:
	wing_angle = clampf(angle, -60.0, 0.0)
	cooldown = maxf(0.0, cooldown - delta)
	flap_flash = maxf(0.0, flap_flash - delta)
	pullup_flash = maxf(0.0, pullup_flash - delta)
	# Lowering wings gives a gentle, predictable sink at every angle.
	var descent_amount := -wing_angle / 60.0
	diving = false
	# Only explicit flaps add upward momentum. Level wings stop angle-driven sink.
	flap_lift = move_toward(flap_lift, 0.0, 140.0 * delta)
	vertical_speed = 70.0 * descent_amount + 85.0 * heat * heat - flap_lift
	forward_speed = 230.0

# Explicit flap action; angle changes never trigger a flap.
func flap(strength: float = 0.65) -> bool:
	if cooldown > 0.0:
		return false
	flap_strength = clampf(strength, 0.45, 1.0)
	flap_lift = minf(flap_lift + lerpf(150.0, 230.0, flap_strength) * wing_condition(), 260.0)
	vertical_speed = 70.0 * (-wing_angle / 60.0) + 85.0 * heat * heat - flap_lift
	flap_count += 1
	flap_flash = 0.4
	cooldown = 0.32
	return true

