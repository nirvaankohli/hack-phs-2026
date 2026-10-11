class_name SuppliedAssets
extends RefCounted

# Sprite-sheet regions reference the original supplied images, kept unchanged.
# Flat preview backgrounds become transparent when textures enter the renderer.
var coin_frames: Array[Texture2D] = []
var sun: Texture2D
var storm_cloud: Texture2D
var lightning: Texture2D
var wing_frames: Array[Texture2D] = []
var bird_species: Array[Array] = []

func _init() -> void:
	for x in [16, 53, 89, 125, 162, 198]:
		coin_frames.append(region("res://assets/source/coins.png", Rect2i(x, 44, 36, 36), Color.WHITE, 0.08))
	sun = region("res://assets/source/sun.png", Rect2i(20, 20, 220, 218), Color.WHITE, 0.08)
	storm_cloud = region("res://assets/source/storm.png", Rect2i(95, 48, 365, 208), Color.WHITE, 0.08)
	lightning = region("res://assets/source/storm.png", Rect2i(164, 259, 236, 247), Color.WHITE, 0.08)
	for rect in [Rect2i(16, 81, 74, 33), Rect2i(100, 81, 64, 33), Rect2i(188, 80, 48, 34), Rect2i(35, 147, 36, 32), Rect2i(108, 147, 50, 33), Rect2i(180, 146, 65, 34)]:
		wing_frames.append(region("res://assets/source/wings.png", rect, Color("d2d3d5"), 0.075))
	# Yellow, green, goose, blue, and green/yellow birds from the supplied sheet.
	var sheets := [
		[Rect2i(30, 174, 115, 82), Rect2i(174, 174, 115, 82), Rect2i(307, 174, 115, 82), Rect2i(442, 174, 115, 82)],
		[Rect2i(30, 277, 120, 96), Rect2i(166, 277, 120, 96), Rect2i(301, 277, 120, 96), Rect2i(431, 277, 120, 96)],
		[Rect2i(40, 382, 260, 148), Rect2i(298, 382, 260, 148), Rect2i(40, 530, 260, 148), Rect2i(298, 530, 260, 148)],
		[Rect2i(36, 681, 134, 112), Rect2i(173, 681, 129, 112), Rect2i(305, 681, 129, 112), Rect2i(438, 681, 132, 112)],
		[Rect2i(27, 800, 130, 96), Rect2i(163, 800, 130, 96), Rect2i(299, 800, 130, 96), Rect2i(433, 800, 130, 96)]
	]
	for rects in sheets:
		var frames: Array[Texture2D] = []
		for rect in rects:
			frames.append(region("res://assets/source/birds.png", rect, Color.WHITE, 0.08))
		bird_species.append(frames)

static func region(path: String, rect: Rect2i, background: Color, tolerance: float) -> Texture2D:
	var source := load(path) as Texture2D
	var image := source.get_image().get_region(rect)
	image.convert(Image.FORMAT_RGBA8)
	for y in image.get_height():
		for x in image.get_width():
			var color := image.get_pixel(x, y)
			var difference := maxf(absf(color.r - background.r), maxf(absf(color.g - background.g), absf(color.b - background.b)))
			if difference < tolerance:
				color.a = 0.0
				image.set_pixel(x, y, color)
	return ImageTexture.create_from_image(image)
