// Editor de los candidatos de malla (Ajustes > Malla): el principal (`malla.motor` y sus claves; su nombre es el
// motor) y los de `malla.candidatos` ({nombre: claves que pisan}; `desde: <otro>` reusa la malla de ese otro y solo
// la repinta con UltraTex). Ver pipeline.candidatos_malla. Escribe por el PATCH de Ajustes, nunca `malla.elegida`:
// esa la elige la persona en "Te toca elegir". `malla` no rehace un candidato que ya tiene trabajo/malla_<c>/: para
// que tome un cambio hay que borrarlo ("Rehacer este candidato").
import { html, useState, useEffect, api, t, aviso, Icono, Chip, encolar } from '../comunes.mjs'

const NOMBRE = /^[a-z0-9][a-z0-9_]{0,31}$/
const MOTORES = [['trellis2', 'TRELLIS.2'], ['pixal3d', 'Pixal3D']]
const RESOLUCIONES = { trellis2: [512, 1024], pixal3d: [1024, 1536] }   // Pixal3D a 512 falla; TRELLIS.2 a 1536 no entra
// las claves de malla que escribe este editor (Ajustes las reemplaza en bloque en cada cambio)
export const CLAVES_CANDIDATOS = ['malla.motor', 'malla.seed', 'malla.resolucion', 'malla.ultratex', 'malla.ultratex.seed', 'malla.candidatos']

const esDict = x => x && typeof x === 'object' && !Array.isArray(x)
const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b)
let ids = 0

// resolución por defecto de cada motor, como la leen pipeline.generar_malla (TRELLIS.2: 512 en objetos, 1024 en
// personajes) y generar_malla_pixal3d.py (1536)
const resolucionPorDefecto = (motor, tipo) => (motor === 'pixal3d' ? 1536 : tipo === 'personaje' ? 1024 : 512)

function desdeJson(m, tipo) {
  const motor = m.motor || 'trellis2'
  const utBase = esDict(m.ultratex) ? m.ultratex : {}
  const principal = { id: 'principal', principal: true, tipo: 'motor', motor, seed: m.seed ?? 1234,
    resolucion: m.resolucion ?? resolucionPorDefecto(motor, tipo), ut: !!m.ultratex, utSeed: utBase.seed ?? 1 }
  const extra = Object.entries(m.candidatos || {}).map(([nombre, c]) => {
    const cm = c.motor || motor
    return {
      id: 'c' + ++ids, nombre, orig: c,
      tipo: c.desde ? 'ultratex' : 'motor', desde: c.desde || motor,
      // lo que no pisa lo hereda del principal (dict(base, **c) en pipeline.candidatos_malla)
      motor: cm, seed: c.seed ?? principal.seed,
      resolucion: c.resolucion ?? ('resolucion' in m ? m.resolucion : resolucionPorDefecto(cm, tipo)),
      ut: 'ultratex' in c ? !!c.ultratex : !!m.ultratex,
      utSeed: (esDict(c.ultratex) ? c.ultratex.seed : undefined) ?? utBase.seed ?? 1,
    }
  })
  return [principal, ...extra].map(f => ({ ...f, ini: { ...f } }))   // ini: como vino del json (para el diff)
}

const nombreDe = f => (f.principal ? f.motor : f.nombre)
const cambio = (f, k) => !f.ini || f[k] !== f.ini[k]

// un candidato con lo que cambió en la UI aplicado sobre su dict original (lo que no se tocó queda como estaba)
function candidato(f, p, m, tipoAsset) {
  // lo que heredaría del principal tal como queda después de guardar
  const resPrincipal = 'resolucion' in m || cambio(p, 'resolucion')
  const heredado = { motor: p.motor, seed: p.seed, resolucion: resPrincipal ? p.resolucion : resolucionPorDefecto(f.motor, tipoAsset) }
  const c = { ...(f.orig || {}) }
  const utDict = () => ({ ...(esDict(c.ultratex) ? c.ultratex : { giro: 45 }), seed: f.utSeed })
  if (f.tipo === 'ultratex') {
    if (cambio(f, 'tipo')) { delete c.motor; delete c.seed; delete c.resolucion; delete c.caras }
    if (cambio(f, 'desde') || cambio(f, 'tipo')) c.desde = f.desde
    if (cambio(f, 'utSeed') || cambio(f, 'tipo') || !c.ultratex) c.ultratex = utDict()
    return c
  }
  if (cambio(f, 'tipo')) delete c.desde
  for (const k of ['motor', 'seed', 'resolucion']) {
    if (cambio(f, k) || cambio(f, 'tipo') || (!(k in c) && f[k] !== heredado[k])) c[k] = f[k]
  }
  // Pixal3D con pocas caras sale astillado (los candidatos heredan `caras` del principal)
  if (c.motor === 'pixal3d' && cambio(f, 'motor') && !('caras' in c) && (m.caras || 0) < 100000) c.caras = 200000
  if (cambio(f, 'ut') || cambio(f, 'utSeed') || cambio(f, 'tipo') || p.ut !== p.ini.ut) {
    if (f.ut) c.ultratex = utDict()
    else if (p.ut) c.ultratex = false          // si no, heredaría la del principal
    else delete c.ultratex
  }
  return c
}

// filas -> claves para el PATCH (solo las que cambian respecto del json) y el error que impide guardar
function aJson(filas, m, tipoAsset) {
  const [p, ...extra] = filas
  const patch = {}
  if (cambio(p, 'motor')) patch['malla.motor'] = p.motor
  if (cambio(p, 'seed')) patch['malla.seed'] = p.seed
  if (cambio(p, 'resolucion') || (cambio(p, 'motor') && 'resolucion' in m)) patch['malla.resolucion'] = p.resolucion
  if (p.ut && !m.ultratex) patch['malla.ultratex'] = { seed: p.utSeed }
  else if (p.ut && cambio(p, 'utSeed')) {
    if (esDict(m.ultratex)) patch['malla.ultratex.seed'] = p.utSeed
    else patch['malla.ultratex'] = { seed: p.utSeed }
  } else if (!p.ut && m.ultratex) patch['malla.ultratex'] = false
  const cands = Object.fromEntries(extra.map(f => [f.nombre, candidato(f, p, m, tipoAsset)]))
  const nuevos = extra.length ? cands : null
  if (!igual(nuevos, m.candidatos || null)) patch['malla.candidatos'] = nuevos

  // validar
  const nombres = filas.map(nombreDe)
  let error = null
  for (const f of extra) {
    if (!NOMBRE.test(f.nombre)) error = t('cand.nombre_mal', { n: f.nombre || '…' })
    else if (nombres.filter(x => x === f.nombre).length > 1) error = t('cand.nombre_repetido', { n: f.nombre })
    else if (f.tipo === 'ultratex') {
      const base = filas.find(x => nombreDe(x) === f.desde)
      if (!base || base === f || base.tipo !== 'motor') error = t('cand.desde_mal', { n: f.nombre })
    }
    if (error) break
  }
  if (!error && extra.length && m.elegida != null && !nombres.includes(m.elegida)) {
    error = t('cand.elegida_fuera', { e: m.elegida })
  }
  return { patch, error }
}

function nombreLibre(filas, base) {
  const usados = new Set(filas.map(nombreDe))
  if (!usados.has(base)) return base
  for (let i = 2; ; i++) if (!usados.has(`${base}_${i}`)) return `${base}_${i}`
}

function Rehacer({ d, nombre, sucio }) {
  const [paso, setPaso] = useState(0)   // 0 botón, 1 confirmar, 2 trabajando
  if (paso === 1) {
    return html`<span class="confirmar"><span class="chico">${t('cand.rehacer_confirmar')}</span>
      <button class="boton chico peligro" onClick=${async () => {
        setPaso(2)
        try {
          const r = await api(`assets/${encodeURIComponent(d.nombre)}/malla/${encodeURIComponent(nombre)}/rehacer`, { metodo: 'POST' })
          aviso(t('cand.borrados', { c: r.borrados.join(', ') || nombre }))
          await encolar({ paso: 'malla', nombre: d.nombre })
        } catch (e) { aviso(e.message, 'error') }
        setPaso(0)
      }}>${t('cand.rehacer_si')}</button>
      <button class="boton chico fantasma" onClick=${() => setPaso(0)}>${t('cand.rehacer_no')}</button></span>`
  }
  return html`<button class="boton chico" disabled=${sucio || paso === 2} title=${sucio ? t('cand.guardar_antes') : t('cand.rehacer_ayuda')}
    onClick=${() => setPaso(1)}><${Icono} n="rehacer" />${t('cand.rehacer')}</button>`
}

function Fila({ d, f, filas, hechas, cambiar, quitar, sucio }) {
  const nombre = nombreDe(f)
  const hecha = hechas[nombre] != null
  const editada = hecha && f.ini && ['tipo', 'motor', 'seed', 'resolucion', 'ut', 'utSeed', 'desde'].some(k => cambio(f, k))
  const bases = filas.filter(x => x !== f && x.tipo === 'motor')
  const id = k => `cand-${f.id}-${k}`
  return html`<article class=${'candidato' + (f.principal ? ' principal' : '')}>
    <header>
      ${f.principal
        ? html`<b>${nombre}</b><span class="tenue chico">${t('cand.principal')}</span>`
        : html`<input class="entrada mono nombre-cand" value=${f.nombre} aria-label=${t('cand.nombre')} spellcheck="false" autocapitalize="off"
            aria-invalid=${!NOMBRE.test(f.nombre)} onInput=${e => cambiar({ nombre: e.target.value.trim() })} />`}
      ${Object.keys(hechas).length > 0 && html`<${Chip} clase=${hecha ? 'hecho' : ''}>${t(hecha ? 'cand.hecho' : 'cand.falta')}<//>`}
      <span class="acciones-cand">
        ${hecha && f.ini && nombreDe(f.ini) === nombre && html`<${Rehacer} d=${d} nombre=${nombre} sucio=${sucio} />`}
        ${!f.principal && html`<button class="icono-boton" onClick=${quitar} aria-label=${t('cand.quitar')} title=${t('cand.quitar')}><${Icono} n="x" /></button>`}
      </span>
    </header>
    <div class="fila">
      ${!f.principal && html`<label class="campo" for=${id('tipo')}><span>${t('cand.tipo')}</span>
        <select class="entrada" id=${id('tipo')} value=${f.tipo} onChange=${e => cambiar({ tipo: e.target.value, desde: f.desde && bases.some(b => nombreDe(b) === f.desde) ? f.desde : nombreDe(bases[0] || filas[0]) })}>
          <option value="motor">${t('cand.tipo_motor')}</option>
          <option value="ultratex" disabled=${!bases.length}>${t('cand.tipo_ultratex')}</option>
        </select></label>`}
      ${f.tipo === 'ultratex'
        ? html`<label class="campo" for=${id('desde')}><span>${t('cand.desde')}</span>
            <select class="entrada" id=${id('desde')} value=${f.desde} onChange=${e => cambiar({ desde: e.target.value })}>
              ${bases.map(b => html`<option value=${nombreDe(b)}>${nombreDe(b)}</option>`)}</select>
            <small>${t('cand.desde_ayuda')}</small></label>`
        : html`<label class="campo" for=${id('motor')}><span>${t('aj.motor_malla')}</span>
            <select class="entrada" id=${id('motor')} value=${f.motor} onChange=${e => {
              const motor = e.target.value
              const res = RESOLUCIONES[motor].includes(f.resolucion) ? f.resolucion : RESOLUCIONES[motor].at(-1)
              cambiar({ motor, resolucion: res })
            }}>${MOTORES.map(([v, n]) => html`<option value=${v}>${n}</option>`)}</select>
            ${f.principal && html`<small>${t('cand.principal_ayuda')}</small>`}</label>
          <label class="campo" for=${id('seed')}><span>${t('aj.seed_malla')}</span>
            <input class="entrada" id=${id('seed')} type="number" step="1" value=${f.seed} onInput=${e => cambiar({ seed: Number(e.target.value) })} /></label>
          <label class="campo" for=${id('res')}><span>${t('cand.resolucion')}</span>
            <select class="entrada" id=${id('res')} value=${f.resolucion} onChange=${e => cambiar({ resolucion: Number(e.target.value) })}>
              ${[...new Set([...RESOLUCIONES[f.motor], f.resolucion])].sort((a, b) => a - b).map(r => html`<option value=${r}>${r}</option>`)}
            </select>
            ${!RESOLUCIONES[f.motor].includes(f.resolucion) ? html`<small style="color:var(--error)">${t(f.motor === 'pixal3d' ? 'cand.res_pixal_baja' : 'cand.res_trellis_alta')}</small>`
              : !f.principal && f.ini && f.orig && !('resolucion' in f.orig) && !cambio(f, 'resolucion') ? html`<small>${t('cand.res_hereda')}</small>` : ''}</label>`}
      ${f.tipo === 'motor' && html`<label class="casilla"><input type="checkbox" checked=${f.ut} onChange=${e => cambiar({ ut: e.target.checked })} />${t('cand.con_ultratex')}</label>`}
      ${(f.tipo === 'ultratex' || f.ut) && html`<label class="campo" for=${id('ut')}><span>${t('aj.seed_ultratex')}</span>
        <input class="entrada" id=${id('ut')} type="number" step="1" value=${f.utSeed} onInput=${e => cambiar({ utSeed: Number(e.target.value) })} /></label>`}
    </div>
    ${editada && html`<p class="aviso-cand chico"><${Icono} n="alerta" />${t('cand.ya_hecho')}</p>`}
  </article>`
}

export function Candidatos({ d, onCambio }) {
  const m = d.json.malla || {}
  const [filas, setFilas] = useState(() => desdeJson(m, d.tipo))
  const { patch, error } = aJson(filas, m, d.tipo)
  useEffect(() => { onCambio(patch, error) }, [JSON.stringify(patch), error])
  const hechas = Object.keys(m.candidatos || {}).length ? (d.mallas_hechas || {}) : {}
  const sucio = Object.keys(patch).length > 0
  // los candidatos guardados que todavía no se generaron (el paso Malla 3D puede figurar listo igual)
  const faltan = Object.keys(m.candidatos || {}).length
    ? [m.motor || 'trellis2', ...Object.keys(m.candidatos)].filter(n => hechas[n] == null) : []
  const cambiar = (i, cambios) => setFilas(fs => {
    const nuevas = fs.map((f, k) => (k === i ? { ...f, ...cambios } : f))
    if (i === 0 && cambios.motor && cambios.motor !== fs[0].motor) {   // el principal se llama como su motor
      return nuevas.map(f => (f.tipo === 'ultratex' && f.desde === fs[0].motor ? { ...f, desde: cambios.motor } : f))
    }
    return nuevas
  })
  const agregar = tipo => setFilas(fs => {
    const p = fs[0]
    const f = tipo === 'ultratex'
      ? { id: 'c' + ++ids, nombre: nombreLibre(fs, 'ultratex'), tipo, desde: nombreDe(p), motor: p.motor, seed: p.seed, resolucion: p.resolucion, ut: true, utSeed: 1 }
      : { id: 'c' + ++ids, nombre: nombreLibre(fs, tipo), tipo: 'motor', motor: tipo, seed: 1, ut: false, utSeed: 1,
          resolucion: tipo === p.motor ? p.resolucion : resolucionPorDefecto(tipo, d.tipo) }
    return [...fs, f]
  })
  return html`<div class="campo candidatos-malla">
    <span>${t('cand.titulo')}</span><small>${t('cand.ayuda')}</small>
    <div class="lista-candidatos">${filas.map((f, i) => html`<${Fila} key=${f.id} d=${d} f=${f} filas=${filas} hechas=${hechas}
      sucio=${sucio} cambiar=${c => cambiar(i, c)} quitar=${() => setFilas(fs => fs.filter(x => x !== f))} />`)}</div>
    <div class="botones-cand">
      <button class="boton chico" onClick=${() => agregar('trellis2')}><${Icono} n="nuevo" />${t('cand.agregar_trellis')}</button>
      <button class="boton chico" onClick=${() => agregar('pixal3d')}><${Icono} n="nuevo" />${t('cand.agregar_pixal')}</button>
      <button class="boton chico" onClick=${() => agregar('ultratex')}><${Icono} n="nuevo" />${t('cand.agregar_ultratex')}</button>
    </div>
    ${filas.length > 1 && html`<small>${t('cand.al_guardar')}</small>`}
    ${faltan.length > 0 && !sucio && html`<div class="aviso brasa"><${Icono} n="info" />
      <p style="flex:1">${t('cand.faltan', { c: faltan.join(', ') })}</p>
      <button class="boton chico primario" onClick=${() => encolar({ paso: 'malla', nombre: d.nombre })}><${Icono} n="correr" />${t('cand.generar_faltan')}</button></div>`}
    ${error && html`<p class="chico" role="alert" style="color:var(--error)">${error}</p>`}
  </div>`
}
