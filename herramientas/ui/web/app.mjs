// Entrada de la UI: el marco (barra lateral en escritorio, barra de abajo en el celular), el ruteo por hash y la
// conexión con el servidor (SSE de la cola, doctor).
import {
  html, render, useEffect, useGlobal, useRuta, t, Icono, Crisol, Colada, Lightbox, Avisos, conectar, cargarDoctor,
  leerPref, guardarPref, idiomaActual, cambiarIdioma, nombrePaso,
} from './comunes.mjs'
import { Biblioteca } from './componentes/biblioteca.mjs'
import { Asset } from './componentes/asset.mjs'
import { Nuevo } from './componentes/nuevo.mjs'
import { Cola } from './componentes/cola.mjs'
import { Instalacion } from './componentes/instalacion.mjs'
import { Movimientos } from './componentes/movimientos.mjs'

const NAV = [
  ['/', 'biblioteca', 'nav.biblioteca'],
  ['/nuevo', 'nuevo', 'nav.nuevo'],
  ['/cola', 'cola', 'nav.cola'],
  ['/movimientos', 'movimientos', 'nav.movimientos'],
  ['/instalacion', 'instalacion', 'nav.instalacion'],
]

function actual(ruta, destino) {
  return destino === '/' ? (ruta === '/' || ruta.startsWith('/a/')) : ruta.startsWith(destino)
}

function Preferencias() {
  const tema = leerPref('tema', 'sistema')
  const ponerTema = v => {
    guardarPref('tema', v)
    if (v === 'sistema') delete document.documentElement.dataset.theme
    else document.documentElement.dataset.theme = v
    cambiarIdioma(idiomaActual())   // re-render
  }
  return html`<div style="display:grid;gap:8px">
    <div class="segmentos" role="group" aria-label=${t('tema.titulo')}>
      ${[['sistema', 'tema.sistema'], ['light', 'tema.claro'], ['dark', 'tema.oscuro']].map(([v, k]) =>
        html`<button aria-pressed=${tema === v} onClick=${() => ponerTema(v)}>${t(k)}</button>`)}
    </div>
    <div class="segmentos" role="group" aria-label=${t('idioma.titulo')}>
      ${[['es', 'Español'], ['en', 'English']].map(([v, k]) =>
        html`<button aria-pressed=${idiomaActual() === v} onClick=${() => cambiarIdioma(v)} lang=${v}>${k}</button>`)}
    </div>
  </div>`
}

function CrisolMini() {
  const g = useGlobal()
  const tr = g.cola.trabajos.find(x => x.estado === 'corriendo')
  const pendientes = g.cola.trabajos.filter(x => x.estado === 'pendiente').length
  const quien = (tr ? tr.nombre : '') + (pendientes ? ` +${pendientes}` : '')
  return html`<a class="crisol-mini" href="#/cola" title=${tr ? `${nombrePaso(tr.paso, tr.tipo)}: ${quien}` : null}>
    <div class="linea"><b>${tr ? nombrePaso(tr.paso, tr.tipo) : t('cola.nada')}</b>
      ${quien && html`<span class="tenue">${quien}</span>`}</div>
    <${Colada} tr=${tr} cola=${g.cola} />
  </a>`
}

function Marco({ ruta, children }) {
  const g = useGlobal()
  const tr = g.cola.trabajos.find(x => x.estado === 'corriendo')
  const enCola = g.cola.trabajos.filter(x => x.estado === 'pendiente' || x.estado === 'corriendo').length
  const lleno = tr ? Math.min(1, (g.cola.ahora - tr.inicio) / Math.max(1, tr.estimado)) : 0.35
  return html`<div class="app">
    <aside class="lateral">
      <a class="marca" href="#/"><${Crisol} lleno=${lleno} /><b>AssetCrisol</b></a>
      <nav class="nav">
        ${NAV.map(([href, icono, k]) => html`<a href=${'#' + href} aria-current=${actual(ruta, href) ? 'page' : null}>
          <${Icono} n=${icono} />${t(k)}${href === '/cola' && enCola ? html`<span class="cuenta">${enCola}</span>` : ''}</a>`)}
      </nav>
      <div class="pie"><${CrisolMini} /><${Preferencias} /></div>
    </aside>
    <main class="principal" id="principal">${children}</main>
    <nav class="barra-abajo">
      ${NAV.filter(([h]) => h !== '/movimientos').map(([href, icono, k]) => html`<a href=${'#' + href} aria-current=${actual(ruta, href) ? 'page' : null}>
        ${href === '/cola' && tr && html`<${Colada} tr=${tr} cola=${g.cola} />`}
        <${Icono} n=${icono} />${t(k)}</a>`)}
    </nav>
    <${Lightbox} /><${Avisos} />
  </div>`
}

function App() {
  const ruta = useRuta()
  useEffect(() => { conectar(); cargarDoctor() }, [])
  let pantalla
  const m = ruta.match(/^\/a\/([^/]+)(?:\/([a-z]+))?/)
  if (m) pantalla = html`<${Asset} nombre=${decodeURIComponent(m[1])} pestana=${m[2] || 'resultado'} key=${m[1]} />`
  else if (ruta.startsWith('/nuevo')) pantalla = html`<${Nuevo} />`
  else if (ruta.startsWith('/cola')) pantalla = html`<${Cola} />`
  else if (ruta.startsWith('/instalacion')) pantalla = html`<${Instalacion} />`
  else if (ruta.startsWith('/movimientos')) pantalla = html`<${Movimientos} />`
  else pantalla = html`<${Biblioteca} />`
  return html`<${Marco} ruta=${ruta}>${pantalla}<//>`
}

render(html`<${App} />`, document.getElementById('app'))
