class_name FlightModel
extends RefCounted

const FLAP_SPEED := -215.0
const GLIDE_SPEED := 62.0
const DIVE_SPEED := 240.0

static func next_velocity(current: float, mode: String, delta: float) -> float:
	var target := GLIDE_SPEED
	var acceleration := 500.0
	if mode == "flap":
		target = FLAP_SPEED
		acceleration = 1100.0
	elif mode == "dive":
		target = DIVE_SPEED
		acceleration = 750.0
	return move_toward(current, target, acceleration * delta)
