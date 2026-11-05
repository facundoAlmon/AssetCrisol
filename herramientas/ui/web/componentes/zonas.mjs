// Editor de pesos por zonas (Resultado > Guía > Pesos por zonas): cajas sobre los renders de la guía (frente: x y z;
// costado: y y z, con la cámara de trabajo/guia/guia.json). Los vértices de cada caja quedan enteros en un hueso
// (rig_lib.pesos_zonas): piezas rígidas que el bone heat reparte mal, o manos que tocan el cuerpo. Guarda en
// modelo.pesos_zonas (PUT api/assets/<n>/pesos_zonas); se aplican al rehacer `blender`.
import { html, useState, useEffect, useRef, api, t, urlArchivo, Icono, Cargando, Error, aviso, encolar, nombrePaso } from '../comunes.mjs'

const VISTAS = [['frente', 0], ['costado', 1]]   // vista y su eje horizontal (x, y); el vertical es z
const COLORES = ['#ff9e45', '#5fc48d', '#74b4ec', '#e06bd0', '#f2d14b', '#ff7a6b']
const copiar = x => JSON.parse(JSON.stringify(x))
const r3 = v => Math.round(v * 1000) / 1000

export function EditorZonas({ d, cerrar }) {
  const [g, setG] = useState(null)
  const [error, setError] = useState(null)
  const [Z, setZ] = useState([])
  const [sel, setSel] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [guardadas, setGuardadas] = useState(false)
  const ruta = `assets/${encodeURIComponent(d.nombre)}/pesos_zonas`
  const empezar = x => { setG(x); setZ(copiar(x.zonas)); setSel(x.zonas.length ? 0 : null) }
  const cargar = () => api(ruta).then(x => { empezar(x); setError(null) }, e => setError(e.message))
  useEffect(() => { cargar() }, [d.nombre])
  if (error) return html`<${Error} error=${error} reintentar=${cargar} />`
  if (!g) return html`<${Cargando} />`

  const cambiado = JSON.stringify(Z) !== JSON.stringify(g.zonas)
  const cambiar = (i, z) => setZ(Z.map((x, k) => k === i ? z : x))
  const agregar = () => {
    const J = g.articulaciones, mano = J['hand.S'] || J['hand.L']
    const c = mano ? [mano[1][0], mano[1][1], mano[1][2]] : [0, 0, g.centro_z]
    const m = g.ortho * 0.05
    setZ([...Z, { min: [r3(c[0] - m), r3(c[1] - m), r3(c[2] - m)], max: [r3(c[0] + m), r3(c[1] + m), r3(c[2] + m)],
      hueso: g.huesos.includes('hand.L') ? 'hand.L' : g.huesos[0] }])
    setSel(Z.length)
  }
  const quitar = i => { setZ(Z.filter((_, k) => k !== i)); setSel(null) }
  const guardar = async () => {
    setGuardando(true)
    try {
      empezar(await api(ruta, { metodo: 'PUT', cuerpo: { zonas: Z } }))
      setGuardadas(true)
      aviso(t('zonas.guardadas'))
    } catch (e) { aviso(e.message, 'error') }
    setGuardando(false)
  }
  return html`<div class="editor-art">
    <p class="tenue chico" style="margin:0 0 10px">${t('zonas.ayuda')}</p>
    <div class="editor-art-vistas">${VISTAS.map(([vista, eje]) => html`<${Vista} key=${vista} vista=${vista} eje=${eje}
      g=${g} Z=${Z} sel=${sel} setSel=${setSel} cambiar=${cambiar} url=${urlArchivo(d.nombre, g[vista], g.version)} />`)}</div>
    <ul class="lista-zonas">${Z.map((z, i) => html`<li key=${i} aria-current=${i === sel ? 'true' : null}>
      <button class="zona-color" style=${{ background: COLORES[i % COLORES.length] }} onClick=${() => setSel(i)}
        aria-label=${t('zonas.elegir', { i: i + 1 })} />
      <label class="campo"><span>${t('zonas.hueso')}</span>
        <select class="entrada" value=${z.hueso} onChange=${e => cambiar(i, { ...z, hueso: e.target.value })} onFocus=${() => setSel(i)}>
          ${[...new Set([...g.huesos, z.hueso])].map(h => html`<option value=${h}>${h}</option>`)}</select></label>
      <span class="mono chico tenue">${['x', 'y', 'z'].map((k, j) => `${k} ${z.min[j].toFixed(2)}…${z.max[j].toFixed(2)}`).join(' · ')}</span>
      <button class="boton chico fantasma peligro" onClick=${() => quitar(i)}><${Icono} n="papelera" />${t('zonas.quitar')}</button>
    </li>`)}</ul>
    ${!Z.length && html`<p class="tenue chico">${t('zonas.ninguna')}</p>`}
    <div class="editor-art-pie">
      <button class="boton chico" onClick=${agregar}><${Icono} n="nuevo" />${t('zonas.agregar')}</button>
      <div class="acciones">
        <button class="boton chico fantasma" disabled=${!cambiado} onClick=${() => empezar(g)}>${t('art.descartar')}</button>
        <button class="boton chico" onClick=${cerrar}>${t('visor.cerrar')}</button>
        <button class="boton chico primario" disabled=${!cambiado || guardando} onClick=${guardar}><${Icono} n="check" />${t('art.guardar')}</button>
      </div>
    </div>
    ${guardadas && !cambiado && html`<div class="aviso" style="margin-top:12px;flex-wrap:wrap">
      <${Icono} n="info" /><span style="flex:1;min-width:200px">${t('art.siguiente', { paso: nombrePaso('blender', d.tipo) })}</span>
      <button class="boton chico primario" onClick=${() => { encolar({ paso: 'blender', nombre: d.nombre }); setGuardadas(false) }}>
        <${Icono} n="correr" />${t('art.correr_blender', { paso: nombrePaso('blender', d.tipo) })}</button>
    </div>`}
  </div>`
}

function Vista({ vista, eje, g, Z, sel, setSel, cambiar, url }) {
  const svg = useRef(null)
  const arrastre = useRef(null)
  const ppu = g.px / g.ortho
  const aPx = (h, z) => [g.px / 2 + h * ppu, g.px / 2 - (z - g.centro_z) * ppu]
  const caja = [g.px * 0.15, 0, g.px * 0.7, g.px]   // el personaje es angosto: el centro del render
  const enSvg = ev => {
    const p = svg.current.createSVGPoint()
    p.x = ev.clientX; p.y = ev.clientY
    return p.matrixTransform(svg.current.getScreenCTM().inverse())
  }
  // modo: 'mover' o la esquina ('ii' arriba-izq... en píxeles: h0/h1 horizontal, z0/z1 vertical)
  const bajar = (ev, i, modo) => {
    ev.preventDefault(); ev.stopPropagation()
    ev.currentTarget.setPointerCapture(ev.pointerId)
    setSel(i)
    arrastre.current = { i, modo, q: enSvg(ev), z: copiar(Z[i]) }
  }
  const mover = ev => {
    const a = arrastre.current
    if (!a) return
    const q = enSvg(ev)
    const dh = (q.x - a.q.x) / ppu, dz = -(q.y - a.q.y) / ppu
    const z = copiar(a.z)
    const min = 0.01
    if (a.modo === 'mover') {
      z.min[eje] = r3(z.min[eje] + dh); z.max[eje] = r3(z.max[eje] + dh)
      z.min[2] = r3(z.min[2] + dz); z.max[2] = r3(z.max[2] + dz)
    } else {
      if (a.modo.includes('izq')) z.min[eje] = r3(Math.min(z.min[eje] + dh, z.max[eje] - min))
      else z.max[eje] = r3(Math.max(z.max[eje] + dh, z.min[eje] + min))
      if (a.modo.includes('arr')) z.max[2] = r3(Math.max(z.max[2] + dz, z.min[2] + min))
      else z.min[2] = r3(Math.min(z.min[2] + dz, z.max[2] - min))
    }
    cambiar(a.i, z)
  }
  const tecla = (ev, i) => {
    const dir = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[ev.key]
    if (!dir) return
    ev.preventDefault()
    const p = ev.shiftKey ? 0.02 : 0.005
    const z = copiar(Z[i])
    if (ev.altKey) { z.max[eje] = r3(Math.max(z.max[eje] + dir[0] * p, z.min[eje] + 0.01)); z.min[2] = r3(Math.min(z.min[2] - dir[1] * p, z.max[2] - 0.01)) }
    else { for (const k of ['min', 'max']) { z[k][eje] = r3(z[k][eje] + dir[0] * p); z[k][2] = r3(z[k][2] + dir[1] * p) } }
    cambiar(i, z)
  }
  const r = g.px * 0.012
  return html`<figure class="editor-art-vista">
    <figcaption class="tenue chico">${t('art.' + vista)}</figcaption>
    <svg ref=${svg} viewBox=${caja.join(' ')} onPointerMove=${mover} onPointerUp=${() => { arrastre.current = null }}
      onPointerCancel=${() => { arrastre.current = null }} role="group" aria-label=${t('art.' + vista)}>
      <image href=${url} x="0" y="0" width=${g.px} height=${g.px} />
      ${Z.map((z, i) => {
        const [x0, y0] = aPx(z.min[eje], z.max[2]), [x1, y1] = aPx(z.max[eje], z.min[2])
        const c = COLORES[i % COLORES.length], elegida = i === sel
        return html`<g key=${i} class=${'zona' + (elegida ? ' elegida' : '')}>
          <rect x=${x0} y=${y0} width=${x1 - x0} height=${y1 - y0} fill=${c} fill-opacity=${elegida ? 0.28 : 0.15} stroke=${c}
            stroke-width=${elegida ? 3 : 2} tabindex="0" role="button" aria-label=${`${t('zonas.elegir', { i: i + 1 })}: ${z.hueso}`}
            onPointerDown=${ev => bajar(ev, i, 'mover')} onKeyDown=${ev => tecla(ev, i)} onFocus=${() => setSel(i)}><title>${z.hueso}</title></rect>
          ${elegida && [['izq arr', x0, y0], ['der arr', x1, y0], ['izq aba', x0, y1], ['der aba', x1, y1]].map(([m, x, y]) =>
            html`<circle key=${m} cx=${x} cy=${y} r=${r} fill=${c} stroke="#fff" stroke-width="2" class="asa-zona"
              onPointerDown=${ev => bajar(ev, i, m)} />`)}
        </g>`
      })}
    </svg>
  </figure>`
}
