// Cola: el paso que corre (tiempo, estimado, log en vivo, cancelar), los que esperan y el historial.
import { html, useState, useGlobal, api, t, aviso, Icono, Chip, Colada, duracion, transcurrido, nombrePaso } from '../comunes.mjs'

const CLASE = { hecho: 'hecho', fallo: 'fallo', corriendo: 'corriendo', pendiente: 'pendiente-cola' }

async function quitar(tr) {
  try { await api('cola/' + tr.id, { metodo: 'DELETE' }) } catch (e) { aviso(e.message, 'error') }
}

function Enlace({ tr }) {
  if (tr.paso === 'movimiento') return html`<span>${tr.nombre}</span>`
  if (tr.paso === 'rehacer') return html`<span>${tr.nombre.split(',').join(', ')}</span>`
  return html`<a href=${'#/a/' + encodeURIComponent(tr.nombre)}>${tr.nombre}</a>`
}

function Actual({ tr, cola, log }) {
  const pasado = transcurrido(tr, cola)
  const lineas = log?.id === tr.id ? log.log : ''
  const gpu = /\[gpu\] ocupada/.test(lineas.split('\n').slice(-3).join('\n'))
  return html`<section class="panel trabajo-actual">
    <div class="cabeza">
      <h2>${nombrePaso(tr.paso, tr.tipo)}</h2><span class="que"><${Enlace} tr=${tr} /></span>
      ${gpu && html`<${Chip} clase="decidir">${t('cola.espera_gpu')}<//>`}
      <button class="boton chico peligro" disabled=${tr.cancelando} onClick=${() => quitar(tr)}><${Icono} n="x" />${t('cola.cancelar')}</button>
    </div>
    ${gpu ? html`<div class="colada"><i style="width:0" /></div>` : html`<${Colada} tr=${tr} cola=${cola} />`}
    <p class="tenue chico">${gpu ? duracion(pasado) : t(pasado > tr.estimado ? 'cola.pasado' : 'cola.transcurrido', { t: duracion(pasado), e: duracion(tr.estimado) })}</p>
    <pre class="consola" aria-live="off">${lineas || '…'}</pre>
  </section>`
}

function Fila({ tr }) {
  const [log, setLog] = useState(null)
  const ver = async () => {
    if (log !== null) return setLog(null)
    try { setLog(await (await fetch(`/api/trabajos/${tr.id}/log`)).text()) } catch (e) { aviso(e.message, 'error') }
  }
  const dur = tr.inicio && tr.fin ? t('cola.duro', { t: duracion(tr.fin - tr.inicio) }) : ''
  return html`<li>
    <div class="que"><b>${nombrePaso(tr.paso, tr.tipo)}</b> <${Enlace} tr=${tr} />
      <div class="tenue chico">${new Date((tr.fin || tr.creado) * 1000).toLocaleString()} ${dur && ` — ${dur}`}
        ${tr.resultado?.error && html`<div style="color:var(--error);overflow-wrap:anywhere">${tr.resultado.error}</div>`}</div></div>
    <${Chip} clase=${CLASE[tr.estado] || ''}>${t('cola.estado.' + tr.estado)}<//>
    ${tr.estado === 'pendiente'
      ? html`<button class="boton chico" onClick=${() => quitar(tr)}>${t('cola.quitar')}</button>`
      : html`<button class="boton chico" onClick=${ver}><${Icono} n="log" />${t(log !== null ? 'cola.ocultar_log' : 'cola.ver_log')}</button>`}
    ${log !== null && html`<pre class="consola" style="flex-basis:100%">${log || '—'}</pre>`}
  </li>`
}

export function Cola() {
  const g = useGlobal()
  const tr = g.cola.trabajos.find(x => x.estado === 'corriendo')
  const pendientes = g.cola.trabajos.filter(x => x.estado === 'pendiente')
  const historial = g.cola.trabajos.filter(x => !['corriendo', 'pendiente'].includes(x.estado)).reverse()
  return html`
    <header class="encabezado"><h1>${t('cola.titulo')}</h1></header>
    <div style="display:grid;gap:20px;max-width:980px">
      ${tr ? html`<${Actual} tr=${tr} cola=${g.cola} log=${g.log} />` : html`<div class="panel vacio"><p>${t('cola.vacia')}</p></div>`}
      ${pendientes.length > 0 && html`<section class="panel"><h2>${t('cola.pendientes')}</h2>
        <ul class="lista-cola">${pendientes.map(x => html`<${Fila} tr=${x} key=${x.id} />`)}</ul></section>`}
      ${historial.length > 0 && html`<section class="panel"><h2>${t('cola.historial')}</h2>
        <ul class="lista-cola">${historial.map(x => html`<${Fila} tr=${x} key=${x.id} />`)}</ul></section>`}
    </div>`
}
