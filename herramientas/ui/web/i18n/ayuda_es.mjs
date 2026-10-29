// Ayuda extendida de cada paso (el "Más" de la cadena): qué hace, qué mirar y qué probar si sale mal, más la sección
// del README. Las mismas claves en ayuda_en.mjs. `blender_<tipo>`: el paso blender de objetos y vehículos.
export default {
  imagen: {
    hace: 'Genera una imagen candidata por cada seed. Con referencia, Qwen Image Edit la redibuja en el estilo y conserva el diseño; sin referencia, Z-Image Turbo (o FLUX.2) la inventa desde la descripción. Unos 20 s por seed.',
    mirar: 'Elegí la de proporciones correctas (a veces salen cabezonas), cuerpo entero, brazos separados del cuerpo y piernas un poco abiertas: lo que se toca en la imagen se funde en la malla. Sin piezas sueltas (correas, cartucheras) ni texto.',
    mal: 'Probá otras seeds (Ajustes > Imagen) antes de cambiar la descripción. Si la idea está bien pero tiene detalles feos, usala de referencia y pasala de nuevo por Qwen pidiendo solo esos cambios. Ojos achinados: editar solo los ojos, no cambiar de seed.',
    readme: '1-imagen-crisol-imagen',
  },
  vistas: {
    hace: 'Dibuja con Qwen la espalda y los dos costados de la imagen elegida. La malla de 4 vistas (Pixal3D) y el repintado con UltraTex las usan.',
    mirar: 'Que la espalda no repita lo del pecho (un logo, una luz) y que cada costado mire hacia su borde de la imagen.',
    mal: 'Borrá la vista mala (Archivos: trabajo/imagen/vista_<v>.png) y volvé a correr el paso: solo rehace las que faltan.',
    readme: 'vistas-crisol-vistas',
  },
  malla: {
    hace: 'Arma el modelo 3D texturizado desde la imagen elegida: Pixal3D (mejor en caras y estampados) o TRELLIS.2 (objetos y vehículos), y si está activado lo repinta con UltraTex. Entre 2 y 8 minutos. Con candidatos, genera solo los que faltan.',
    mirar: 'El modelo en 3D desde todos lados: la cara de cerca, la espalda (sin repintado inventa copiando el pecho), agujeros y colores. Con candidatos, compará las tarjetas y elegí uno.',
    mal: 'La seed de la malla pesa mucho: probá 2 o 3 antes de tocar otra cosa (Ajustes > Malla, como candidatos). Cara manchada con TRELLIS.2: probá Pixal3D + UltraTex. Ojos raros: otra seed de UltraTex.',
    readme: '2-malla-crisol-malla',
  },
  ultratex: {
    hace: 'Vuelve a pintar la textura de la malla con UltraTex mirando la imagen elegida (y, si están, las vistas de espalda y costados). No cambia la forma.',
    mirar: 'La cara de cerca (los ojos dependen de la seed de UltraTex) y la espalda.',
    mal: 'Otra seed de UltraTex. Si la espalda copia el pecho, activá "Pintar la espalda con la vista de Qwen" en Ajustes > Malla.',
    readme: '2-malla-crisol-malla',
  },
  guia: {
    hace: 'Renderiza la malla de frente y de costado con una grilla y dibuja dónde quedaron las articulaciones (hombros, codos, caderas, rodillas...). Es solo para revisar: no cambia nada.',
    mirar: 'Que cada articulación caiga en su lugar del cuerpo, de frente y de costado. Verde: huesos que deforman; naranja: controles; amarillo: cabezas de hueso.',
    mal: 'Corré "Detectar articulaciones" y volvé a mirar la guía. En muñecos o juguetes donde no anda, hay que cargarlas a mano en el json.',
    readme: '3a-guía-de-articulaciones-crisol-guia',
  },
  articulaciones: {
    hace: 'Detecta las articulaciones con DWPose sobre los renders de la guía y las guarda en el personaje. Si no encuentra a nadie o la pose no es creíble, deja las de antes.',
    mirar: 'Después, la guía: que hombros, codos, muñecas, caderas, rodillas y tobillos caigan en su lugar.',
    mal: 'A veces la primera vez sale mal y al volver a correrlo anda. Con muñecos, juguetes y chibis DWPose no suele detectar a nadie: cargarlas a mano mirando la guía.',
    readme: '3a-guía-de-articulaciones-crisol-guia',
  },
  blender: {
    hace: 'En Blender: le pone un esqueleto a la malla, calcula cuánto mueve cada hueso a cada parte (pesos), arma todas las animaciones y renderiza sus cuadros de costado. Segundos a un minuto.',
    mirar: 'Las animaciones en el resultado (después de "Hoja de sprites"): codos y rodillas que doblan bien, nada que se estire raro, la cara mirando al frente.',
    mal: 'Cara que mira arriba o abajo: Ajustes > Modelo > Cabeza arriba (negativo levanta la cara). Codos "de plastilina", piezas que se arrastran o brazos fundidos: ver la sección de pesos del README. Si las articulaciones están mal, todo lo demás sale mal: mirar primero la guía.',
    readme: '3b-blender-crisol-blender',
  },
  blender_objeto: {
    hace: 'En Blender: renderiza el objeto en las 8 direcciones isométricas y de costado, con la luz y el estilo elegidos.',
    mirar: 'Que el objeto esté derecho y entero en todas las vistas.',
    mal: 'Si está girado, Ajustes > Modelo > Giro. Si le falta una parte o tiene agujeros, es la malla: probá otra seed.',
    readme: 'objetos',
  },
  blender_vehiculo: {
    hace: 'En Blender: separa las ruedas de la carrocería (para que giren), arma vehiculo.glb y una hoja de revisión. Con candidatos, arma uno por candidato.',
    mirar: 'Las 4 ruedas separadas y en su lugar, la trompa hacia adelante y sin agujeros en la carrocería.',
    mal: 'Autos en tres cuartos desde arriba salen mejor con TRELLIS.2. Si una rueda queda pegada, probá otra seed de malla.',
    readme: 'vehículos',
  },
  sprites: {
    hace: 'Junta los cuadros renderizados en una hoja de sprites (13 columnas), escribe el meta con cada animación, el gif de vista previa y el retrato. Aplica el posproceso del estilo (color, nitidez, contorno).',
    mirar: 'El gif de la animación: que todas se vean bien y el personaje no salte de lugar entre cuadros.',
    mal: 'Si se ve chico o grande, Ajustes > Sprites > Alto en pantalla. Problemas de movimiento vienen de "Rig y animaciones".',
    readme: '4-sprites-crisol-sprites',
  },
  retrato: {
    hace: 'Rehace solo el retrato (la cara recortada) y el cuerpo de frente, sin volver a armar la hoja.',
    mirar: 'Que la cara quede centrada y entera en el recorte.',
    mal: 'El retrato sale de la imagen elegida sin fondo; si preferís el render 3D, se cambia en el json (retrato.fuente).',
    readme: '4-sprites-crisol-sprites',
  },
  iso: {
    hace: 'Renderiza las animaciones con cámara isométrica (30°) en 8 direcciones, una hoja por animación. Unos 25 s.',
    mirar: 'El reproductor iso del resultado: probá varias animaciones y direcciones, sobre todo de espaldas.',
    mal: 'Si sobran animaciones (pesa más), elegí cuáles en Ajustes > Animaciones del isométrico. Lo que se ve mal en todas las direcciones viene de "Rig y animaciones".',
    readme: 'iso-crisol-iso',
  },
  anclas: {
    hace: 'Sin renderizar (unos segundos): guarda por cada cuadro iso dónde están las manos, la cabeza, el pecho y los pies, para colgarle al personaje una espada o un casco en el juego.',
    mirar: 'Nada a la vista: se usa desde el juego. Correrlo después de cada "Isométrico".',
    mal: 'Si en el juego lo colgado no sigue a la mano, volvé a correr Isométrico y Anclas con el mismo json.',
    readme: 'anclas-crisol-anclas',
  },
  revisar: {
    hace: 'Arma una hoja de control con la cabeza de costado, los codos doblados, la caminata iso de frente y de espalda, las poses clave y el "revés": lo que se ve del interior de la malla, en magenta.',
    mirar: 'Es lo último que hay que mirar antes de usar el personaje. Avisa si en alguna pose el revés pasa del 3 % (la boca abierta siempre marca y no es un problema).',
    mal: 'Manchas magenta grandes: agujeros o ropa que se atraviesa al animar. Probá otra malla o, si son caras al revés, la opción de normales del README.',
    readme: 'qué-mirar-en-cada-paso-receta-para-humanoides',
  },
  godot: {
    hace: 'Exporta escenas y recursos listos para un proyecto de Godot (el sprite con sus animaciones y su script), en la carpeta godot/ del asset.',
    mirar: 'Nada a la vista: copiar la carpeta al proyecto. No instala en ningún proyecto solo.',
    mal: 'Si cambiaste animaciones, rehacé Hoja de sprites e Isométrico antes de exportar.',
    readme: '5-godot-crisol-godot',
  },
  comparar: {
    hace: 'Arma una hoja con todos los candidatos de malla ya generados, renderizados igual, y las vistas de cada tarjeta para elegir.',
    mirar: 'Las tarjetas de Te toca elegir: cara, espalda y agujeros de cada candidato.',
    mal: 'Si un candidato no aparece, todavía no está generado: corré Malla 3D.',
    readme: '2-malla-crisol-malla',
  },
  texturas: {
    hace: 'Genera candidatas de cada textura repetible del escenario (piso, camino, pared, fondo), una por seed.',
    mirar: 'Que se repitan sin costuras y que de lejos no se vean como ruido: mejor formas grandes y poco detalle.',
    mal: 'Otras seeds o una descripción más simple (Ajustes > Escenario). Con "solo" se rehacen algunas texturas.',
    readme: 'escenarios',
  },
  tema: {
    hace: 'Con las texturas elegidas arma las repetibles finales, los colores del tema y una vista previa del escenario.',
    mirar: 'La vista previa: que piso, camino y pared combinen y se distingan.',
    mal: 'Si una textura no convence, cambiá la elección en Texturas y volvé a correr el tema.',
    readme: 'escenarios',
  },
}
