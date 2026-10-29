// Lo que usan todas las pantallas: Preact + htm, la API del servidor, el estado global (cola por SSE, doctor,
// assets), los textos (i18n), íconos y piezas chicas (imagen con miniatura, lightbox, avisos flotantes).
import { html, render, useState, useEffect, useRef, useMemo, useCallback } from './vendor/preact-htm.mjs'
import es from './i18n/es.mjs'
import en from './i18n/en.mjs'

export { html, render, useState, useEffect, useRef, useMemo, useCallback }

// ---------- preferencias del navegador (pueden no estar: modo privado) ----------
export function leerPref(clave, defecto) {
  try { return localStorage.getItem('crisol.' + clave) ?? defecto } catch { return defecto }
}
export function guardarPref(clave, valor) {
  try { localStorage.setItem('crisol.' + clave, valor) } catch { /* sin almacenamiento */ }
}

// ---------- i18n ----------
const IDIOMAS = { es, en }
let idioma = leerPref('idioma', (navigator.language || 'es').startsWith('es') ? 'es' : 'en')
if (!IDIOMAS[idioma]) idioma = 'es'
document.documentElement.lang = idioma
export const idiomaActual = () => idioma
export function cambiarIdioma(i) {
  idioma = i
  guardarPref('idioma', i)
  document.documentElement.lang = i
  avisar()
}
export function t(clave, vars) {
  let s = IDIOMAS[idioma][clave] ?? es[clave] ?? clave
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v)
  return s
}
// en objetos y vehículos, `blender` no arma un rig: renderiza las vistas (o arma el vehículo)
export const nombrePaso = (p, tipo) => t(p === 'blender' && tipo && tipo !== 'personaje' ? 'paso.blender_' + tipo : 'paso.' + p)

// ---------- API ----------
export async function api(ruta, { metodo = 'GET', cuerpo, crudo } = {}) {
  const r = await fetch('/api/' + ruta, {
    method: metodo,
    headers: crudo ? { 'Content-Type': crudo.type || 'application/octet-stream' } : cuerpo ? { 'Content-Type': 'application/json' } : {},
    body: crudo || (cuerpo ? JSON.stringify(cuerpo) : undefined),
  })
  if (r.status === 401) location.reload()   // crisol ui en la red sin la cookie del token: la página lo pide
  const texto = await r.text()
  let d
  try { d = texto ? JSON.parse(texto) : {} } catch { d = { error: texto } }
  if (!r.ok) throw new Error(d.error || r.statusText)
  return d
}
export const urlArchivo = (n, ruta, v) => `/archivos/${encodeURIComponent(n)}/${ruta.split('/').map(encodeURIComponent).join('/')}${v ? '?v=' + v : ''}`
export const urlMini = (n, ruta, lado = 320, extra = '', v) => `/mini/${encodeURIComponent(n)}/${ruta.split('/').map(encodeURIComponent).join('/')}?lado=${lado}${extra}${v ? '&v=' + v : ''}`

// ---------- estado global ----------
const estado = { cola: { trabajos: [], version: -1, ahora: Date.now() / 1000 }, log: null, doctor: null, versionAssets: 0, conectado: true, avisos: [] }
const oyentes = new Set()
function avisar() { for (const f of oyentes) f({}) }
export function useGlobal() {
  const [, forzar] = useState(0)
  useEffect(() => {
    const f = () => forzar(x => x + 1)
    oyentes.add(f)
    return () => oyentes.delete(f)
  }, [])
  return estado
}
export function poner(cambios) { Object.assign(estado, cambios); avisar() }

let idAviso = 0
export function aviso(texto, tipo = '', accion) {
  const id = ++idAviso
  estado.avisos = [...estado.avisos, { id, texto, tipo, accion }]
  avisar()
  setTimeout(() => { estado.avisos = estado.avisos.filter(a => a.id !== id); avisar() }, tipo === 'error' ? 9000 : 5000)
}

// eventos del servidor: cola, log del trabajo en curso y versión de los assets
let previos = null
export function conectar() {
  const es = new EventSource('/api/eventos')
  es.addEventListener('cola', e => {
    const c = JSON.parse(e.data)
    if (previos) {
      for (const tr of c.trabajos) {
        const antes = previos.get(tr.id)
        if (antes && antes !== tr.estado && (tr.estado === 'hecho' || tr.estado === 'fallo')) {
          const vars = { paso: nombrePaso(tr.paso, tr.tipo), n: tr.nombre }
          aviso(t(tr.estado === 'hecho' ? 'cola.termino' : 'cola.fallo', vars), tr.estado === 'fallo' ? 'error' : '',
            tr.paso !== 'movimiento' && tr.paso !== 'rehacer' ? { texto: t('cola.ir'), href: '#/a/' + tr.nombre } : null)
        }
      }
    }
    previos = new Map(c.trabajos.map(x => [x.id, x.estado]))
    c.recibido = Date.now() / 1000
    poner({ cola: c, conectado: true })
  })
  es.addEventListener('log', e => poner({ log: JSON.parse(e.data) }))
  es.addEventListener('assets', e => poner({ versionAssets: Number(e.data) }))
  es.onerror = () => {
    poner({ conectado: false })
    // un 401 cierra el EventSource para siempre (p. ej. la UI se reabrió con otro token): recargar pide el token
    if (es.readyState === EventSource.CLOSED) fetch('/api/cola').then(r => { if (r.status === 401) location.reload() }, () => {})
  }
  // el tiempo transcurrido y la barra avanzan aunque la cola no cambie
  setInterval(() => { if (estado.cola.trabajos.some(x => x.estado === 'corriendo')) avisar() }, 1000)
}

export async function cargarDoctor(refrescar = false) {
  if (refrescar) await api('doctor', { metodo: 'POST' })
  for (let i = 0; i < 120; i++) {
    const d = await api('doctor')
    if (!d.cargando) { poner({ doctor: d }); return d }
    await new Promise(r => setTimeout(r, 1000))
  }
}

// trabajos de la cola por asset: {corriendo: trabajo|null, pendientes: [pasos]}
export function trabajosDe(cola, nombre) {
  const activos = cola.trabajos.filter(x => (x.estado === 'corriendo' || x.estado === 'pendiente') &&
    (x.nombre === nombre || (x.paso === 'rehacer' && x.nombre.split(',').includes(nombre))))
  return { corriendo: activos.find(x => x.estado === 'corriendo') || null, pendientes: activos.filter(x => x.estado === 'pendiente') }
}

export async function encolar(cuerpo) {
  try {
    const tr = await api('cola', { metodo: 'POST', cuerpo })
    aviso(t('cola.encolado', { paso: nombrePaso(tr.paso, tr.tipo), n: tr.nombre }))
    return tr
  } catch (e) { aviso(e.message, 'error') }
}

// ---------- tiempo ----------
export function duracion(seg) {
  seg = Math.max(0, Math.round(seg))
  if (seg < 60) return t('comun.segundos', { n: seg })
  const m = Math.floor(seg / 60), s = seg % 60
  return m >= 10 || !s ? t('comun.minutos', { n: m }) : t('comun.minutos_seg', { m, s })
}
// segundos desde que empezó, corrigiendo el reloj del navegador con la hora del servidor
export function transcurrido(tr, cola) {
  const ahora = cola.ahora + (Date.now() / 1000 - (cola.recibido || Date.now() / 1000))
  return ahora - tr.inicio
}

// ---------- ruta (hash) ----------
export function useRuta() {
  const [ruta, setRuta] = useState(location.hash.slice(1) || '/')
  useEffect(() => {
    const f = () => { setRuta(location.hash.slice(1) || '/'); window.scrollTo(0, 0) }
    addEventListener('hashchange', f)
    return () => removeEventListener('hashchange', f)
  }, [])
  return ruta
}

// ---------- íconos (trazos propios, 24×24) ----------
const P = {
  biblioteca: 'M4 5h6v6H4zM14 5h6v6h-6zM4 15h6v4H4zM14 15h6v4h-6z',
  nuevo: 'M12 5v14M5 12h14',
  cola: 'M5 7h14M5 12h14M5 17h9',
  instalacion: 'M14.5 4.5a4 4 0 0 0-5 5L4 15v5h5l5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-3-3z',
  movimientos: 'M13 4a2 2 0 1 1 0 .1M9 20l2-6 3 2v4M7 11l3-3 4 1 3 3M11 14l-3 1',
  correr: 'M8 5l11 7-11 7z',
  rehacer: 'M4 12a8 8 0 1 0 2.4-5.7M4 4v4h4',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6 6l12 12M18 6L6 18',
  atras: 'M15 5l-7 7 7 7',
  ampliar: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',
  alerta: 'M12 4l9 16H3zM12 10v4M12 17.5v.5',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 7.5v.5',
  sol: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  luna: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z',
  log: 'M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5',
  pausa: 'M8 5v14M16 5v14',
  carpeta: 'M3 6h6l2 2h10v11H3z',
  subir: 'M12 16V4M7 9l5-5 5 5M4 20h16',
  punto: 'M12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2z',
  cubo: 'M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5',
  centrar: 'M12 3v4M12 17v4M3 12h4M17 12h4M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
}
export function Icono({ n, titulo }) {
  return html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
    stroke-linejoin="round" aria-hidden=${titulo ? null : 'true'} role=${titulo ? 'img' : null}>
    ${titulo && html`<title>${titulo}</title>`}<path d=${P[n]} /></svg>`
}

// el crisol del logo: un recipiente con el metal adentro (se llena con el progreso del trabajo en curso)
export function Crisol({ lleno = 0.55 }) {
  const y = 19 - 11 * Math.min(1, Math.max(0, lleno))
  return html`<svg viewBox="0 0 32 32" aria-hidden="true">
    <defs><clipPath id="vaso"><path d="M7 9h18l-2.2 13.5a3 3 0 0 1-3 2.5h-7.6a3 3 0 0 1-3-2.5z" /></clipPath></defs>
    <rect x="0" y=${y + 3} width="32" height="32" fill="var(--brasa)" clip-path="url(#vaso)" />
    <path d="M7 9h18l-2.2 13.5a3 3 0 0 1-3 2.5h-7.6a3 3 0 0 1-3-2.5zM5 9h22M10 28h12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
  </svg>`
}

// ---------- piezas ----------
export function Cargando() { return html`<p class="tenue" role="status">${t('comun.cargando')}</p>` }

export function Error({ error, reintentar }) {
  return html`<div class="aviso error" role="alert"><${Icono} n="alerta" />
    <div style="display:grid;gap:8px"><p>${t('comun.error', { e: error })}</p>
    ${reintentar && html`<div><button class="boton chico" onClick=${reintentar}>${t('comun.reintentar')}</button></div>`}</div></div>`
}

export function Chip({ clase = '', children }) {
  return html`<span class=${'chip ' + clase}>${clase && html`<span class="punto" />`}${children}</span>`
}

export function Colada({ tr, cola }) {
  if (!tr) return html`<div class="colada"><i style="width:0" /></div>`
  const pasado = transcurrido(tr, cola)
  const frac = Math.min(0.97, pasado / Math.max(1, tr.estimado))
  return html`<div class=${'colada' + (pasado > tr.estimado ? ' pasado' : '')} role="progressbar"
    aria-valuemin="0" aria-valuemax="100" aria-valuenow=${Math.round(frac * 100)}><i style=${{ width: frac * 100 + '%' }} /></div>`
}

// lightbox: una imagen grande, con tamaño real a un clic (los sprites se miran de cerca)
let abrirLightbox = () => {}
export function verGrande(src, titulo) { abrirLightbox({ src, titulo }) }
export function Lightbox() {
  const [img, setImg] = useState(null)
  const [zoom, setZoom] = useState(false)
  abrirLightbox = x => { setImg(x); setZoom(false) }
  useEffect(() => {
    if (!img) return
    const f = e => { if (e.key === 'Escape') setImg(null) }
    addEventListener('keydown', f)
    return () => removeEventListener('keydown', f)
  }, [img])
  if (!img) return null
  return html`<div class=${'lightbox' + (zoom ? ' zoom' : '')} role="dialog" aria-modal="true" aria-label=${img.titulo || ''}
      onClick=${e => { if (e.target === e.currentTarget) setImg(null) }}>
    <header><b>${img.titulo}</b>
      <button class="boton chico" onClick=${() => setZoom(!zoom)}>${t(zoom ? 'visor.ajustar' : 'visor.zoom')}</button>
      <button class="icono-boton" style="color:inherit" onClick=${() => setImg(null)} aria-label=${t('visor.cerrar')}><${Icono} n="x" /></button>
    </header>
    <div class="lienzo damero" onClick=${e => { if (e.target === e.currentTarget) setImg(null) }}><img src=${img.src} alt=${img.titulo || ''} /></div>
  </div>`
}

export function Avisos() {
  const g = useGlobal()
  return html`<div class="avisos" aria-live="polite">
    ${!g.conectado && html`<div class="aviso error"><${Icono} n="alerta" /><p>${t('comun.desconectado')}</p></div>`}
    ${g.avisos.map(a => html`<div class=${'aviso ' + (a.tipo === 'error' ? 'error' : '')} key=${a.id}>
      <${Icono} n=${a.tipo === 'error' ? 'alerta' : 'check'} /><p style="flex:1">${a.texto}</p>
      ${a.accion && html`<a class="boton chico" href=${a.accion.href}>${a.accion.texto}</a>`}</div>`)}
  </div>`
}
