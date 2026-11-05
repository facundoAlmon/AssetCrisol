// Editor del retrato (Resultado > Retrato): un cuadro 4:5 sobre la fuente entera (la imagen sin fondo o el render de
// frente del modelo) que se arrastra y se agranda o achica, con la vista previa del recorte. Guarda retrato.fuente y
// retrato.caja.<fuente> (fracciones de la fuente; Automático la borra) con PUT api/assets/<n>/retrato y encola
// `crisol retrato`: con la imagen es un recorte (sin Blender), con el modelo la caja pasa a la cámara.
import { html, useState, useEffect, useRef, api, t, urlArchivo, Icono, Cargando, Error, aviso, encolar } from '../comunes.mjs'

const ASPECTO = 0.8   // ancho / alto del retrato, en píxeles

// el cuadro por defecto si no hay caja ni automática: arriba al centro, un tercio del alto
function porDefecto(f) {
  const h = 0.33, w = h * f.alto * ASPECTO / f.ancho
  return [0.5 - w / 2, 0.02, 0.5 + w / 2, 0.02 + h]
}

// alto en fracciones -> ancho en fracciones, para que el cuadro sea 4:5 en píxeles de la fuente
const anchoDe = (h, f) => h * f.alto * ASPECTO / f.ancho

function encajar(c, f) {
  let [x0, y0, x1, y1] = c
  let h = Math.min(Math.max(y1 - y0, 0.04), 1)
  let w = anchoDe(h, f)
  if (w > 1) { w = 1; h = w * f.ancho / (f.alto * ASPECTO) }
  x0 = Math.min(Math.max(x0, 0), 1 - w)
  y0 = Math.min(Math.max(y0, 0), 1 - h)
  return [x0, y0, x0 + w, y0 + h]
}

function Vista({ d, f, caja }) {
  const lienzo = useRef(null)
  const img = useRef(null)
  const dibujar = () => {
    const c = lienzo.current, im = img.current
    if (!c || !im?.complete || !im.naturalWidth) return
    const g = c.getContext('2d')
    g.clearRect(0, 0, c.width, c.height)
    const [x0, y0, x1, y1] = caja
    g.drawImage(im, x0 * im.naturalWidth, y0 * im.naturalHeight, (x1 - x0) * im.naturalWidth, (y1 - y0) * im.naturalHeight,
      0, 0, c.width, c.height)
  }
  useEffect(() => {
    const im = new Image()
    im.onload = dibujar
    im.src = urlArchivo(d.nombre, f.ruta, Math.round(f.fecha))
    img.current = im
  }, [f.ruta, f.fecha])
  useEffect(dibujar, [caja])
  return html`<canvas ref=${lienzo} width="200" height="250" class="damero retrato-vista" aria-label=${t('retrato.vista')} />`
}

export function EditorRetrato({ d, cerrar }) {
  const [r, setR] = useState(null)
  const [error, setError] = useState(null)
  const [fuente, setFuente] = useState(null)
  const [caja, setCaja] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const escenario = useRef(null)
  const arrastre = useRef(null)
  const url = `assets/${encodeURIComponent(d.nombre)}/retrato`
  const cargar = () => api(url).then(x => {
    setR(x)
    const fu = x.fuentes[x.fuente] ? x.fuente : (x.fuentes.imagen ? 'imagen' : 'modelo')
    setFuente(fu)
  }, e => setError(e.message))
  useEffect(() => { cargar() }, [])
  const f = r && fuente ? r.fuentes[fuente] : null
  useEffect(() => {
    if (f) setCaja(encajar(r.caja[fuente] || f.auto || porDefecto(f), f))
  }, [r, fuente])
  if (error) return html`<${Error} error=${error} reintentar=${cargar} />`
  if (!r || !f || !caja) return html`<${Cargando} />`

  const mover = (dx, dy) => setCaja(c => encajar([c[0] + dx, c[1] + dy, c[2] + dx, c[3] + dy], f))
  const escalar = k => setCaja(c => {   // desde el centro
    const h = (c[3] - c[1]) * k, w = anchoDe(h, f), cx = (c[0] + c[2]) / 2, cy = (c[1] + c[3]) / 2
    return encajar([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], f)
  })
  const empezar = (e, modo) => {
    e.preventDefault(); e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    arrastre.current = { modo, x: e.clientX, y: e.clientY, caja, rect: escenario.current.getBoundingClientRect() }
  }
  const seguir = e => {
    const a = arrastre.current
    if (!a) return
    const dx = (e.clientX - a.x) / a.rect.width, dy = (e.clientY - a.y) / a.rect.height
    const [x0, y0, x1, y1] = a.caja
    if (a.modo === 'mover') setCaja(encajar([x0 + dx, y0 + dy, x1 + dx, y1 + dy], f))
    else {   // la esquina de abajo a la derecha: el alto manda (4:5), la de arriba a la izquierda queda
      const h = Math.max(y1 - y0 + Math.max(dy, dx * f.ancho / (f.alto * ASPECTO)), 0.04)
      setCaja(encajar([x0, y0, x0 + anchoDe(h, f), y0 + h], f))
    }
  }
  const soltar = () => { arrastre.current = null }
  const teclas = e => {
    const p = e.shiftKey ? 0.05 : 0.01
    const k = { ArrowLeft: [-p, 0], ArrowRight: [p, 0], ArrowUp: [0, -p], ArrowDown: [0, p] }[e.key]
    if (k) { e.preventDefault(); mover(...k) }
    if (e.key === '+' || e.key === '=') { e.preventDefault(); escalar(1.05) }
    if (e.key === '-') { e.preventDefault(); escalar(1 / 1.05) }
  }
  const guardar = async automatico => {
    setGuardando(true)
    try {
      await api(url, { metodo: 'PUT', cuerpo: { fuente, caja: automatico ? null : caja.map(x => +x.toFixed(4)) } })
      await encolar({ paso: 'retrato', nombre: d.nombre })
      aviso(t('retrato.guardado'))
      cerrar()
    } catch (e) { aviso(e.message, 'error'); setGuardando(false) }
  }
  const anchoPx = Math.round((caja[2] - caja[0]) * f.ancho)
  // la imagen (1024 px) ya se agranda ~2× en el automático: avisar cuando se agranda bastante más
  const agranda = r.ancho_px / Math.max(anchoPx, 1)
  const borroso = fuente === 'imagen' && agranda > 2.4
  const [x0, y0, x1, y1] = caja.map(v => v * 100)
  return html`<div class="editor-retrato">
    <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
      <b>${t('retrato.titulo')}</b>
      <div class="segmentos" role="group" aria-label=${t('retrato.fuente')} style="margin-left:auto">
        ${['imagen', 'modelo'].map(x => html`<button aria-pressed=${fuente === x} disabled=${!r.fuentes[x]}
          title=${!r.fuentes[x] ? t('retrato.sin_' + x) : null} onClick=${() => setFuente(x)}>${t('retrato.de_' + x)}</button>`)}
      </div>
    </div>
    <p class="tenue chico">${t('retrato.ayuda')}</p>
    ${fuente === 'imagen' && r.vieja && html`<div class="aviso brasa chico"><${Icono} n="alerta" />
      <p>${t('retrato.vieja', { e: r.elegida })}</p></div>`}
    <div class="retrato-cuerpo">
      <div class="retrato-escenario damero" ref=${escenario} onPointerMove=${seguir} onPointerUp=${soltar} onPointerCancel=${soltar}>
        <img src=${urlArchivo(d.nombre, f.ruta, Math.round(f.fecha))} alt=${f.ruta} draggable="false" />
        <div class="retrato-caja" tabindex="0" role="slider" aria-label=${t('retrato.caja')}
          aria-valuetext=${`${Math.round(x0)}%, ${Math.round(y0)}%, ${anchoPx}px`}
          style=${{ left: x0 + '%', top: y0 + '%', width: (x1 - x0) + '%', height: (y1 - y0) + '%' }}
          onPointerDown=${e => empezar(e, 'mover')} onKeyDown=${teclas}>
          <span class="retrato-asa" onPointerDown=${e => empezar(e, 'escalar')} aria-hidden="true" />
        </div>
      </div>
      <div style="display:grid;gap:10px;align-content:start;justify-items:start">
        <${Vista} d=${d} f=${f} caja=${caja} />
        <span class="tenue chico mono">${anchoPx} × ${Math.round(anchoPx / ASPECTO)} px</span>
        <div style="display:flex;gap:6px">
          <button class="icono-boton" title=${t('retrato.alejar')} aria-label=${t('retrato.alejar')} onClick=${() => escalar(1.08)}>−</button>
          <button class="icono-boton" title=${t('retrato.acercar')} aria-label=${t('retrato.acercar')} onClick=${() => escalar(1 / 1.08)}>+</button>
        </div>
        ${borroso && html`<p class="chico" style="color:var(--error);max-width:200px">${t('retrato.borroso', { a: anchoPx, b: r.ancho_px, f: agranda.toFixed(1) })}</p>`}
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="boton primario" disabled=${guardando} onClick=${() => guardar(false)}>${t('retrato.guardar')}</button>
      <button class="boton" disabled=${guardando || (!r.caja[fuente] && r.fuente === fuente)} onClick=${() => guardar(true)}
        title=${t('retrato.automatico_ayuda')}>${t('retrato.automatico')}</button>
      <button class="boton fantasma" onClick=${cerrar}>${t('ren.cancelar')}</button>
    </div>
  </div>`
}
