// Editor de articulaciones: los puntos del esqueleto sobre los renders de la guía (frente y costado, con la cámara de
// trabajo/guia/guia.json) para moverlos arrastrando o con las flechas. Guarda en modelo.articulaciones
// (PUT api/assets/<n>/articulaciones), que redibuja guia.png y deja `blender` viejo.
import { html, useState, useEffect, useRef, api, t, urlArchivo, Icono, Cargando, Error, aviso, encolar, nombrePaso } from '../comunes.mjs'

const CENTRO = ['hips', 'spine', 'chest', 'neck', 'head']   // en el medio: de frente solo se mueven en z
const SIN_DIBUJAR = n => n === 'root' || n.startsWith('knee_pole') || n.startsWith('foot_ik')
const base = n => n.replace(/\.[SLR]$/, '')
const lado = n => n.match(/\.([SLR])$/)?.[1]
// nombre de cada punto: el del primer extremo de hueso que está en la tabla (hueso sin lado . 0 cabeza / 1 cola)
const NOMBRES = ['hips.0', 'spine.0', 'chest.0', 'neck.0', 'head.0', 'head.1', 'shoulder.0', 'shoulder.1', 'upper_arm.0',
  'forearm.0', 'hand.0', 'hand.1', 'thigh.0', 'shin.0', 'foot.0', 'foot.1']
const VISTAS = [['frente', 0], ['costado', 1]]   // vista y su eje horizontal (x, y); el vertical es z

// Los puntos son los extremos de hueso que coinciden (la cola del muslo y la cabeza de la canilla son la rodilla):
// mover uno mueve todos. El root y el polo de la rodilla no se editan (el polo sigue a la rodilla).
function agrupar(J) {
  const puntos = []
  for (const [n, par] of Object.entries(J)) {
    if (n === 'root' || n.startsWith('knee_pole')) continue
    par.forEach((c, e) => {
      let p = puntos.find(p => p.c.every((v, i) => Math.abs(v - c[i]) < 1e-4))
      if (!p) puntos.push(p = { c, miembros: [] })
      p.miembros.push([n, e])
    })
  }
  return puntos.map((p, id) => {
    const claves = p.miembros.map(([n, e]) => `${base(n)}.${e}`)
    const nombre = NOMBRES.find(k => claves.includes(k)) || claves[0]
    const lados = [...new Set(p.miembros.map(([n]) => lado(n)).filter(Boolean))]
    return { id, miembros: p.miembros, nombre, lado: lados[0], centro: p.miembros.every(([n]) => CENTRO.includes(n)) }
  })
}

// de frente, lo del lado .S se dibuja en +x y espejado en -x, salvo que el json traiga ese lado suelto (.L/.R)
function espejos(nombres, J) {
  if (nombres.some(n => lado(n) !== 'S')) return [1]
  return [1, -1].filter(s => !nombres.some(n => `${base(n)}.${s > 0 ? 'L' : 'R'}` in J))
}

const copiar = J => JSON.parse(JSON.stringify(J))

export function EditorArticulaciones({ d, cerrar }) {
  const [g, setG] = useState(null)
  const [error, setError] = useState(null)
  const [J, setJ] = useState(null)
  const [historial, setHistorial] = useState([])
  const [sel, setSel] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [guardadas, setGuardadas] = useState(false)
  const puntos = useRef([])
  const actual = useRef(null)   // las últimas (las flechas seguidas no esperan a que se vuelva a dibujar)
  actual.current = J
  const ruta = `assets/${encodeURIComponent(d.nombre)}/articulaciones`
  const empezar = x => { setG(x); setJ(copiar(x.articulaciones)); puntos.current = agrupar(x.articulaciones); setHistorial([]); setSel(null) }
  const cargar = () => api(ruta).then(x => { empezar(x); setError(null) }, e => setError(e.message))
  useEffect(() => { cargar() }, [d.nombre])
  if (error) return html`<${Error} error=${error} reintentar=${cargar} />`
  if (!g || !J) return html`<${Cargando} />`

  const cambiado = JSON.stringify(J) !== JSON.stringify(g.articulaciones)
  const ppu = g.px / g.ortho
  const aPx = (h, z) => [g.px / 2 + h * ppu, g.px / 2 - (z - g.centro_z) * ppu]
  const deUnidades = (u, v) => [(u - g.px / 2) / ppu, g.centro_z - (v - g.px / 2) / ppu]
  const coord = p => J[p.miembros[0][0]][p.miembros[0][1]]

  const recordar = () => setHistorial(h => [...h.slice(-49), copiar(actual.current)])
  // mueve el punto: el eje horizontal de la vista (con el signo del espejo) y z; el polo de la rodilla la sigue
  const mover = (p, eje, h, z, Jbase = actual.current) => {
    const N = copiar(Jbase)
    for (const [n, e] of p.miembros) {
      const c = N[n][e]
      if (!(p.centro && eje === 0)) c[eje] = Math.round(h * 1000) / 1000
      c[2] = Math.round(z * 1000) / 1000
    }
    for (const n of Object.keys(N).filter(n => n.startsWith('knee_pole'))) {
      const muslo = N['thigh.' + lado(n)]
      if (!muslo) continue
      for (const c of N[n]) { c[0] = muslo[1][0]; c[2] = muslo[1][2] }
    }
    setJ(N)
    actual.current = N
    return N
  }
  const deshacer = () => { if (historial.length) { setJ(historial.at(-1)); setHistorial(historial.slice(0, -1)) } }
  const guardar = async () => {
    setGuardando(true)
    try {
      empezar(await api(ruta, { metodo: 'PUT', cuerpo: { articulaciones: J } }))
      setGuardadas(true)
      aviso(t('art.guardadas'))
    } catch (e) { aviso(e.message, 'error') }
    setGuardando(false)
  }
  const elegido = puntos.current.find(p => p.id === sel)

  return html`<div class="editor-art">
    <p class="tenue chico" style="margin:0 0 10px">${t('art.ayuda')}</p>
    <div class="editor-art-vistas">${VISTAS.map(([vista, eje]) => html`<${Vista} key=${vista} vista=${vista} eje=${eje}
      g=${g} J=${J} puntos=${puntos.current} sel=${sel} setSel=${setSel} aPx=${aPx} deUnidades=${deUnidades}
      url=${urlArchivo(d.nombre, g[vista], g.version)} recordar=${recordar} mover=${mover} actual=${actual} />`)}</div>
    <div class="editor-art-pie">
      <span class="chico" aria-live="polite" style="min-width:0;overflow-wrap:anywhere">${elegido
        ? html`<b>${t('art.p.' + elegido.nombre)}${elegido.lado && elegido.lado !== 'S' ? ` (${elegido.lado})` : ''}</b>
            <span class="mono"> x ${coord(elegido)[0].toFixed(3)} · y ${coord(elegido)[1].toFixed(3)} · z ${coord(elegido)[2].toFixed(3)}</span>`
        : html`<span class="tenue">${t(g.origen === 'estimadas' ? 'art.estimadas' : g.fuente === 'a mano' ? 'art.a_mano' : 'art.cargadas')}</span>`}</span>
      <div class="acciones">
        <button class="boton chico fantasma" disabled=${!historial.length} onClick=${deshacer}><${Icono} n="rehacer" />${t('art.deshacer')}</button>
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

function Vista({ vista, eje, g, J, puntos, sel, setSel, aPx, deUnidades, url, recordar, mover, actual }) {
  const svg = useRef(null)
  const arrastre = useRef(null)
  const de = (n, e, s) => { const c = J[n][e]; return aPx(c[eje] * (eje === 0 ? s : 1), c[2]) }
  // recorte horizontal: lo que ocupa el esqueleto (los renders son cuadrados y el personaje, angosto), al menos 60 %
  const us = Object.entries(J).filter(([n]) => !SIN_DIBUJAR(n)).flatMap(([, par]) => par.map(c => Math.abs(c[eje]) * g.px / g.ortho))
  const medio = Math.min(g.px / 2, Math.max(g.px * 0.3, Math.max(...us) + g.px * 0.08))
  const caja = [g.px / 2 - medio, 0, medio * 2, g.px]
  const r = g.px * 0.011
  const enSvg = ev => {
    const p = svg.current.createSVGPoint()
    p.x = ev.clientX; p.y = ev.clientY
    return p.matrixTransform(svg.current.getScreenCTM().inverse())
  }
  const bajar = (ev, p, s) => {
    ev.preventDefault()
    ev.currentTarget.setPointerCapture(ev.pointerId)
    recordar()
    setSel(p.id)
    const q = enSvg(ev), [x, y] = de(...p.miembros[0], s)
    arrastre.current = { p, s, J, dx: q.x - x, dy: q.y - y }   // sin saltar al cursor: conserva dónde se agarró
  }
  const moverPuntero = ev => {
    const a = arrastre.current
    if (!a) return
    const q = enSvg(ev)
    const [h, z] = deUnidades(q.x - a.dx, q.y - a.dy)
    a.J = mover(a.p, eje, h * (eje === 0 ? a.s : 1), z, a.J)
  }
  const tecla = (ev, p, s) => {
    const dir = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[ev.key]
    if (!dir) return
    ev.preventDefault()
    recordar()
    setSel(p.id)
    const paso = ev.shiftKey ? 0.02 : 0.004
    const c = actual.current[p.miembros[0][0]][p.miembros[0][1]]
    mover(p, eje, c[eje] + dir[0] * paso * (eje === 0 ? s : 1), c[2] + dir[1] * paso)
  }
  const huesos = Object.keys(J).filter(n => !SIN_DIBUJAR(n))
  return html`<figure class="editor-art-vista">
    <figcaption class="tenue chico">${t('art.' + vista)}</figcaption>
    <svg ref=${svg} viewBox=${caja.join(' ')} onPointerMove=${moverPuntero} onPointerUp=${() => { arrastre.current = null }}
      onPointerCancel=${() => { arrastre.current = null }} role="group" aria-label=${t('art.' + vista)}>
      <image href=${url} x="0" y="0" width=${g.px} height=${g.px} />
      <line x1=${aPx(0, 0)[0]} y1="0" x2=${aPx(0, 0)[0]} y2=${g.px} class="art-eje" />
      ${huesos.flatMap(n => (eje === 0 ? espejos([n], J) : [1]).map(s => {
        const [a, b] = [de(n, 0, s), de(n, 1, s)]
        return html`<line key=${n + s} x1=${a[0]} y1=${a[1]} x2=${b[0]} y2=${b[1]} class=${'art-hueso' + (s < 0 ? ' espejo' : '')} />`
      }))}
      ${puntos.flatMap(p => (eje === 0 ? espejos(p.miembros.map(([n]) => n), J) : [1]).map(s => {
        const [x, y] = de(...p.miembros[0], s)
        const titulo = t('art.p.' + p.nombre) + (p.lado && p.lado !== 'S' ? ` (${p.lado})` : '')
        return html`<g key=${p.id + '_' + s} class=${'art-punto' + (p.id === sel ? ' elegido' : '') + (s < 0 ? ' espejo' : '')}
          tabindex="0" role="button" aria-label=${titulo} aria-pressed=${p.id === sel}
          onPointerDown=${ev => bajar(ev, p, s)} onKeyDown=${ev => tecla(ev, p, s)} onFocus=${() => setSel(p.id)}>
          <title>${titulo}</title>
          <circle cx=${x} cy=${y} r=${r * 2.8} class="toque" />
          <circle cx=${x} cy=${y} r=${p.id === sel ? r * 1.35 : r} class="marca" />
        </g>`
      }))}
    </svg>
  </figure>`
}
