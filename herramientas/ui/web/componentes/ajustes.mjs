// Ajustes de un asset sin tocar el json: los campos comunes por tipo (README > personaje.json) y los métodos de
// animación. El json completo queda como modo avanzado, con un diff antes de guardar. Las elecciones (imagen, malla,
// texturas) no se cambian acá: van por Decidir.
import { html, useState, useEffect, useMemo, api, t, aviso, Icono, Cargando } from '../comunes.mjs'

const leer = (obj, clave) => clave.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj)

// tipos de campo: texto, area, numero, entero, seeds, bool, select (opciones), animaciones
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
  if (!leer(j, 'imagen.referencia')) {
    lista.push({ g: 'imagen', clave: 'imagen.motor', tipo: 'select', etiqueta: 'aj.motor_imagen',
      opciones: [['', t('aj.defecto')], ['zimage', 'Z-Image Turbo'], ['flux2', 'FLUX.2 Dev']] })
  }
  if (!m.candidatos) {
    lista.push({ g: 'malla', clave: 'malla.motor', tipo: 'select', etiqueta: 'aj.motor_malla', opciones: [['pixal3d', 'Pixal3D'], ['trellis2', 'TRELLIS.2']] })
  }
  lista.push({ g: 'malla', clave: 'malla.seed', tipo: 'entero', etiqueta: 'aj.seed_malla', ayuda: 'aj.seed_malla_ayuda' })
  if (ut) {
    lista.push({ g: 'malla', clave: 'malla.ultratex.seed', tipo: 'entero', etiqueta: 'aj.seed_ultratex', ayuda: 'aj.seed_ultratex_ayuda' },
      { g: 'malla', clave: 'malla.ultratex.espalda', tipo: 'bool', etiqueta: 'aj.espalda' },
      { g: 'malla', clave: 'malla.ultratex.costados', tipo: 'bool', etiqueta: 'aj.costados' })
  }
  lista.push({ g: 'modelo', clave: 'modelo.altura', tipo: 'numero', paso: 0.01, etiqueta: 'aj.altura' })
  if (d.tipo === 'personaje') {
    lista.push({ g: 'modelo', clave: 'animacion.cabeza_arriba_grados', tipo: 'numero', paso: 1, etiqueta: 'aj.cabeza', ayuda: 'aj.cabeza_ayuda' },
      { g: 'sprites', clave: 'sprites.alto_en_pantalla_px', tipo: 'entero', nulo: true, etiqueta: 'aj.alto_px', ayuda: 'aj.alto_px_ayuda' },
      { g: 'animaciones', clave: 'isometrico.animaciones', tipo: 'animaciones', etiqueta: 'aj.iso_anims', ayuda: 'aj.iso_anims_ayuda', animaciones })
  } else {
    lista.push({ g: 'modelo', clave: 'modelo.giro_grados', tipo: 'numero', paso: 1, etiqueta: 'aj.giro' })
  }
  return lista
}

function Campo({ c, valor, cambiar }) {
  const etiqueta = c.crudo ? c.etiqueta : t(c.etiqueta)
  const ayuda = c.ayuda && html`<small>${t(c.ayuda)}</small>`
  const id = 'aj-' + c.clave.replaceAll('.', '-')
  if (c.tipo === 'bool') {
    return html`<label class="casilla"><input type="checkbox" checked=${!!valor} onChange=${e => cambiar(e.target.checked)} />${etiqueta}</label>`
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
  let control
  if (c.tipo === 'area') {
    control = html`<textarea class="entrada" id=${id} lang=${c.ingles ? 'en' : null} value=${valor ?? ''} onInput=${e => cambiar(e.target.value || null)} />`
  } else if (c.tipo === 'select') {
    control = html`<select class="entrada" id=${id} value=${valor ?? ''} onChange=${e => cambiar(e.target.value || null)}>
      ${c.opciones.map(([v, n]) => html`<option value=${v}>${n}</option>`)}</select>`
  } else if (c.tipo === 'seeds') {
    control = html`<input class="entrada mono" id=${id} inputmode="numeric" value=${(valor || []).join(', ')}
      onChange=${e => cambiar(e.target.value.split(/[ ,;]+/).filter(Boolean).map(Number).filter(Number.isFinite))} />`
  } else {
    control = html`<input class="entrada" id=${id} type="number" step=${c.tipo === 'entero' ? 1 : c.paso} value=${valor ?? ''}
      onInput=${e => cambiar(e.target.value === '' ? (c.nulo ? null : undefined) : Number(e.target.value))} />`
  }
  return html`<label class="campo" for=${id}><span>${etiqueta}</span>${control}${ayuda}</label>`
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
  useEffect(() => {
    Promise.all([api('estilos'), api('animaciones')]).then(([estilos, animaciones]) => setCat({ estilos, animaciones }), e => aviso(e.message, 'error'))
  }, [])
  useEffect(() => setCambios({}), [d])
  if (avanzado) return html`<${Avanzado} d=${d} recargar=${recargar} volver=${() => setAvanzado(false)} />`
  if (!cat) return html`<${Cargando} />`
  const lista = campos(d, cat.estilos, cat.animaciones)
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
    ${grupos.map(g => html`<section class="grupo-ajustes" key=${g}>
      <h3>${t('aj.g.' + g)}</h3>
      <div class="fila">${lista.filter(c => c.g === g).map(c => html`<div key=${c.clave}
          style=${c.tipo === 'area' || c.tipo === 'animaciones' ? 'grid-column:1/-1' : ''}>
        <${Campo} c=${c} valor=${valor(c)} cambiar=${v => setCambios({ ...cambios, [c.clave]: v })} /></div>`)}</div>
      ${g === 'animaciones' && html`<${Metodos} d=${d} />`}
    </section>`)}
    <div class="barra-guardar">
      <button class="boton primario" disabled=${!sucio || guardando} onClick=${guardar}><${Icono} n="check" />${t('aj.guardar')}</button>
      ${sucio && html`<button class="boton fantasma" onClick=${() => setCambios({})}>${t('aj.descartar')}</button>`}
      <button class="boton fantasma" style="margin-left:auto" onClick=${() => setAvanzado(true)}>${t('aj.avanzado')}</button>
    </div>
  </div>`
}
