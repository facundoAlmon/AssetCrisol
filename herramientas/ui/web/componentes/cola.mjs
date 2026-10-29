// Cola: el paso que corre (tiempo, estimado, log en vivo, cancelar), los que esperan y el historial.
import { html, useState, useGlobal, api, t, aviso, Icono, Chip, Colada, duracion, transcurrido, nombrePaso, Plegable } from '../comunes.mjs'

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

function Fila({ tr, marcado, marcar }) {
  const [log, setLog] = useState(null)
  const ver = async () => {
    if (log !== null) return setLog(null)
    try { setLog(await (await fetch(`/api/trabajos/${tr.id}/log`)).text()) } catch (e) { aviso(e.message, 'error') }
  }
  const dur = tr.inicio && tr.fin ? t('cola.duro', { t: duracion(tr.fin - tr.inicio) }) : ''
  return html`<li>
    ${marcar && html`<input type="checkbox" class="marca-fila" checked=${marcado} onChange=${e => marcar(e.target.checked)}
      aria-label=${t('cola.seleccionar') + ': ' + nombrePaso(tr.paso, tr.tipo) + ' ' + tr.nombre} />`}
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

// terminados: se pueden borrar (todos o los marcados) con sus logs; confirmar en la misma barra, sin diálogos
function Historial({ historial }) {
  const [marcados, setMarcados] = useState(new Set())
  const [confirmar, setConfirmar] = useState(null)   // null, o los ids a borrar (null en ids = todos)
  const vivos = new Set(historial.map(x => x.id))
  const sel = [...marcados].filter(id => vivos.has(id))
  const marcar = (id, si) => { const m = new Set(marcados); si ? m.add(id) : m.delete(id); setMarcados(m); setConfirmar(null) }
  const borrar = async ids => {
    try {
      const r = await api('cola/historial', { metodo: 'DELETE', cuerpo: ids ? { ids } : {} })
      aviso(t('cola.borrados', { n: r.borrados.length }))
      setMarcados(new Set())
    } catch (e) { aviso(e.message, 'error') }
    setConfirmar(null)
  }
  const n = confirmar ? (confirmar.ids ? confirmar.ids.length : historial.length) : 0
  const barra = html`<div class="acciones-historial">
    ${confirmar
      ? html`<span class="chico">${t('cola.borrar_confirmar', { n })}</span>
          <button class="boton chico peligro" onClick=${() => borrar(confirmar.ids)}>${t('cola.borrar_si')}</button>
          <button class="boton chico fantasma" onClick=${() => setConfirmar(null)}>${t('cola.borrar_no')}</button>`
      : sel.length
        ? html`<button class="boton chico" onClick=${() => setConfirmar({ ids: sel })}><${Icono} n="x" />${t('cola.borrar_sel', { n: sel.length })}</button>`
        : html`<button class="boton chico fantasma" onClick=${() => setConfirmar({ ids: null })}><${Icono} n="x" />${t('cola.borrar_todo')}</button>`}
  </div>`
  return html`<section class="panel"><${Plegable} titulo=${t('cola.historial')} resumen=${String(historial.length)} extra=${barra}>
    <ul class="lista-cola">${historial.map(x => html`<${Fila} tr=${x} key=${x.id} marcado=${marcados.has(x.id)} marcar=${si => marcar(x.id, si)} />`)}</ul>
  <//></section>`
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
      ${historial.length > 0 && html`<${Historial} historial=${historial} />`}
    </div>`
}
