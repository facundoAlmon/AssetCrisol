// Textura de detalle de un tema de AssetCrisol: el detalle viene en lineal (gris medio = el color del tema), así que
// el color final es tinte × detalle × 2 en lineal (README > Escenarios). `luz` oscurece una pared de costado.
shader_type canvas_item;

uniform vec4 tinte = vec4(0.5, 0.5, 0.5, 1.0);
uniform float luz = 1.0;

vec3 a_lineal(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c));
}

vec3 a_srgb(vec3 c) {
	return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c));
}

void fragment() {
	vec3 detalle = texture(TEXTURE, UV).rgb;
	vec3 c = a_lineal(tinte.rgb) * detalle * 2.0 * luz;
	COLOR = vec4(a_srgb(clamp(c, 0.0, 1.0)), 1.0);
}
