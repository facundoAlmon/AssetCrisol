// Extended help for each step (the "More" in the chain): what it does, what to check and what to try if it goes
// wrong, plus the README section. Same keys as ayuda_es.mjs.
export default {
  imagen: {
    hace: 'Makes one candidate image per seed. With a reference, Qwen Image Edit redraws it in the style and keeps the design; without one, Z-Image Turbo (or FLUX.2) makes it up from the description. About 20 s per seed.',
    mirar: 'Pick the one with the right proportions (heads sometimes come out too big), full body, arms away from the body and legs a bit apart: whatever touches in the image gets fused in the mesh. No loose pieces (straps, pouches) and no text.',
    mal: 'Try other seeds (Settings > Image) before changing the description. If the idea is right but has ugly details, use it as a reference and run it through Qwen again asking only for those changes. Squinting eyes: edit only the eyes, don\'t change the seed.',
    readme: '1-image-crisol-imagen',
  },
  vistas: {
    hace: 'Draws the back and both sides of the chosen image with Qwen. The 4-view mesh (Pixal3D) and the UltraTex repaint use them.',
    mirar: 'The back must not repeat what is on the chest (a logo, a light) and each side must face its own edge of the image.',
    mal: 'Delete the bad view (Files: trabajo/imagen/vista_<v>.png) and run the step again: it only redoes the missing ones.',
    readme: 'views-crisol-vistas',
  },
  malla: {
    hace: 'Builds the textured 3D model from the chosen image: Pixal3D (better faces and prints) or TRELLIS.2 (props and vehicles), and repaints it with UltraTex when enabled. 2 to 8 minutes. With candidates, it only makes the missing ones.',
    mirar: 'The model in 3D from every side: the face up close, the back (without the repaint it copies the chest), holes and colors. With candidates, compare the cards and pick one.',
    mal: 'The mesh seed matters a lot: try 2 or 3 before touching anything else (Settings > Mesh, as candidates). Blotchy face with TRELLIS.2: try Pixal3D + UltraTex. Odd eyes: another UltraTex seed.',
    readme: '2-mesh-crisol-malla',
  },
  ultratex: {
    hace: 'Repaints the mesh texture with UltraTex looking at the chosen image (and the back and side views, if any). It does not change the shape.',
    mirar: 'The face up close (the eyes depend on the UltraTex seed) and the back.',
    mal: 'Another UltraTex seed. If the back copies the chest, turn on "Paint the back with the Qwen view" in Settings > Mesh.',
    readme: '2-mesh-crisol-malla',
  },
  guia: {
    hace: 'Renders the mesh from the front and the side with a grid and draws where the joints are (shoulders, elbows, hips, knees...). Only for checking: it changes nothing.',
    mirar: 'Each joint in its place on the body, from the front and the side. Green: deforming bones; orange: controls; yellow: bone heads.',
    mal: 'Run "Detect joints" and check the guide again. On dolls or toys where it fails, place them by hand: Result > Guide > Edit joints.',
    readme: '3a-joint-guide-crisol-guia',
  },
  articulaciones: {
    hace: 'Detects the joints with DWPose on the guide renders and saves them in the character. It goes before the guide and the rig: without it, Blender estimates them by slicing the mesh, and that goes wrong on almost every character. If DWPose finds nobody or the pose is not plausible, it keeps the previous ones.',
    mirar: 'Then the guide: shoulders, elbows, wrists, hips, knees and ankles in their place.',
    mal: 'On dolls, toys and chibis DWPose often finds nobody (the step note says so): the estimated ones stay; if they look wrong in the guide, fix them with Result > Guide > Edit joints.',
    readme: '3a-joint-guide-crisol-guia',
  },
  blender: {
    hace: 'In Blender: gives the mesh a skeleton, works out how much each bone moves each part (weights), builds every animation and renders its side-view frames. It also leaves the animated 3D character (trabajo/animado.glb). Seconds to a minute.',
    mirar: 'The animations in "Animated 3D" (orbiting it, in full screen or frame by frame with the bar) and, after "Sprite sheet", from the side: elbows and knees bending right, nothing stretching oddly, the face looking ahead.',
    mal: 'Face looking up or down: Settings > Model > Head up (negative lifts the face). "Clay" elbows, dragged pieces or arms fused to the body: see the weights section of the README. Wrong joints break everything else: check the guide first.',
    readme: '3b-blender-crisol-blender',
  },
  blender_objeto: {
    hace: 'In Blender: renders the prop in the 8 isometric directions and from the side, with the chosen light and style.',
    mirar: 'The prop upright and whole in every view.',
    mal: 'If it is turned, Settings > Model > Rotation. Missing parts or holes come from the mesh: try another seed.',
    readme: 'props',
  },
  blender_vehiculo: {
    hace: 'In Blender: splits the wheels from the body (so they spin), builds vehiculo.glb and a review sheet. With candidates, one per candidate.',
    mirar: 'The 4 wheels apart and in place, the nose forward and no holes in the body.',
    mal: 'Cars in three-quarter view from above come out better with TRELLIS.2. If a wheel stays stuck, try another mesh seed.',
    readme: 'vehicles',
  },
  sprites: {
    hace: 'Packs the rendered frames into a sprite sheet (13 columns), writes the meta with each animation, the preview gif and the portrait. Applies the style post-processing (color, sharpness, outline).',
    mirar: 'The animation gif: every animation looks right and the character does not jump around between frames.',
    mal: 'Too small or too big: Settings > Sprites > On-screen height. Movement problems come from "Rig and animations".',
    readme: '4-sprites-crisol-sprites',
  },
  retrato: {
    hace: 'Redoes only the portrait (the cropped face) and the front body, without rebuilding the sheet.',
    mirar: 'The face centered and whole in the crop.',
    mal: 'The portrait comes from the chosen image without background; to use the 3D render instead, change it in the json (retrato.fuente).',
    readme: '4-sprites-crisol-sprites',
  },
  iso: {
    hace: 'Renders the animations with an isometric camera (30°) in 8 directions, one sheet per animation. About 25 s.',
    mirar: 'The iso player in the result: try several animations and directions, especially from behind.',
    mal: 'If there are animations you don\'t need (they weigh), pick them in Settings > Isometric animations. What looks wrong in every direction comes from "Rig and animations".',
    readme: 'iso-crisol-iso',
  },
  anclas: {
    hace: 'Without rendering (a few seconds): saves, for every iso frame, where the hands, head, chest and feet are, to attach a sword or a helmet to the character in the game.',
    mirar: 'Nothing to look at: the game uses it. Run it after every "Isometric".',
    mal: 'If the attached item does not follow the hand in the game, run Isometric and Anchors again with the same json.',
    readme: 'anchors-crisol-anclas',
  },
  revisar: {
    hace: 'Builds a check sheet with the head from the side, the bent elbows, the iso walk from front and back, the key poses and the "inside-out" view: what shows of the inside of the mesh, in magenta.',
    mirar: 'The last thing to check before using the character. It warns if any pose goes over 3 % inside-out (an open mouth always shows and is not a problem).',
    mal: 'Large magenta patches: holes or clothes that pass through when animating. Try another mesh or, if they are flipped faces, the normals option in the README.',
    readme: 'what-to-check-at-each-step-humanoid-recipe',
  },
  godot: {
    hace: 'Exports scenes and resources ready for a Godot project (the sprite with its animations and its script), in the asset\'s godot/ folder.',
    mirar: 'Nothing to look at: copy the folder into the project. It never installs into a project by itself.',
    mal: 'If you changed animations, redo Sprite sheet and Isometric before exporting.',
    readme: '5-godot-crisol-godot',
  },
  comparar: {
    hace: 'Builds a sheet with every mesh candidate already made, rendered the same way, and the views for each card to choose from.',
    mirar: 'The cards in Your call: face, back and holes of each candidate.',
    mal: 'If a candidate is missing, it is not made yet: run 3D mesh.',
    readme: '2-mesh-crisol-malla',
  },
  texturas: {
    hace: 'Makes candidates for each tileable texture of the scene (floor, path, wall, backdrop), one per seed.',
    mirar: 'They tile without seams and don\'t look like noise from afar: large shapes and little detail work best.',
    mal: 'Other seeds or a simpler description (Settings > Scene). "Only" redoes some of the textures.',
    readme: 'scenery',
  },
  tema: {
    hace: 'With the chosen textures, builds the final tileables, the theme colors and a preview of the scene.',
    mirar: 'The preview: floor, path and wall go together and can be told apart.',
    mal: 'If a texture doesn\'t work, change the choice in Textures and run the theme again.',
    readme: 'scenery',
  },
}
