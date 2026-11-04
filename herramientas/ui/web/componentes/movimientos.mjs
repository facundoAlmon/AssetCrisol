// Movimientos: clips de Kimodo para las animaciones de los personajes, en cuatro pasos a la vista: 1) generar
// variantes (`crisol movimiento`, en la CPU, por la cola), 2) mirarlas animadas y recortarlas, 3) pasar una a la
// biblioteca (`crisol clip`) y decidir si la usan todos los personajes o solo algunos (`crisol metodo <n>
// anim=kimodo`), 4) rehacer rig, iso y anclas de los que la usen. Cada clip se ve con su esqueleto de costado animado
// (api/movimientos/esqueleto, metodos.esqueleto: no hace falta la hoja PNG de esqueletos).
import { html, useState, useEffect, useRef, useGlobal, api, t, aviso, Icono, Cargando, Chip, encolar } from '../comunes.mjs'

const segundos = v => (v === '' || v === null || v === undefined ? '' : String(v))
const num = v => (v === '' || v === null || v === undefined || Number.isNaN(Number(v)) ? null : Number(v))
const fmt = s => s.toFixed(2).replace(/\.?0+$/, '') || '0'

// los esqueletos ya pedidos (una página puede mostrar varias veces el mismo clip)
const cache = new Map()
function cargarEsqueleto(clave) {
  if (!cache.has(clave)) cache.set(clave, api('movimientos/esqueleto?' + clave).catch(e => { cache.delete(clave); throw e }))
  return cache.get(clave)
}

// El clip de costado (adelante = derecha; izquierda en rojo, derecha en azul) en loop entre desde y hasta (segundos;
// lo de afuera queda en gris en la barra). En pausa, la barra elige el instante y «desde acá» / «hasta acá» lo marcan.
export function Esqueleto({ clave, desde, hasta, marcar }) {
  const lienzo = useRef(null)
  const [e, setE] = useState(null)
  const [error, setError] = useState(null)
  const [pausa, setPausa] = useState(matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [s, setS] = useState(0)          // segundo que se muestra (lo mueve la reproducción o la barra)
  const estado = useRef({ s: 0, antes: null })
  useEffect(() => { let vivo = true; cargarEsqueleto(clave).then(x => vivo && setE(x), x => vivo && setError(x.message)); return () => { vivo = false } }, [clave])
  const dur = e ? e.cuadros / e.fps : 0
  const a = Math.max(0, Math.min(num(desde) ?? 0, dur)), b = Math.max(a, Math.min(num(hasta) ?? dur, dur))
  useEffect(() => {
    if (!e) return
    let cuadro
    const paso = ahora => {
      cuadro = requestAnimationFrame(paso)
      const r = estado.current
      if (!pausa) {
        if (r.antes !== null) r.s += (ahora - r.antes) / 1000
        if (r.s < a || r.s > b) r.s = a
        setS(r.s)
      }
      r.antes = ahora
      dibujar(lienzo.current, e, Math.min(e.cuadros - 1, Math.round(r.s * e.fps)))
    }
    cuadro = requestAnimationFrame(paso)
    return () => cancelAnimationFrame(cuadro)
  }, [e, pausa, a, b])
  if (error) return html`<p class="tenue chico">${t('mov.sin_esqueleto', { e: error })}</p>`
  if (!e) return html`<div class="esqueleto cargando"><${Cargando} /></div>`
  const ir = v => { estado.current.s = +v; setS(+v); setPausa(true) }
  const cuadro = Math.min(e.cuadros - 1, Math.round(s * e.fps))
  return html`<div class="esqueleto">
    <canvas ref=${lienzo} width="320" height="240" aria-label=${t('mov.esqueleto_alt')} role="img" />
    <div class="esqueleto-controles">
      <button class="boton chico" onClick=${() => { estado.current.antes = null; setPausa(!pausa) }}>
        <${Icono} n=${pausa ? 'correr' : 'pausa'} />${t(pausa ? 'visor.reproducir' : 'visor.pausa')}</button>
      <label class="barra-clip" style=${{ '--a': (a / dur * 100) + '%', '--b': (b / dur * 100) + '%' }}>
        <input type="range" min="0" max=${dur} step=${1 / e.fps} value=${s} onInput=${ev => ir(ev.target.value)} aria-label=${t('mov.instante')} />
      </label>
      <span class="mono chico tenue">${t('mov.instante_txt', { s: fmt(s), c: cuadro, d: fmt(dur) })}</span>
    </div>
    ${marcar && html`<div class="esqueleto-controles">
      <button class="boton chico fantasma" disabled=${s >= b - 0.1} onClick=${() => marcar('desde', fmt(s))}>${t('mov.desde_aca')}</button>
      <button class="boton chico fantasma" disabled=${s <= a + 0.1} onClick=${() => marcar('hasta', fmt(s))}>${t('mov.hasta_aca')}</button>
      ${(num(desde) !== null || num(hasta) !== null) && html`<button class="boton chico fantasma" onClick=${() => marcar('todo')}>${t('mov.clip_entero')}</button>`}
    </div>`}
  </div>`
}

function dibujar(c, e, k) {
  if (!c) return
  const g = c.getContext('2d')
  g.fillStyle = getComputedStyle(c).getPropertyValue('--superficie').trim() || '#fff'
  g.fillRect(0, 0, c.width, c.height)
  const xy = e.cuadros_xy[k]
  const esc = c.height * 0.4, ox = c.width / 2, oy = c.height - 18
  g.strokeStyle = '#8a8f99'; g.lineWidth = 1
  g.beginPath(); g.moveTo(10, oy); g.lineTo(c.width - 10, oy); g.stroke()
  g.lineWidth = 3; g.lineCap = 'round'
  for (const [i, j, izq] of e.huesos) {
    g.strokeStyle = izq ? '#d43c3c' : '#3c5ad4'
    g.beginPath()
    g.moveTo(ox + xy[2 * i] * esc, oy - xy[2 * i + 1] * esc)
    g.lineTo(ox + xy[2 * j] * esc, oy - xy[2 * j + 1] * esc)
    g.stroke()
  }
}

function Pasos() {
  return html`<ol class="pasos-mov">${[1, 2, 3, 4].map(i => html`<li><span class="num-paso">${i}</span>
    <div><b>${t('mov.paso' + i)}</b><small class="tenue">${t('mov.paso' + i + '_ayuda')}</small></div></li>`)}</ol>`
}

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
  // una generación = misma animación y seed: el prompt una vez, sus variantes adentro
  const grupos = []
  for (const c of mov.candidatos) {
    const k = `${c.animacion}_s${c.seed}`
    let gr = grupos.find(x => x.k === k)
    if (!gr) grupos.push(gr = { k, animacion: c.animacion, seed: c.seed, prompt: c.prompt, duracion: c.duracion, variantes: [] })
    gr.variantes.push(c)
  }
  return html`
    <header class="encabezado"><div style="display:grid;gap:6px"><h1>${t('mov.titulo')}</h1><p class="tenue" style="max-width:70ch">${t('mov.ayuda')}</p></div></header>
    <div style="display:grid;gap:20px;max-width:1100px;min-width:0">
      <${Pasos} />
      <section class="panel grupo-ajustes">
        <header><h2><span class="num-paso">1</span>${t('mov.generar_titulo')}</h2></header>
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
        <header><h2><span class="num-paso">2</span>${t('mov.candidatos')}</h2></header>
        <p class="tenue chico" style="margin-bottom:12px">${t('mov.candidatos_ayuda')}</p>
        ${grupos.length === 0 ? html`<p class="tenue">${t('mov.sin_candidatos')}</p>` : html`<div class="clips">
          ${grupos.map(gr => html`<${Generacion} key=${gr.k} gr=${gr} animaciones=${mov.animaciones} porAnim=${porAnim} clip=${clip} cuadros=${mov.cuadros} />`)}
        </div>`}
      </section>

      <section class="panel">
        <header><h2><span class="num-paso">3</span>${t('mov.biblioteca')}</h2></header>
        <p class="tenue chico" style="margin-bottom:12px">${t('mov.biblioteca_ayuda')}</p>
        <div class="clips">${mov.biblioteca.map(c => html`<${EnBiblioteca} key=${c.animacion} c=${c} clip=${clip} personajes=${personajes}
          recargar=${cargar} />`)}</div>
      </section>
    </div>`
}

function Generacion({ gr, animaciones, porAnim, clip, cuadros }) {
  const c0 = cuadros?.[gr.animacion]
  return html`<article class="clip generacion">
    <header>
      <b>${gr.animacion}</b><span class="tenue chico">${t('mov.seed')} ${gr.seed}</span>
      ${gr.duracion && html`<span class="tenue chico">${t('mov.segundos', { s: gr.duracion })}</span>`}
      <span class="tenue chico">${t('mov.n_variantes', { n: gr.variantes.length })}</span>
    </header>
    ${gr.prompt && html`<p class="tenue chico" lang="en">${gr.prompt}</p>`}
    ${c0 && html`<p class="tenue chico">${t(c0.loop ? 'mov.cuadros_loop' : 'mov.cuadros', { a: gr.animacion, n: c0.cuadros })}</p>`}
    <div class="variantes">${gr.variantes.map(c => html`<${Variante} key=${c.id} c=${c} animaciones=${animaciones} porAnim=${porAnim} clip=${clip} />`)}</div>
  </article>`
}

function Variante({ c, animaciones, porAnim, clip }) {
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
  const marcar = (k, s) => setV(k === 'todo' ? { ...v, desde: '', hasta: '' } : { ...v, [k]: s })
  return html`<div class="variante">
    <header><span class="mono">${t('mov.variante', { i: c.muestra + 1 })}</span><span class="mono chico tenue">${c.id}</span>
      ${usado.map(a => html`<${Chip} clase="hecho">${t('mov.en_biblioteca', { a })}</${Chip}>`)}</header>
    <${Esqueleto} clave=${'candidato=' + encodeURIComponent(c.id)} desde=${v.desde} hasta=${v.hasta} marcar=${marcar} />
    <div class="controles">
      <${Ventana} v=${v} set=${setV} />
      <label class="campo"><span>${t('mov.para')}</span>
        <select class="entrada" value=${v.para} onChange=${e => setV({ ...v, para: e.target.value })}>
          ${animaciones.map(a => html`<option value=${a}>${a}</option>`)}</select></label>
      <label class="casilla"><input type="checkbox" checked=${v.recomendado} onChange=${e => setV({ ...v, recomendado: e.target.checked })} />
        ${t('mov.por_defecto')}</label>
    </div>
    <div class="controles">
      <button class="boton chico" disabled=${ocupado} onClick=${pasar}><${Icono} n="check" />${t('mov.pasar_a', { a: v.para })}</button>
      ${hay && html`<span class="tenue chico">${t(hay.origen === 'repo' ? 'mov.reemplaza_repo' : 'mov.reemplaza_propio', { a: v.para })}</span>`}
    </div>
  </div>`
}

function Ventana({ v, set }) {
  return html`
    <label class="campo ventana"><span>${t('mov.desde')}</span>
      <input class="entrada" type="number" min="0" step="0.05" placeholder=${t('mov.inicio')} value=${v.desde}
        onInput=${e => set({ ...v, desde: e.target.value })} /></label>
    <label class="campo ventana"><span>${t('mov.hasta')}</span>
      <input class="entrada" type="number" min="0" step="0.05" placeholder=${t('mov.fin')} value=${v.hasta}
        onInput=${e => set({ ...v, hasta: e.target.value })} /></label>`
}

function EnBiblioteca({ c, clip, personajes, recargar }) {
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
      setQuien('')
      recargar()
    } catch (e) { aviso(e.message, 'error') }
    setOcupado(false)
  }
  const marcar = (k, s) => setV(k === 'todo' ? { desde: '', hasta: '' } : { ...v, [k]: s })
  const libres = personajes.filter(n => !c.usan.includes(n))
  return html`<article class="clip">
    <header>
      <b>${c.animacion}</b>
      <${Chip} clase=${c.origen === 'repo' ? '' : 'hecho'}>${t('mov.origen_' + c.origen.replace('+', '_'))}</${Chip}>
      ${c.duracion && html`<span class="tenue chico">${t('mov.segundos', { s: c.duracion })}</span>`}
      ${c.candidato && html`<span class="tenue chico mono">${c.candidato}</span>`}
    </header>
    ${(c.nota || c.prompt) && html`<p class="tenue chico">${c.nota || c.prompt}</p>`}
    <${Esqueleto} clave=${'animacion=' + encodeURIComponent(c.animacion)} desde=${v.desde} hasta=${v.hasta} marcar=${marcar} />
    <div class="controles">
      <${Ventana} v=${v} set=${setV} />
      <button class="boton chico" disabled=${ocupado || !cambiada} onClick=${() => hacer({ desde: v.desde, hasta: v.hasta })}>
        ${t('mov.guardar_ventana')}</button>
    </div>
    <div class="controles">
      <div class="campo"><span>${t('mov.metodo_defecto')}</span>
        <div class="segmentos" role="group" aria-label=${t('mov.metodo_defecto')}>
          ${[false, true].map(r => html`<button aria-pressed=${c.recomendado === r} disabled=${ocupado}
            onClick=${() => c.recomendado !== r && hacer({ recomendado: r })}>${r ? 'kimodo' : 'procedural'}</button>`)}
        </div><small class="tenue">${t(c.recomendado ? 'mov.defecto_kimodo' : 'mov.defecto_procedural', { a: c.animacion })}</small></div>
    </div>
    <p class="chico">${c.usan.length ? t('mov.lo_usan', { n: c.usan.join(', ') }) : t('mov.no_lo_usa')}</p>
    ${libres.length > 0 && html`<div class="controles">
      <label class="campo"><span>${t('mov.usar_en')}</span>
        <select class="entrada" value=${quien} onChange=${e => setQuien(e.target.value)}>
          <option value="">${t('mov.elegir_personaje')}</option>
          ${libres.map(n => html`<option value=${n}>${n}</option>`)}</select></label>
      <button class="boton chico" disabled=${ocupado || !quien} onClick=${usar}>${t('mov.usar')}</button>
    </div>`}
    ${c.origen !== 'repo' && html`<div><button class="boton chico peligro" disabled=${ocupado} onClick=${() => hacer({ quitar: true })}>
      ${c.origen === 'propia' ? t('mov.quitar') : t('mov.deshacer')}</button></div>`}
  </article>`
}
