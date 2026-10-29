// Movimientos: clips candidatos con Kimodo (`crisol movimiento`, en la CPU, por la cola), la fila de esqueletos de
// cada muestra para mirarla y la biblioteca de movimientos (`crisol clip`): pasar un candidato, su ventana
// (desde/hasta), si es el método por defecto, quitarlo y usarlo en un personaje (`crisol metodo <n> anim=kimodo`).
import { html, useState, useEffect, useGlobal, api, t, aviso, Icono, Cargando, Chip, encolar, verGrande } from '../comunes.mjs'

const hojaUrl = (c, fila) => `/movimientos/${c.hoja}?${fila ? `fila=${c.muestra}&` : ''}v=${Math.round(c.modificado)}`
const segundos = v => (v === '' || v === null || v === undefined ? '' : String(v))

export function Movimientos() {
  const g = useGlobal()
  const [mov, setMov] = useState(null)
  const [personajes, setPersonajes] = useState([])
  const [f, setF] = useState({ animacion: 'caminar', prompt: '', duracion: 4, seed: 1, muestras: 3 })
  const cargar = () => api('movimientos').then(setMov, e => aviso(e.message, 'error'))
  useEffect(() => { cargar() }, [g.versionAssets])
  useEffect(() => {
    api('assets').then(d => setPersonajes(d.assets.filter(a => a.tipo === 'personaje').map(a => a.nombre)), () => {})
  }, [])
  if (!mov) return html`<${Cargando} />`
  const campo = (k, v) => setF({ ...f, [k]: v })
  const enCola = g.cola.trabajos.some(x => x.paso === 'movimiento' && ['pendiente', 'corriendo'].includes(x.estado) && x.nombre === f.animacion)
  const clip = async (cuerpo, ok) => {
    try {
      setMov(await api('movimientos/clip', { metodo: 'POST', cuerpo }))
      aviso(ok || t('mov.guardado'))
      return true
    } catch (e) { aviso(e.message, 'error') }
  }
  const porAnim = Object.fromEntries(mov.biblioteca.map(c => [c.animacion, c]))
  return html`
    <header class="encabezado"><div style="display:grid;gap:6px"><h1>${t('mov.titulo')}</h1><p class="tenue" style="max-width:70ch">${t('mov.ayuda')}</p></div></header>
    <div style="display:grid;gap:20px;max-width:1100px">
      <section class="panel grupo-ajustes">
        <div class="fila">
          <label class="campo"><span>${t('mov.animacion')}</span>
            <select class="entrada" value=${f.animacion} onChange=${e => campo('animacion', e.target.value)}>
              ${mov.animaciones.map(a => html`<option value=${a}>${a}</option>`)}</select></label>
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

      <section class="panel">
        <header><h2>${t('mov.candidatos')}</h2></header>
        <p class="tenue chico" style="margin-bottom:12px">${t('mov.candidatos_ayuda')}</p>
        ${mov.candidatos.length === 0 ? html`<p class="tenue">${t('mov.sin_candidatos')}</p>` : html`<div class="clips">
          ${mov.candidatos.map(c => html`<${Candidato} key=${c.id} c=${c} animaciones=${mov.animaciones} porAnim=${porAnim} clip=${clip} />`)}
        </div>`}
      </section>

      <section class="panel">
        <header><h2>${t('mov.biblioteca')}</h2></header>
        <p class="tenue chico" style="margin-bottom:12px">${t('mov.biblioteca_ayuda')}</p>
        <div class="clips">${mov.biblioteca.map(c => html`<${EnBiblioteca} key=${c.animacion} c=${c} clip=${clip} personajes=${personajes} />`)}</div>
      </section>
    </div>`
}

function Ventana({ v, set }) {
  return html`
    <label class="campo ventana"><span>${t('mov.desde')}</span>
      <input class="entrada" type="number" min="0" step="0.1" placeholder=${t('mov.inicio')} value=${v.desde}
        onInput=${e => set({ ...v, desde: e.target.value })} /></label>
    <label class="campo ventana"><span>${t('mov.hasta')}</span>
      <input class="entrada" type="number" min="0" step="0.1" placeholder=${t('mov.fin')} value=${v.hasta}
        onInput=${e => set({ ...v, hasta: e.target.value })} /></label>`
}

function Candidato({ c, animaciones, porAnim, clip }) {
  const [v, setV] = useState({ para: animaciones.includes(c.animacion) ? c.animacion : animaciones[0], desde: '', hasta: '', recomendado: false })
  const [ocupado, setOcupado] = useState(false)
  const usado = Object.values(porAnim).filter(b => b.candidato === c.id && b.origen === 'propia').map(b => b.animacion)
  const hay = porAnim[v.para]
  const pasar = async () => {
    setOcupado(true)
    await clip({ animacion: v.para, candidato: c.id, desde: v.desde, hasta: v.hasta, recomendado: v.recomendado },
      t('mov.pasado', { c: c.id, a: v.para }))
    setOcupado(false)
  }
  return html`<article class="clip">
    <header>
      <span class="mono">${c.id}</span>
      ${c.duracion && html`<span class="tenue chico">${t('mov.segundos', { s: c.duracion })}</span>`}
      ${usado.map(a => html`<${Chip} clase="hecho">${t('mov.en_biblioteca', { a })}</${Chip}>`)}
    </header>
    ${c.prompt && html`<p class="tenue chico" lang="en">${c.prompt}</p>`}
    ${c.hoja && html`<div class="esqueletos">
      <button onClick=${() => verGrande(hojaUrl(c), c.hoja)} title=${t('mov.ver_hoja')}>
        <img src=${hojaUrl(c, true)} alt=${t('mov.esqueletos', { c: c.id })} /></button></div>`}
    <div class="controles">
      <label class="campo"><span>${t('mov.para')}</span>
        <select class="entrada" value=${v.para} onChange=${e => setV({ ...v, para: e.target.value })}>
          ${animaciones.map(a => html`<option value=${a}>${a}</option>`)}</select></label>
      <${Ventana} v=${v} set=${setV} />
      <label class="casilla"><input type="checkbox" checked=${v.recomendado} onChange=${e => setV({ ...v, recomendado: e.target.checked })} />
        ${t('mov.por_defecto')}</label>
      <button class="boton primario chico" disabled=${ocupado} onClick=${pasar}>
        ${hay ? t('mov.reemplazar', { a: v.para }) : t('mov.pasar')}</button>
    </div>
  </article>`
}

function EnBiblioteca({ c, clip, personajes }) {
  const inicial = { desde: segundos(c.desde), hasta: segundos(c.hasta) }
  const [v, setV] = useState(inicial)
  const [ocupado, setOcupado] = useState(false)
  const [quien, setQuien] = useState('')
  useEffect(() => setV(inicial), [c.desde, c.hasta])
  const cambiada = v.desde !== inicial.desde || v.hasta !== inicial.hasta
  const hacer = async cuerpo => { setOcupado(true); await clip({ animacion: c.animacion, ...cuerpo }); setOcupado(false) }
  const usar = async () => {
    setOcupado(true)
    try {
      await api(`assets/${encodeURIComponent(quien)}/metodos`, { metodo: 'POST', cuerpo: { cambios: { [c.animacion]: 'kimodo' } } })
      aviso(t('mov.usado', { a: c.animacion, n: quien }))
    } catch (e) { aviso(e.message, 'error') }
    setOcupado(false)
  }
  return html`<article class="clip">
    <header>
      <span class="mono">${c.animacion}</span>
      <${Chip} clase=${c.origen === 'repo' ? '' : 'hecho'}>${t('mov.origen_' + c.origen.replace('+', '_'))}</${Chip}>
      ${c.duracion && html`<span class="tenue chico">${t('mov.segundos', { s: c.duracion })}</span>`}
      ${c.candidato && html`<span class="tenue chico mono">${c.candidato}</span>`}
    </header>
    ${(c.nota || c.prompt) && html`<p class="tenue chico">${c.nota || c.prompt}</p>`}
    <div class="controles">
      <div class="campo"><span>${t('mov.metodo_defecto')}</span>
        <div class="segmentos" role="group" aria-label=${t('mov.metodo_defecto')}>
          ${[false, true].map(r => html`<button aria-pressed=${c.recomendado === r} disabled=${ocupado}
            onClick=${() => c.recomendado !== r && hacer({ recomendado: r })}>${r ? 'kimodo' : 'procedural'}</button>`)}
        </div></div>
      <${Ventana} v=${v} set=${setV} />
      <button class="boton chico" disabled=${ocupado || !cambiada} onClick=${() => hacer({ desde: v.desde, hasta: v.hasta })}>
        ${t('mov.guardar_ventana')}</button>
      ${c.origen !== 'repo' && html`<button class="boton chico peligro" disabled=${ocupado} onClick=${() => hacer({ quitar: true })}>
        ${c.origen === 'propia' ? t('mov.quitar') : t('mov.deshacer')}</button>`}
    </div>
    ${personajes.length > 0 && html`<div class="controles">
      <label class="campo"><span>${t('mov.usar_en')}</span>
        <select class="entrada" value=${quien} onChange=${e => setQuien(e.target.value)}>
          <option value="">${t('mov.elegir_personaje')}</option>
          ${personajes.map(n => html`<option value=${n}>${n}</option>`)}</select></label>
      <button class="boton chico" disabled=${ocupado || !quien} onClick=${usar}>${t('mov.usar')}</button>
    </div>`}
  </article>`
}
