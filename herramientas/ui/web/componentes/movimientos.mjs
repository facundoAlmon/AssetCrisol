// Movimientos: clips candidatos con Kimodo (`crisol movimiento`, en la CPU) y sus hojas de esqueletos para mirarlos.
// Pasar un clip a la biblioteca (movimientos/<anim>.npz + biblioteca.json) sigue siendo a mano (README > Animaciones:
// dos métodos).
import { html, useState, useEffect, useGlobal, api, t, aviso, Icono, Cargando, encolar, verGrande } from '../comunes.mjs'

export function Movimientos() {
  const g = useGlobal()
  const [anims, setAnims] = useState(null)
  const [hojas, setHojas] = useState([])
  const [f, setF] = useState({ animacion: 'caminar', prompt: '', duracion: 4, seed: 1, muestras: 3 })
  useEffect(() => { api('animaciones').then(setAnims, e => aviso(e.message, 'error')) }, [])
  useEffect(() => { api('movimientos').then(setHojas, () => {}) }, [g.versionAssets])
  if (!anims) return html`<${Cargando} />`
  const campo = (k, v) => setF({ ...f, [k]: v })
  const enCola = g.cola.trabajos.some(x => x.paso === 'movimiento' && ['pendiente', 'corriendo'].includes(x.estado) && x.nombre === f.animacion)
  return html`
    <header class="encabezado"><div style="display:grid;gap:6px"><h1>${t('mov.titulo')}</h1><p class="tenue" style="max-width:70ch">${t('mov.ayuda')}</p></div></header>
    <div style="display:grid;gap:20px;max-width:1100px">
      <section class="panel grupo-ajustes">
        <div class="fila">
          <label class="campo"><span>${t('mov.animacion')}</span>
            <select class="entrada" value=${f.animacion} onChange=${e => campo('animacion', e.target.value)}>
              ${anims.map(a => html`<option value=${a.id}>${a.id}</option>`)}</select></label>
          <label class="campo"><span>${t('mov.duracion')}</span>
            <input class="entrada" type="number" min="1" max="10" step="0.5" value=${f.duracion} onInput=${e => campo('duracion', Number(e.target.value))} /></label>
          <label class="campo"><span>${t('mov.seed')}</span>
            <input class="entrada" type="number" step="1" value=${f.seed} onInput=${e => campo('seed', Number(e.target.value))} /></label>
          <label class="campo"><span>${t('mov.muestras')}</span>
            <input class="entrada" type="number" min="1" max="8" step="1" value=${f.muestras} onInput=${e => campo('muestras', Number(e.target.value))} /></label>
        </div>
        <label class="campo"><span>${t('mov.prompt')}</span>
          <textarea class="entrada" lang="en" placeholder="a person walks forward at a relaxed pace" value=${f.prompt}
            onInput=${e => campo('prompt', e.target.value)} /></label>
        <div><button class="boton primario" disabled=${!f.prompt.trim() || enCola}
          onClick=${() => encolar({ paso: 'movimiento', ...f, prompt: f.prompt.trim() })}><${Icono} n="correr" />${t('mov.generar')}</button></div>
      </section>
      ${hojas.length > 0 && html`<div class="opciones">${hojas.map(h => html`<article class="opcion" key=${h.archivo}>
        <button class="arte damero" onClick=${() => verGrande(`/movimientos/${h.archivo}?v=${Math.round(h.modificado)}`, h.archivo)}>
          <img src=${`/movimientos/${h.archivo}?v=${Math.round(h.modificado)}`} alt=${h.archivo} loading="lazy" /></button>
        <footer><span class="mono chico">${h.archivo.replace('.png', '')}</span><span class="tenue chico">${h.clips} clips</span></footer>
      </article>`)}</div>`}
    </div>`
}
