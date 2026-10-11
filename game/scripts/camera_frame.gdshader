shader_type canvas_item;
uniform vec2 frame_size = vec2(400.0, 300.0);
uniform float radius = 18.0;
uniform vec4 border_color : source_color = vec4(0.64, 0.78, 0.80, 1.0);
void fragment() {
    vec4 pixel = texture(TEXTURE, UV);
    vec2 q = abs(UV * frame_size - frame_size * 0.5) - (frame_size * 0.5 - vec2(radius));
    float distance_to_edge = length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - radius;
    float mask = 1.0 - smoothstep(-0.8, 0.0, distance_to_edge);
    float border = smoothstep(-3.2, -2.2, distance_to_edge);
    COLOR = vec4(mix(pixel.rgb, border_color.rgb, border), pixel.a * mask);
}
