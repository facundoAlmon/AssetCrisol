// Instalación: lo que dice `crisol doctor --json` (revisiones y pasos disponibles, con cómo arreglar lo que falta).
import { html, useState, useGlobal, t, Icono, Chip, Cargando, cargarDoctor } from '../comunes.mjs'

const CLASE = { ok: 'hecho', aviso: 'viejo', falta: 'fallo' }

export function Instalacion() {
  const g = useGlobal()
  const [revisando, setRevisando] = useState(false)
  const d = g.doctor
  const revisar = async () => { setRevisando(true); await cargarDoctor(true); setRevisando(false) }
  const grupos = d ? [...new Set(d.revisiones.map(r => r.grupo))] : []
  const faltan = d ? d.pasos.filter(p => !p.disponible) : []
  return html`
    <header class="encabezado">
      <div style="display:grid;gap:6px"><h1>${t('inst.titulo')}</h1><p class="tenue">${t('inst.ayuda')}</p></div>
      <div class="acciones"><button class="boton" disabled=${revisando} onClick=${revisar}><${Icono} n="rehacer" />
        ${revisando ? t('inst.revisando') : t('inst.revisar')}</button></div>
    </header>
    ${!d ? html`<${Cargando} />` : html`<div style="display:grid;gap:20px;max-width:1100px">
      ${d.error && html`<div class="aviso error"><${Icono} n="alerta" /><p>${d.error}</p></div>`}
      <div class=${'aviso ' + (faltan.length ? 'brasa' : '')}><${Icono} n=${faltan.length ? 'alerta' : 'check'} />
        <p>${faltan.length ? t('inst.falta_algo') : t('inst.todo_bien')}</p></div>
      <section class="panel" style="overflow-x:auto"><h2>${t('inst.pasos')}</h2>
        <table class="tabla"><thead><tr><th>${t('inst.pasos')}</th><th></th><th>${t('inst.necesita')}</th></tr></thead>
          <tbody>${d.pasos.map(p => html`<tr>
            <td><b>${p.paso}</b></td>
            <td><${Chip} clase=${p.disponible ? 'hecho' : 'fallo'}>${t(p.disponible ? 'inst.disponible' : 'inst.no_disponible')}<//></td>
            <td class="tenue chico">${p.necesita}${p.falta?.length ? html`<div style="color:var(--error)">${p.falta.join(', ')}</div>` : ''}</td>
          </tr>`)}</tbody></table>
      </section>
      ${grupos.map(gr => html`<section class="panel" style="overflow-x:auto" key=${gr}><h2>${gr}</h2>
        <table class="tabla"><tbody>${d.revisiones.filter(r => r.grupo === gr).map(r => html`<tr>
          <td><b>${r.nombre}</b></td>
          <td><${Chip} clase=${CLASE[r.estado] || ''}>${r.estado}<//></td>
          <td class="chico"><div style="overflow-wrap:anywhere">${r.detalle}</div>
            ${r.arreglo && r.estado !== 'ok' && html`<div class="tenue" style="margin-top:4px">${t('inst.arreglo')}: <span class="mono">${r.arreglo}</span></div>`}</td>
        </tr>`)}</tbody></table></section>`)}
    </div>`}`
}
