// Biblioteca: todos los assets de datos_dir con su miniatura, en qué paso están y si falta elegir algo. Filtro por
// tipo y nombre; selección de personajes para rehacerlos en lote.
import {
  html, useState, useEffect, useMemo, useGlobal, api, t, urlMini, Icono, Chip, Cargando, Error, trabajosDe, encolar,
  nombrePaso,
} from '../comunes.mjs'

const TIPOS = ['todos', 'personaje', 'objeto', 'vehiculo', 'escenario']

export function estadoGeneral(a, cola) {
  const { corriendo, pendientes } = trabajosDe(cola, a.nombre)
  if (corriendo) return ['corriendo', t('asset.corriendo') + ': ' + nombrePaso(corriendo.paso, a.tipo)]
  if (pendientes.length) return ['pendiente-cola', t('estado.en_cola')]
  if (a.decidir?.length) return ['decidir', t('estado.decidir')]
  if (a.pasos?.some(p => p.estado === 'viejo')) return ['viejo', t('estado.viejo')]
  if (!a.siguiente) return ['hecho', t('estado.listo_todo')]
  return ['', t('asset.siguiente', { paso: nombrePaso(a.siguiente.split(' ')[1], a.tipo) })]
}

export function useAssets() {
  const g = useGlobal()
  const [d, setD] = useState(null)
  const [error, setError] = useState(null)
  const cargar = () => api('assets').then(x => { setD(x); setError(null) }, e => setError(e.message))
  useEffect(() => { cargar() }, [g.versionAssets])
  return { d, error, cargar }
}

function Tarjeta({ a, cola, seleccionando, seleccionado, alternar }) {
  const [clase, texto] = estadoGeneral(a, cola)
  const { corriendo } = trabajosDe(cola, a.nombre)
  const pasos = (a.pasos || []).filter(p => p.estado !== 'no_aplica' && !p.opcional)
  const contenido = html`
    <div class="arte damero">${a.miniatura
      ? html`<img src=${urlMini(a.nombre, a.miniatura, 400, '', Math.round(a.modificado))} alt="" loading="lazy" />`
      : html`<span class="tenue chico">${t('tipo.' + a.tipo)}</span>`}</div>
    <div class="info">
      <span class="nombre">${a.nombre}</span>
      <div class="progreso-paso" aria-hidden="true">${pasos.map(p => html`<i class=${corriendo?.paso === p.paso ? 'corriendo' : p.estado} />`)}</div>
      <div class="meta"><${Chip} clase=${clase}>${texto}<//></div>
    </div>`
  if (seleccionando) {
    const puede = a.tipo === 'personaje'
    return html`<label class="asset" style=${{ cursor: puede ? 'pointer' : 'not-allowed', opacity: puede ? 1 : 0.5 }}>
      <span class="seleccion"><input type="checkbox" disabled=${!puede} checked=${seleccionado} onChange=${alternar} aria-label=${a.nombre} /></span>
      ${contenido}</label>`
  }
  return html`<a class="asset" href=${'#/a/' + encodeURIComponent(a.nombre)} title=${`${a.nombre}: ${t('tipo.' + a.tipo)}, ${a.estilo}`}>${contenido}</a>`
}

export function Biblioteca() {
  const g = useGlobal()
  const { d, error, cargar } = useAssets()
  const [tipo, setTipo] = useState('todos')
  const [buscar, setBuscar] = useState('')
  const [sel, setSel] = useState(null)   // null = sin selección; Set de nombres
  const lista = useMemo(() => (d?.assets || [])
    .filter(a => tipo === 'todos' || a.tipo === tipo)
    .filter(a => !buscar || a.nombre.includes(buscar.toLowerCase()))
    .sort((x, y) => (y.modificado || 0) - (x.modificado || 0)), [d, tipo, buscar])
  const hay = useMemo(() => new Set((d?.assets || []).map(a => a.tipo)), [d])

  if (error) return html`<${Error} error=${error} reintentar=${cargar} />`
  if (!d) return html`<${Cargando} />`
  const rehacer = async () => {
    await encolar({ paso: 'rehacer', nombres: [...sel] })
    setSel(null)
  }
  return html`
    <header class="encabezado">
      <h1>${t('bib.titulo')}</h1>
      <div class="acciones">
        ${sel
          ? html`<button class="boton" onClick=${() => setSel(null)}>${t('bib.cancelar_sel')}</button>
              <button class="boton primario" disabled=${!sel.size} onClick=${rehacer} title=${t('bib.rehacer_ayuda')}>
                <${Icono} n="rehacer" />${t('bib.rehacer_sel', { n: sel.size })}</button>`
          : html`${hay.has('personaje') && html`<button class="boton" onClick=${() => setSel(new Set())}>${t('bib.seleccionar')}</button>`}
              <a class="boton primario" href="#/nuevo"><${Icono} n="nuevo" />${t('bib.nuevo')}</a>`}
      </div>
    </header>
    ${d.assets.length > 0 && html`<div class="filtros">
      <div class="segmentos desplazable" role="group">
        ${TIPOS.filter(x => x === 'todos' || hay.has(x)).map(x =>
          html`<button aria-pressed=${tipo === x} onClick=${() => setTipo(x)}>${t('tipo.' + x)}</button>`)}
      </div>
      <input class="entrada" type="search" placeholder=${t('bib.buscar')} aria-label=${t('bib.buscar')} value=${buscar}
        onInput=${e => setBuscar(e.target.value)} />
    </div>`}
    ${d.assets.length === 0
      ? html`<div class="vacio"><h2>${t('bib.vacia', { datos: d.datos })}</h2><p>${t('bib.vacia_accion')}</p>
          <a class="boton primario" href="#/nuevo"><${Icono} n="nuevo" />${t('bib.nuevo')}</a></div>`
      : lista.length === 0
        ? html`<p class="vacio">${t('bib.sin_resultados')}</p>`
        : html`<div class="grilla">${lista.map(a => a.error
            ? html`<div class="asset" key=${a.nombre}><div class="info"><span class="nombre">${a.nombre}</span>
                <p class="chico" style="color:var(--error)">${a.error}</p></div></div>`
            : html`<${Tarjeta} key=${a.nombre} a=${a} cola=${g.cola} seleccionando=${!!sel} seleccionado=${sel?.has(a.nombre)}
                alternar=${() => { const s = new Set(sel); s.has(a.nombre) ? s.delete(a.nombre) : s.add(a.nombre); setSel(s) }} />`)}</div>`}`
}
