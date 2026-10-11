shader_type canvas_item;

uniform float scroll = 0.0;
uniform float motion_amount = 1.0;

void fragment() {
    // Move whole, undistorted copies left. Crossfade only their overlapping edges.
    float overlap = 0.12;
    float stride = 1.0 - overlap;
    float x = mod(UV.x + scroll, stride);
    vec4 incoming = texture(TEXTURE, vec2(x, UV.y));
    vec4 sky = incoming;
    if (x < overlap) {
        vec4 outgoing = texture(TEXTURE, vec2(x + stride, UV.y));
        sky = mix(outgoing, incoming, smoothstep(0.0, overlap, x));
    }
    COLOR = mix(texture(TEXTURE, UV), sky, motion_amount);
}
