// Ajustes de un asset sin tocar el json: los campos comunes por tipo (README > personaje.json) y los métodos de
// animación. El json completo queda como modo avanzado, con un diff antes de guardar. Las elecciones (imagen, malla,
// texturas) no se cambian acá: van por Decidir.
import { html, useState, useEffect, useMemo, api, t, aviso, Icono, Cargando, Plegable, nombrePaso } from '../comunes.mjs'
import { Candidatos, CLAVES_CANDIDATOS } from './candidatos.mjs'

const leer = (obj, clave) => clave.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj)

// la superresolución: se renderiza N veces más grande y el juego lo reduce (más nítido, más pesado)
const SUPER = [1, 2, 3, 4].map(n => [n, `${n}×`])

// tipos de campo: texto, area, numero, entero, seeds, bool, select (opciones; numerico: el valor es un número),
// animaciones, resolucion (el texto con el tamaño que sale), parte_prompt (pisa una parte del prompt del estilo),
// prompt_armado (el prompt que sale con lo guardado)
function campos(d, estilos, animaciones) {
  const j = d.json
  const estilo = { g: 'estilo', clave: 'estilo', tipo: 'select', etiqueta: 'aj.estilo', ayuda: 'aj.estilo_ayuda',
    opciones: [['', t('aj.defecto') + ` (${estilos.defecto})`], ...estilos.estilos.map(e => [e.id, e.id])] }
  if (d.tipo === 'escenario') {
    const tex = Object.keys(j.texturas || {}).flatMap(k => [
      { g: 'escenario', clave: `texturas.${k}.descripcion`, tipo: 'area', etiqueta: t('aj.textura', { k }), crudo: true, ingles: true },
      { g: 'escenario', clave: `texturas.${k}.seeds`, tipo: 'seeds', etiqueta: 'aj.seeds', ayuda: 'aj.seeds_ayuda' },
    ])
    return [estilo,
      { g: 'escenario', clave: 'motor', tipo: 'select', etiqueta: 'aj.motor_escenario', opciones: [['sdxl', 'SDXL'], ['zimage', 'Z-Image Turbo'], ['flux', 'FLUX.2']] },
      ...tex,
      { g: 'escenario', clave: 'tema.px', tipo: 'entero', etiqueta: 'aj.tema_px' }]
  }
  const m = j.malla || {}
  const ut = m.ultratex && typeof m.ultratex === 'object'
  const lista = [estilo,
    { g: 'imagen', clave: 'imagen.descripcion', tipo: 'area', etiqueta: 'aj.descripcion', ayuda: 'nuevo.descripcion_ayuda', ingles: true },
    { g: 'imagen', clave: 'imagen.seeds', tipo: 'seeds', etiqueta: 'aj.seeds', ayuda: 'aj.seeds_ayuda' }]
  // las partes del prompt que pone el estilo, pisables por asset (bloque `prompt` del json; con un imagen.prompt a mano
  // sin descripcion el estilo no entra en el prompt)
  if (d.prompt_estilo && (leer(j, 'imagen.descripcion') || !leer(j, 'imagen.prompt'))) {
    const partes = [d.tipo === 'personaje' ? 'render_personaje' : 'render_objeto', 'tema', 'paleta', 'extra']
    lista.push(...partes.map(k => ({ g: 'prompt', clave: `prompt.${k}`, tipo: 'parte_prompt', etiqueta: 'aj.prompt_' + k.replace(/_.*/, ''),
      ayuda: 'aj.prompt_' + k.replace(/_.*/, '') + '_ayuda', heredado: d.prompt_estilo[k] || '' })),
    { g: 'prompt', clave: 'prompt_imagen', tipo: 'prompt_armado' })
  }
  if (!leer(j, 'imagen.referencia')) {
    lista.push({ g: 'imagen', clave: 'imagen.motor', tipo: 'select', etiqueta: 'aj.motor_imagen',
      opciones: [['', t('aj.defecto')], ['zimage', 'Z-Image Turbo'], ['flux2', 'FLUX.2 Dev']] })
  }
  // motor, seed, resolución y UltraTex del principal y de los candidatos: el editor de candidatos (candidatos.mjs)
  lista.push({ g: 'malla', clave: 'malla.candidatos', tipo: 'candidatos' })
  if (ut) {
    lista.push({ g: 'malla', clave: 'malla.ultratex.espalda', tipo: 'bool', etiqueta: 'aj.espalda' },
      { g: 'malla', clave: 'malla.ultratex.costados', tipo: 'bool', etiqueta: 'aj.costados' })
  }
  lista.push({ g: 'modelo', clave: 'modelo.altura', tipo: 'numero', paso: 0.01, etiqueta: 'aj.altura' })
  const e = d.escala || {}
  if (d.tipo === 'personaje') {
    lista.push({ g: 'modelo', clave: 'animacion.cabeza_arriba_grados', tipo: 'numero', paso: 1, etiqueta: 'aj.cabeza', ayuda: 'aj.cabeza_ayuda' },
      { g: 'sprites', clave: 'sprites.alto_en_pantalla_px', tipo: 'entero', nulo: true, etiqueta: 'aj.alto_px', ayuda: 'aj.alto_px_ayuda',
        auto: e.altura && e.px_por_unidad ? Math.round(e.altura * e.px_por_unidad) : null },
      { g: 'sprites', clave: 'sprites.superresolucion', tipo: 'select', numerico: true, etiqueta: 'aj.superres', ayuda: 'aj.superres_ayuda',
        opciones: [['', t('aj.defecto') + ' (3×)'], ...SUPER] },
      { g: 'sprites', clave: 'isometrico.baldosa_px', tipo: 'entero', nulo: true, etiqueta: 'aj.baldosa', ayuda: 'aj.baldosa_ayuda', auto: e.baldosa_px },
      { g: 'sprites', clave: 'isometrico.superresolucion', tipo: 'select', numerico: true, etiqueta: 'aj.superres_iso',
        opciones: [['', t('aj.defecto') + ' (2×)'], ...SUPER] },
      { g: 'sprites', clave: 'resolucion', tipo: 'resolucion' },
      { g: 'animaciones', clave: 'isometrico.animaciones', tipo: 'animaciones', etiqueta: 'aj.iso_anims', ayuda: 'aj.iso_anims_ayuda', animaciones })
  } else {
    lista.push({ g: 'modelo', clave: 'modelo.giro_grados', tipo: 'numero', paso: 1, etiqueta: 'aj.giro' },
      { g: 'sprites', clave: 'isometrico.baldosa_px', tipo: 'entero', nulo: true, etiqueta: 'aj.baldosa', ayuda: 'aj.baldosa_ayuda', auto: e.baldosa_px },
      { g: 'sprites', clave: 'isometrico.superresolucion', tipo: 'select', numerico: true, etiqueta: 'aj.superres_iso',
        opciones: [['', t('aj.defecto') + ' (2×)'], ...SUPER] },
      { g: 'sprites', clave: 'lateral.px_por_unidad', tipo: 'numero', paso: 0.01, nulo: true, etiqueta: 'aj.lateral_px', ayuda: 'aj.lateral_px_ayuda', auto: e.px_por_unidad },
      { g: 'sprites', clave: 'lateral.superresolucion', tipo: 'select', numerico: true, etiqueta: 'aj.superres_lateral',
        opciones: [['', t('aj.defecto') + ' (3×)'], ...SUPER] },
      { g: 'sprites', clave: 'resolucion', tipo: 'resolucion' })
  }
  // el modelo para un juego 3D (trabajo/tiempo_real/, paso blender): tiempo_real false lo apaga
  const cuadrupedo = leer(j, 'modelo.esqueleto') === 'cuadrupedo'
  // sin bloque propio vale el de config.json (false = apagado para todos)
  const general = d.tiempo_real_general
  const activo = (j.tiempo_real == null ? general : j.tiempo_real) !== false
  lista.push({ g: 'juego3d', clave: 'tiempo_real', tipo: 'juego3d_activo', etiqueta: 'aj.j3d_activo',
    ayuda: general === false ? 'aj.j3d_general_apagado' : 'aj.j3d_activo_ayuda', activo })
  if (activo) {
    const lods = d.tipo === 'personaje'
      ? { alta: [40000, 20000, 10000], liviana: [10000, 5000, 2000] }
      : { alta: [20000, 10000, 4000], liviana: [5000, 2500, 1000] }
    lista.push(
      { g: 'juego3d', clave: 'tiempo_real.lods', tipo: 'select', etiqueta: 'aj.j3d_calidad', ayuda: 'aj.j3d_calidad_ayuda',
        valores: lods, opciones: [['', t('aj.j3d_media', { c: d.tipo === 'personaje' ? '20k/10k/5k' : '10k/5k/2k' })],
          ['alta', t('aj.j3d_alta', { c: lods.alta.map(x => x / 1000 + 'k').join('/') })],
          ['liviana', t('aj.j3d_liviana', { c: lods.liviana.map(x => x / 1000 + 'k').join('/') })]] },
      { g: 'juego3d', clave: 'tiempo_real.textura_px', tipo: 'select', numerico: true, etiqueta: 'aj.j3d_textura',
        opciones: [['', t('aj.defecto') + ' (2048 px)'], [1024, '1024 px'], [4096, '4096 px']] },
      { g: 'juego3d', clave: 'tiempo_real.mapas', tipo: 'select', etiqueta: 'aj.j3d_mapas', ayuda: 'aj.j3d_mapas_ayuda',
        valores: { ao: ['normal', 'orm', 'ao'], color: [] },
        opciones: [['', t('aj.j3d_mapas_defecto')], ['ao', t('aj.j3d_mapas_ao')], ['color', t('aj.j3d_mapas_color')]] })
    if (d.tipo === 'personaje' && !cuadrupedo) {
      lista.push({ g: 'juego3d', clave: 'tiempo_real.huesos', tipo: 'select', etiqueta: 'aj.j3d_huesos', ayuda: 'aj.j3d_huesos_ayuda',
        opciones: [['', t('aj.defecto') + ' (Mixamo)'], ['godot', 'Godot (SkeletonProfileHumanoid)'], ['crisol', 'AssetCrisol']] })
    }
  }
  return lista
}

const aSeeds = texto => texto.split(/[ ,;]+/).filter(Boolean).map(Number).filter(Number.isFinite)

// el texto propio (con onInput y no onChange: si no, el botón de guardar seguía en gris hasta salir del campo) y no
// el de la lista, para no reformatear "1, " mientras se escribe; se rehace si la lista cambia desde afuera
function Seeds({ id, valor, cambiar }) {
  const lista = (valor || []).join(', ')
  const [texto, setTexto] = useState(lista)
  useEffect(() => { if (aSeeds(texto).join(', ') !== lista) setTexto(lista) }, [lista])
  return html`<input class="entrada mono" id=${id} inputmode="numeric" value=${texto}
    onInput=${e => { setTexto(e.target.value); cambiar(aSeeds(e.target.value)) }} />`
}

function Campo({ c, valor, cambiar }) {
  const etiqueta = c.crudo ? c.etiqueta : t(c.etiqueta)
  const ayuda = c.ayuda && html`<small>${t(c.ayuda)}</small>`
  const id = 'aj-' + c.clave.replaceAll('.', '-')
  if (c.tipo === 'bool') {
    return html`<label class="casilla"><input type="checkbox" checked=${!!valor} onChange=${e => cambiar(e.target.checked)} />${etiqueta}</label>`
  }
  if (c.tipo === 'juego3d_activo') {   // tiempo_real: false = apagado; prenderlo deja lo que tenía (o el por defecto)
    return html`<div class="campo"><label class="casilla"><input type="checkbox" checked=${c.activo}
      onChange=${e => cambiar(e.target.checked ? (c.previo && typeof c.previo === 'object' ? c.previo : {}) : false)} />${etiqueta}</label>${ayuda}</div>`
  }
  if (c.tipo === 'animaciones') {
    const marcadas = new Set(valor || [])
    return html`<fieldset class="campo" style="border:0;padding:0;margin:0"><legend style="font-weight:600;font-size:14px;margin-bottom:6px">${etiqueta}</legend>
      ${ayuda}<div class="animaciones-ajuste">${c.animaciones.map(a => html`<label class="casilla" key=${a.id}>
        <input type="checkbox" checked=${marcadas.has(a.id)} onChange=${e => {
          const s = new Set(marcadas); e.target.checked ? s.add(a.id) : s.delete(a.id)
          cambiar(s.size ? c.animaciones.map(x => x.id).filter(x => s.has(x)) : null)
        }} />${a.id} <span class="tenue chico">${a.godot}</span></label>`)}</div></fieldset>`
  }
  if (c.tipo === 'parte_prompt') {
    // null = el del estilo (de placeholder); "" = sin esta parte; texto = el propio del asset
    const propio = valor != null
    return html`<div class="campo"><label for=${id}>${etiqueta}
        <span class="tenue chico"> · ${t(valor === '' ? 'aj.prompt_sacado' : propio ? 'aj.prompt_propio' : 'aj.prompt_heredado')}</span></label>
      <textarea class="entrada" id=${id} lang="en" style="min-height:64px" value=${valor ?? ''}
        placeholder=${valor === '' ? t('aj.prompt_vacio') : c.heredado}
        onInput=${e => cambiar(e.target.value === '' ? null : e.target.value)} />
      ${ayuda}
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">
        ${!propio && c.heredado && html`<button class="boton fantasma chico" onClick=${() => cambiar(c.heredado)}>${t('aj.prompt_editar')}</button>`}
        ${valor !== '' && c.heredado && html`<button class="boton fantasma chico" onClick=${() => cambiar('')}>${t('aj.prompt_sacar')}</button>`}
        ${propio && html`<button class="boton fantasma chico" onClick=${() => cambiar(null)}>${t('aj.prompt_volver')}</button>`}
      </div></div>`
  }
  let control
  if (c.tipo === 'area') {
    control = html`<textarea class="entrada" id=${id} lang=${c.ingles ? 'en' : null} value=${valor ?? ''} onInput=${e => cambiar(e.target.value || null)} />`
  } else if (c.tipo === 'select' && c.valores) {   // opciones con nombre para valores que no son texto (listas)
    const clave = Object.keys(c.valores).find(k => JSON.stringify(c.valores[k]) === JSON.stringify(valor)) ?? ''
    control = html`<select class="entrada" id=${id} value=${clave} onChange=${e => cambiar(e.target.value === '' ? null : c.valores[e.target.value])}>
      ${c.opciones.map(([v, n]) => html`<option value=${v}>${n}</option>`)}</select>`
  } else if (c.tipo === 'select') {
    control = html`<select class="entrada" id=${id} value=${valor ?? ''} onChange=${e => cambiar(e.target.value === '' ? null : c.numerico ? Number(e.target.value) : e.target.value)}>
      ${c.opciones.map(([v, n]) => html`<option value=${v}>${n}</option>`)}</select>`
  } else if (c.tipo === 'seeds') {
    control = html`<${Seeds} id=${id} valor=${valor} cambiar=${cambiar} />`
  } else {
    control = html`<input class="entrada" id=${id} type="number" step=${c.tipo === 'entero' ? 1 : c.paso} value=${valor ?? ''}
      placeholder=${c.auto != null ? t('aj.auto', { v: c.auto }) : null}
      onInput=${e => cambiar(e.target.value === '' ? (c.nulo ? null : undefined) : Number(e.target.value))} />`
  }
  return html`<label class="campo" for=${id}><span>${etiqueta}</span>${control}${ayuda}</label>`
}

// a qué tamaño sale cada cuadro con los valores de ahora (también los sin guardar): en el juego y renderizado
function Resolucion({ d, valor }) {
  const e = d.escala || {}
  if (!e.altura) return null
  const iso = (valor('isometrico.baldosa_px') ?? e.baldosa_px) / Math.SQRT2   // px de pantalla por unidad en iso
  const sIso = valor('isometrico.superresolucion') ?? 2
  const altoIso = Math.round(e.altura * iso * Math.cos(Math.PI / 6))           // de pie, cámara a 30°
  let texto
  if (d.tipo === 'personaje') {
    const alto = valor('sprites.alto_en_pantalla_px') ?? Math.round(e.altura * e.px_por_unidad)
    const s = valor('sprites.superresolucion') ?? 3
    texto = t('aj.res_personaje', { a: alto, ar: alto * s, s, i: altoIso, ir: altoIso * sIso, si: sIso })
  } else {
    const ppu = valor('lateral.px_por_unidad') ?? e.px_por_unidad
    const s = valor('lateral.superresolucion') ?? 3
    const a = Math.round(e.altura * ppu)
    texto = t('aj.res_objeto', { a, ar: a * s, s, i: altoIso, ir: altoIso * sIso, si: sIso })
  }
  return html`<p class="aviso" style="margin:0"><${Icono} n="info" /><span>${texto} ${t('aj.res_rehacer', { p: nombrePaso('blender', d.tipo) })}</span></p>`
}

function Metodos({ d }) {
  const [lista, setLista] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const cargar = () => api(`assets/${encodeURIComponent(d.nombre)}/metodos`).then(setLista, e => aviso(e.message, 'error'))
  useEffect(() => { cargar() }, [d.nombre])
  if (!lista) return html`<${Cargando} />`
  const cambiar = async (anim, metodo) => {
    setGuardando(true)
    try {
      setLista(await api(`assets/${encodeURIComponent(d.nombre)}/metodos`, { metodo: 'POST', cuerpo: { cambios: { [anim]: metodo } } }))
      aviso(t('aj.guardado'))
    } catch (e) { aviso(e.message, 'error') }
    setGuardando(false)
  }
  return html`<div class="campo"><span>${t('paso.metodo')}</span><small>${t('aj.metodos_ayuda')}</small>
    <div class="animaciones-ajuste" style="margin-top:6px">${lista.map(a => {
      const hayKimodo = a.metodo === 'kimodo' || a.nota.startsWith('kimodo')
      return html`<div class="anim" key=${a.animacion} title=${a.nota}>
        <span>${a.animacion}</span>
        <div class="segmentos" role="group" aria-label=${a.animacion}>
          ${['procedural', 'kimodo'].map(m => html`<button aria-pressed=${a.metodo === m} disabled=${guardando || (m === 'kimodo' && !hayKimodo)}
            onClick=${() => a.metodo !== m && cambiar(a.animacion, m)}>${m}</button>`)}
        </div></div>`
    })}</div></div>`
}

function diffLineas(a, b) {
  // diff simple por líneas (LCS): alcanza para un json de cientos de líneas
  const x = a.split('\n'), y = b.split('\n')
  const n = x.length, m = y.length
  const L = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1))
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = x[i] === y[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1])
  const out = []
  let i = 0, j = 0
  while (i < n || j < m) {
    if (i < n && j < m && x[i] === y[j]) { i++; j++ }
    else if (j < m && (i >= n || L[i][j + 1] >= L[i + 1][j])) out.push(['mas', y[j++]])
    else out.push(['menos', x[i++]])
  }
  return out
}

function Avanzado({ d, recargar, volver }) {
  const original = JSON.stringify(d.json, null, 2)
  const [texto, setTexto] = useState(original)
  const [revisar, setRevisar] = useState(false)
  let error = null, nuevo = null
  try { nuevo = JSON.parse(texto) } catch (e) { error = e.message }
  const cambios = useMemo(() => (revisar && nuevo ? diffLineas(original, JSON.stringify(nuevo, null, 2)) : []), [revisar, texto])
  const guardar = async () => {
    try {
      await api(`assets/${encodeURIComponent(d.nombre)}/json`, { metodo: 'PUT', cuerpo: { json: nuevo } })
      aviso(t('aj.guardado'))
      recargar()
      volver()
    } catch (e) { aviso(e.message, 'error') }
  }
  return html`<div style="display:grid;gap:12px">
    <textarea class="entrada mono" style="min-height:420px" spellcheck="false" aria-invalid=${!!error} value=${texto}
      onInput=${e => { setTexto(e.target.value); setRevisar(false) }} aria-label=${d.archivo_json} />
    ${error && html`<p style="color:var(--error)" class="chico">${t('aj.json_mal', { e: error })}</p>`}
    ${revisar && html`<div class="panel diff"><h3 style="margin-bottom:8px">${t('aj.revisar_diff')}</h3>
      <pre class="mono" style="margin:0;white-space:pre-wrap">${cambios.length ? cambios.map(([c, l]) => html`<div class=${c}>${c === 'mas' ? '+ ' : '- '}${l}</div>`) : t('aj.sin_cambios')}</pre></div>`}
    <div class="barra-guardar">
      ${revisar
        ? html`<button class="boton primario" disabled=${!!error || !cambios.length} onClick=${guardar}>${t('aj.guardar')}</button>`
        : html`<button class="boton primario" disabled=${!!error || texto === original} onClick=${() => setRevisar(true)}>${t('aj.revisar_diff')}</button>`}
      <button class="boton fantasma" onClick=${volver}>${t('aj.basico')}</button>
    </div>
  </div>`
}

export function Ajustes({ d, recargar }) {
  const [cat, setCat] = useState(null)
  const [cambios, setCambios] = useState({})
  const [avanzado, setAvanzado] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [errorCand, setErrorCand] = useState(null)
  useEffect(() => {
    Promise.all([api('estilos'), api('animaciones')]).then(([estilos, animaciones]) => setCat({ estilos, animaciones }), e => aviso(e.message, 'error'))
  }, [])
  useEffect(() => setCambios({}), [d])
  if (avanzado) return html`<${Avanzado} d=${d} recargar=${recargar} volver=${() => setAvanzado(false)} />`
  if (!cat) return html`<${Cargando} />`
  // Juego 3D: los campos según la casilla de ahora (también sin guardar)
  const vista = 'tiempo_real' in cambios ? { ...d, json: { ...d.json, tiempo_real: cambios.tiempo_real } } : d
  const lista = campos(vista, cat.estilos, cat.animaciones)
  const grupos = [...new Set(lista.map(c => c.g))]
  const valor = c => (c.clave in cambios ? cambios[c.clave] : leer(d.json, c.clave))
  const sucio = Object.keys(cambios).length > 0
  const guardar = async () => {
    setGuardando(true)
    try {
      const limpio = Object.fromEntries(Object.entries(cambios).filter(([, v]) => v !== undefined))
      await api(`assets/${encodeURIComponent(d.nombre)}/json`, { metodo: 'PATCH', cuerpo: { cambios: limpio } })
      aviso(t('aj.guardado'))
      recargar()
    } catch (e) { aviso(e.message, 'error') }
    setGuardando(false)
  }
  return html`<div style="display:grid;gap:26px">
    ${grupos.map(g => html`<section class="grupo-ajustes" key=${g}><${Plegable} titulo=${t('aj.g.' + g)} nivel="h3">
      <div class="fila">${lista.filter(c => c.g === g).map(c => html`<div key=${c.clave}
          style=${['area', 'animaciones', 'candidatos', 'resolucion', 'parte_prompt', 'prompt_armado'].includes(c.tipo) ? 'grid-column:1/-1' : ''}>
        ${c.tipo === 'resolucion' ? html`<${Resolucion} d=${d} valor=${k => valor({ clave: k })} />`
          : c.tipo === 'prompt_armado' ? d.prompt_imagen && html`<div class="campo"><span>${t('aj.prompt_armado')}</span>
              <small>${t('aj.prompt_armado_ayuda')}</small><pre class="mono chico" style="white-space:pre-wrap;margin:4px 0 0">${d.prompt_imagen}</pre></div>`
          : c.tipo === 'candidatos'
          ? html`<${Candidatos} key=${d.modificado + JSON.stringify(d.json.malla || {})} d=${d} onCambio=${(patch, error) => {
              setCambios(prev => ({ ...Object.fromEntries(Object.entries(prev).filter(([k]) => !CLAVES_CANDIDATOS.includes(k))), ...patch }))
              setErrorCand(error)
            }} />`
          : html`<${Campo} c=${c.tipo === 'juego3d_activo' ? { ...c, previo: d.json.tiempo_real } : c} valor=${valor(c)} cambiar=${v => setCambios(
              c.tipo === 'juego3d_activo'   // apagado: las subclaves no van (tiempo_real deja de ser un bloque)
                ? { ...Object.fromEntries(Object.entries(cambios).filter(([k]) => !k.startsWith('tiempo_real.'))), [c.clave]: v }
                : { ...cambios, [c.clave]: v })} />`}</div>`)}</div>
      ${g === 'animaciones' && html`<${Metodos} d=${d} />`}
    <//></section>`)}
    <div class="barra-guardar">
      <button class="boton primario" disabled=${!sucio || guardando || !!errorCand} title=${errorCand || ''} onClick=${guardar}><${Icono} n="check" />${t('aj.guardar')}</button>
      ${sucio && html`<button class="boton fantasma" onClick=${() => setCambios({})}>${t('aj.descartar')}</button>`}
      <button class="boton fantasma" style="margin-left:auto" onClick=${() => setAvanzado(true)}>${t('aj.avanzado')}</button>
    </div>
  </div>`
}
