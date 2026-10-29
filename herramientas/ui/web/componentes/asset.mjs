// Un asset: la cadena de pasos con su estado (correr, rehacer), lo que falta elegir, el visor de resultados (con el
// reproductor iso por dirección), los ajustes y los archivos/logs.
import {
  html, useState, useEffect, useRef, useGlobal, api, t, urlArchivo, urlMini, Icono, Chip, Cargando, Error, verGrande,
  trabajosDe, encolar, nombrePaso, docPaso, ayudaPaso, urlReadme, aviso, duracion, Colada, transcurrido, Plegable,
} from '../comunes.mjs'
import { Ajustes } from './ajustes.mjs'
import { Visor3D } from './visor3d.mjs'

// pasos que no están en la cadena de `crisol estado` pero se pueden correr a mano
const EXTRA = {
  personaje: ['ultratex', 'retrato'],
  objeto: ['ultratex'],
  vehiculo: [],
  escenario: [],
}

function useDetalle(nombre) {
  const g = useGlobal()
  const [d, setD] = useState(null)
  const [error, setError] = useState(null)
  const cargar = () => api('assets/' + encodeURIComponent(nombre)).then(x => { setD(x); setError(null) }, e => setError(e.message))
  useEffect(() => { cargar() }, [nombre, g.versionAssets])
  return { d, error, cargar }
}

function bloqueado(paso, d) {
  const claves = (d.decidir || []).map(x => x.clave)
  if (paso !== 'imagen' && claves.includes('imagen.elegida')) return true
  if (paso === 'tema' && claves.some(c => c.startsWith('texturas.'))) return true
  return false
}

function BotonPaso({ d, paso, estado, cola, doctor, principal }) {
  const { corriendo, pendientes } = trabajosDe(cola, d.nombre)
  const falta = doctor?.deshabilitados?.[paso]
  if (corriendo?.paso === paso) return html`<${Chip} clase="corriendo">${t('asset.corriendo')}<//>`
  if (pendientes.some(x => x.paso === paso)) return html`<${Chip} clase="pendiente-cola">${t('asset.en_cola')}<//>`
  const rehacer = estado === 'hecho' || estado === 'viejo'
  const off = !!falta || bloqueado(paso, d)
  const titulo = falta ? t('asset.no_disponible', { falta: falta.join('; ') }) : bloqueado(paso, d) ? t('asset.elegir_primero') : docPaso(paso, d.tipo)
  return html`<button class=${'boton chico' + (principal ? ' primario' : '')} disabled=${off} title=${titulo}
      onClick=${() => encolar({ paso, nombre: d.nombre })}>
    <${Icono} n=${rehacer ? 'rehacer' : 'correr'} />${t(rehacer ? 'asset.rehacer' : 'asset.correr')}</button>`
}

// la ayuda extendida de un paso ("Más" en la cadena): qué hace, qué mirar, qué probar si sale mal y su sección del
// README; ocupa todo el ancho de la fila (en la columna del medio no entra)
function AyudaPaso({ a }) {
  return html`<dl class="ayuda-paso">
    <dt>${t('ayuda.hace')}</dt><dd>${a.hace}</dd>
    <dt>${t('ayuda.mirar')}</dt><dd>${a.mirar}</dd>
    <dt>${t('ayuda.mal')}</dt><dd>${a.mal}</dd>
    <dd><a href=${urlReadme(a.readme)} target="_blank" rel="noopener">${t('ayuda.readme')}</a></dd>
  </dl>`
}

// el número de cada paso en la cadena (1, 2...): el mismo lleva su resultado en el visor
const numeros = d => Object.fromEntries(d.pasos.filter(p => p.estado !== 'no_aplica').map((p, i) => [p.paso, i + 1]))

// qué elección cambia cada paso de la cadena (un paso puede tener varias: texturas)
const ELIGE = { imagen: c => c === 'imagen.elegida', malla: c => c === 'malla.elegida', texturas: c => c.startsWith('texturas.') }

function Cadena({ d, cola, doctor, cambiar }) {
  const { corriendo, pendientes } = trabajosDe(cola, d.nombre)
  const [ayuda, setAyuda] = useState(null)   // el paso con la ayuda abierta
  const siguiente = d.siguiente?.split(' ')[1]
  const extra = (EXTRA[d.tipo] || []).filter(p => !(p === 'ultratex' && !d.json?.malla?.ultratex))
  if (d.json?.malla?.candidatos && !d.json.vehiculo) extra.push('comparar')   // los vehículos comparan en `blender`
  const pasos = d.pasos.filter(p => p.estado !== 'no_aplica')
  const resumen = t('asset.hechos', { h: pasos.filter(p => p.estado === 'hecho').length, n: pasos.length }) +
    (siguiente ? ' · ' + t('asset.siguiente', { paso: nombrePaso(siguiente, d.tipo) }) : '')
  return html`<section class="panel"><${Plegable} titulo=${t('asset.cadena')} resumen=${resumen}>
    <ol class="cadena">
      ${pasos.map((p, i) => {
        const enMarcha = corriendo?.paso === p.paso ? 'corriendo' : pendientes.some(x => x.paso === p.paso) ? 'en-cola' : ''
        const falta = doctor?.deshabilitados?.[p.paso]
        return html`<li class=${[p.estado, enMarcha, falta ? 'apagado' : ''].join(' ')} key=${p.paso}>
          <span class="marca-paso">${p.estado === 'hecho' ? html`<${Icono} n="check" />` : p.estado === 'viejo' ? html`<${Icono} n="rehacer" />` : ''}</span>
          <div style="min-width:0">
            <div class="nombre-paso"><span class="num-paso">${i + 1}.</span>${nombrePaso(p.paso, d.tipo)}</div>
            <div class="doc-paso">${docPaso(p.paso, d.tipo)}
              ${ayudaPaso(p.paso, d.tipo) && html` <button class="mas-ayuda" aria-expanded=${ayuda === p.paso}
                onClick=${() => setAyuda(ayuda === p.paso ? null : p.paso)}>${t(ayuda === p.paso ? 'ayuda.menos' : 'ayuda.mas')}</button>`}</div>
            <div class="nota">${t('estado.' + p.estado)}${p.nota ? ': ' + p.nota : ''}</div>
            ${corriendo?.paso === p.paso && html`<div style="margin-top:8px"><${Colada} tr=${corriendo} cola=${cola} /></div>`}
            ${ELIGE[p.paso] && d.elecciones.some(e => ELIGE[p.paso](e.clave) && e.actual != null && !d.decidir.some(x => x.clave === e.clave)) &&
              html`<button class="boton chico fantasma" style="padding:0;min-height:28px;color:var(--brasa)"
                onClick=${() => cambiar(d.elecciones.filter(e => ELIGE[p.paso](e.clave)).map(e => e.clave))}>${t('decidir.cambiar')}</button>`}
          </div>
          <${BotonPaso} d=${d} paso=${p.paso} estado=${p.estado} cola=${cola} doctor=${doctor} principal=${p.paso === siguiente} />
          ${ayuda === p.paso && html`<${AyudaPaso} a=${ayudaPaso(p.paso, d.tipo)} />`}
        </li>`
      })}
    </ol>
    ${extra.length > 0 && html`<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px">
      ${extra.map(p => html`<button class="boton chico" title=${docPaso(p)} disabled=${!!doctor?.deshabilitados?.[p] || bloqueado(p, d) ||
          corriendo?.paso === p || pendientes.some(x => x.paso === p)}
        onClick=${() => encolar({ paso: p, nombre: d.nombre })}><${Icono} n="correr" />${nombrePaso(p)}</button>`)}
    </div>`}
  <//></section>`
}

// ---------- decidir ----------
// guarda la elección (solo con el clic de la persona) y avisa
function useElegir(d, dec, recargar, listo) {
  const [guardando, setGuardando] = useState(null)
  const elegir = async valor => {
    setGuardando(valor)
    try {
      await api(`assets/${encodeURIComponent(d.nombre)}/elegir`, { metodo: 'POST', cuerpo: { clave: dec.clave, valor } })
      aviso(t('decidir.elegida', { v: valor }))
      listo?.()
      recargar()
    } catch (e) { aviso(e.message, 'error') }
    setGuardando(null)
  }
  return { guardando, elegir }
}

function Decision({ d, dec, recargar, listo }) {
  const { guardando, elegir } = useElegir(d, dec, recargar, listo)
  const textura = dec.clave.startsWith('texturas.') ? dec.clave.split('.')[1] : null
  const [mosaico, setMosaico] = useState(false)
  const titulo = textura ? t('decidir.textura', { k: textura }) : t('decidir.' + dec.clave)
  const conImagen = dec.opciones.filter(o => o.imagen)
  const esActual = o => dec.actual != null && String(dec.actual) === String(o.valor)
  return html`<div style="display:grid;gap:12px">
    <header style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
      <h3>${titulo}</h3>
      ${dec.nota && html`<span class="tenue chico">${dec.nota}</span>`}
      ${textura && conImagen.length > 0 && html`<label class="casilla chico" style="margin-left:auto">
        <input type="checkbox" checked=${mosaico} onChange=${e => setMosaico(e.target.checked)} />${t('decidir.mosaico')}</label>`}
    </header>
    ${conImagen.length > 0
      ? html`<div class="opciones">${dec.opciones.map(o => html`<article class="opcion" key=${o.valor}>
          <button class="arte damero" onClick=${() => verGrande(urlArchivo(d.nombre, o.imagen), t('decidir.opcion', { v: o.valor }))}
              aria-label=${t('visor.ampliar') + ': ' + o.valor}
              style=${mosaico ? { backgroundImage: `url(${urlMini(d.nombre, o.imagen, 300)})`, backgroundSize: '50%' } : null}>
            ${!mosaico && o.imagen && html`<img src=${urlMini(d.nombre, o.imagen, 520)} alt="" loading="lazy" />`}
          </button>
          <footer><span class="mono">${o.valor}</span>
            ${esActual(o)
              ? html`<${Chip} clase="hecho">${t('decidir.actual')}<//>`
              : html`<button class="boton chico primario" disabled=${guardando !== null} onClick=${() => elegir(o.valor)}>${t('decidir.elegir')}</button>`}
          </footer></article>`)}</div>`
      : html`${dec.mirar && html`<button class="hoja-decidir damero" onClick=${() => verGrande(urlArchivo(d.nombre, dec.mirar), t('decidir.hoja'))}>
            <img src=${urlMini(d.nombre, dec.mirar, 1400)} alt=${t('decidir.hoja')} /></button>`}
          <div class="botones-opcion">${dec.opciones.map(o => esActual(o)
            ? html`<${Chip} clase="hecho" key=${o.valor}>${t('decidir.actual')}: ${o.valor}<//>`
            : html`<button class="boton primario" key=${o.valor} disabled=${guardando !== null}
                onClick=${() => elegir(o.valor)}>${t('decidir.elegir')}: ${o.valor}</button>`)}</div>`}
  </div>`
}

// los candidatos de malla: una tarjeta por candidato (el principal y los de malla.candidatos) con sus vistas (todas
// las tarjetas en la misma vista, a elegir arriba), cómo se hace, si ya está generado y su visor 3D en la tarjeta
const MOTOR = { trellis2: 'TRELLIS.2', pixal3d: 'Pixal3D' }

function comoSeHace(o) {
  const ut = o.ultratex != null ? t('decidir.cand_ultratex', { s: o.ultratex }) : null
  if (o.desde) return [t('decidir.cand_desde', { d: o.desde }), ut].filter(Boolean).join(' · ')
  return [MOTOR[o.motor] || o.motor, o.seed != null && t('decidir.cand_seed', { s: o.seed }), o.resolucion, ut].filter(Boolean).join(' · ')
}

function TarjetaMalla({ d, o, vista, actual, abierto, alternar3d, elegir, guardando }) {
  const v = o.vistas.find(x => x.id === vista) || o.vistas[0]
  const ver = Math.round(d.modificado)
  return html`<article class=${'opcion tarjeta-malla' + (actual ? ' actual' : '')}>
    ${abierto
      ? html`<${Visor3D} url=${urlArchivo(d.nombre, o.glb, ver)} titulo=${o.valor} />`
      : v
        ? html`<button class="arte damero" onClick=${() => verGrande(urlArchivo(d.nombre, v.imagen, ver), `${o.valor}: ${t('vista.' + v.id)}`)}
              aria-label=${`${t('visor.ampliar')}: ${o.valor}, ${t('vista.' + v.id)}`}>
            <img src=${urlMini(d.nombre, v.imagen, 520, v.centro ? '&centro=1' : '', ver)} alt="" loading="lazy" />
            ${v.vieja && html`<span class="marca-vieja"><${Chip} clase="viejo">${t('decidir.vista_vieja')}<//></span>`}
          </button>`
        : html`<div class="arte sin-arte"><${Icono} n="cubo" />
            <span>${t(o.hecho ? 'decidir.sin_vistas' : 'cand.falta')}</span></div>`}
    <footer>
      <div class="titulo-cand"><span class="mono">${o.valor}</span>
        ${actual && html`<${Chip} clase="hecho">${t('decidir.actual')}<//>`}</div>
      <p class="tenue chico">${comoSeHace(o)}</p>
      <div class="botones-opcion">
        ${o.glb && html`<button class="boton chico" aria-pressed=${abierto} onClick=${alternar3d}>
          <${Icono} n="cubo" />${t(abierto ? 'decidir.ocultar_3d' : 'decidir.ver_3d')}</button>`}
        ${!actual && html`<button class="boton chico primario" style="margin-left:auto" disabled=${guardando !== null}
          title=${o.hecho ? '' : t('decidir.elegir_sin_generar')} onClick=${() => elegir(o.valor)}>${t('decidir.elegir')}</button>`}
      </div>
    </footer>
  </article>`
}

function DecisionMalla({ d, dec, recargar, listo }) {
  const { guardando, elegir } = useElegir(d, dec, recargar, listo)
  const ops = dec.opciones
  const vistas = [...new Set(ops.flatMap(o => o.vistas.map(v => v.id)))]
  const [vista, setVista] = useState(null)
  const [en3d, setEn3d] = useState([])   // los que la persona abre en 3D (hasta 3: un contexto WebGL cada uno)
  const con3d = ops.filter(o => o.glb)
  const alternar3d = v => setEn3d(en3d.includes(v) ? en3d.filter(x => x !== v) : [...en3d, v].slice(-3))
  // generados sin vistas propias (de antes de que `comparar` las guardara): queda la hoja de siempre
  const sinVistas = ops.some(o => o.hecho && !o.vistas.length)
  const pasoVistas = d.json?.vehiculo ? 'blender' : 'comparar'
  return html`<div style="display:grid;gap:12px">
    <header style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
      <h3>${t('decidir.malla.elegida')}</h3>
      ${dec.nota && html`<span class="tenue chico">${dec.nota}</span>`}
      ${con3d.length > 1 && html`<button class="boton chico" style="margin-left:auto"
        onClick=${() => setEn3d(en3d.length ? [] : con3d.slice(0, 3).map(o => o.valor))}><${Icono} n="cubo" />
        ${t(en3d.length ? 'decidir.cerrar_3d' : 'decidir.comparar_3d')}</button>`}
    </header>
    ${vistas.length > 1 && html`<div class="segmentos desplazable" role="group" aria-label=${t('decidir.vista')}>
      ${vistas.map(v => html`<button aria-pressed=${(vista || vistas[0]) === v} onClick=${() => setVista(v)}>${t('vista.' + v)}</button>`)}</div>`}
    ${sinVistas && html`<div class="aviso"><${Icono} n="info" /><p style="flex:1">${t('decidir.sin_vistas_ayuda', { paso: nombrePaso(pasoVistas, d.tipo) })}</p>
      <button class="boton chico" onClick=${() => encolar({ paso: pasoVistas, nombre: d.nombre })}><${Icono} n="correr" />${nombrePaso(pasoVistas, d.tipo)}</button></div>`}
    ${sinVistas && dec.mirar && html`<button class="hoja-decidir damero" onClick=${() => verGrande(urlArchivo(d.nombre, dec.mirar), t('decidir.hoja'))}>
      <img src=${urlMini(d.nombre, dec.mirar, 1400, '', Math.round(d.modificado))} alt=${t('decidir.hoja')} /></button>`}
    <div class="opciones tarjetas-malla">${ops.map(o => html`<${TarjetaMalla} key=${o.valor} d=${d} o=${o} vista=${vista || vistas[0]}
      actual=${dec.actual != null && String(dec.actual) === String(o.valor)} abierto=${en3d.includes(o.valor)}
      alternar3d=${() => alternar3d(o.valor)} elegir=${elegir} guardando=${guardando} />`)}</div>
  </div>`
}

function Decidir({ d, recargar, cambiando, setCambiando }) {
  // lo que falta elegir, más lo que la persona pidió cambiar (con la opción actual marcada)
  const lista = [...d.decidir, ...d.elecciones.filter(e => cambiando?.includes(e.clave) && !d.decidir.some(x => x.clave === e.clave))]
  if (!lista.length) return null
  return html`<section class="panel decidir" style="margin-bottom:20px">
    <header><h2>${t('decidir.titulo')}</h2>
      ${cambiando && html`<button class="boton chico fantasma" style="margin-left:auto" onClick=${() => setCambiando(null)}>${t('decidir.no_cambiar')}</button>`}
      <p class="tenue chico" style="flex-basis:100%">${t('decidir.ayuda')}</p></header>
    <div style="display:grid;gap:26px">${lista.map(dec => html`<${dec.clave === 'malla.elegida' ? DecisionMalla : Decision} key=${dec.clave} d=${d} dec=${dec} recargar=${recargar}
      listo=${() => setCambiando(null)} />`)}</div>
  </section>`
}

// ---------- lo que pidió mirar el último paso ----------
function Mirar({ d, cola }) {
  const ultimo = [...cola.trabajos].reverse().find(x => x.nombre === d.nombre && x.estado === 'hecho')
  const [cerrado, setCerrado] = useState(null)
  const rutas = (ultimo?.resultado?.mirar || []).filter(r => r.startsWith(d.carpeta + '/')).map(r => r.slice(d.carpeta.length + 1))
  if (!ultimo || !rutas.length || cerrado === ultimo.id || Date.now() / 1000 - ultimo.fin > 3600) return null
  return html`<section class="aviso brasa" style="margin-bottom:20px;flex-wrap:wrap">
    <${Icono} n="info" />
    <div style="flex:1;display:grid;gap:10px;min-width:0">
      <b>${t('asset.mirar')} (${nombrePaso(ultimo.paso, d.tipo)})</b>
      <div class="tira" style="padding:0">${rutas.map(r => html`<button onClick=${() => verGrande(urlArchivo(d.nombre, r, ultimo.fin), r)} title=${r}
        class="damero" style="width:120px;height:120px"><img src=${urlMini(d.nombre, r, 240, '', Math.round(ultimo.fin))} alt=${r} /></button>`)}</div>
    </div>
    <button class="icono-boton" onClick=${() => setCerrado(ultimo.id)} aria-label=${t('visor.cerrar')}><${Icono} n="x" /></button>
  </section>`
}

// ---------- visor ----------
export function ReproductorIso({ nombre, meta, version }) {
  const anims = Object.keys(meta.animaciones)
  const [anim, setAnim] = useState(anims.includes('walk') ? 'walk' : anims[0])
  const [dir, setDir] = useState('s')
  const [pausa, setPausa] = useState(false)
  const lienzo = useRef(null)
  const a = meta.animaciones[anim]
  useEffect(() => {
    const img = new Image()
    let cuadro = 0, timer = null, vivo = true
    const fila = meta.direcciones.indexOf(dir)
    const dibujar = () => {
      const c = lienzo.current
      if (!c || !img.complete || !vivo) return
      const ctx = c.getContext('2d')
      ctx.clearRect(0, 0, c.width, c.height)
      ctx.drawImage(img, cuadro * meta.frame_width, fila * meta.frame_height, meta.frame_width, meta.frame_height, 0, 0, c.width, c.height)
    }
    img.onload = () => {
      dibujar()
      if (pausa || a.frames < 2) return
      timer = setInterval(() => {
        cuadro = cuadro + 1 >= a.frames ? (a.loop ? 0 : a.frames - 1) : cuadro + 1
        if (!a.loop && cuadro === a.frames - 1) setTimeout(() => { cuadro = 0 }, 700)
        dibujar()
      }, 1000 / Math.max(1, a.fps))
    }
    img.src = urlArchivo(nombre, `${meta.carpeta}/${a.imagen}`, version)
    return () => { vivo = false; clearInterval(timer) }
  }, [anim, dir, pausa, version])
  // la rosa: la pantalla vista desde arriba (n arriba)
  const ROSA = [['nw', 'n', 'ne'], ['w', null, 'e'], ['sw', 's', 'se']]
  return html`<div class="iso">
    <div class="damero visor nitido" style="min-height:0"><canvas ref=${lienzo} width=${meta.frame_width} height=${meta.frame_height} aria-label=${`${anim} ${dir}`} /></div>
    <div class="controles-iso">
      <select class="entrada" value=${anim} onChange=${e => setAnim(e.target.value)} aria-label=${t('visor.animacion')}>
        ${anims.map(x => html`<option value=${x}>${x}</option>`)}
      </select>
      <div class="rosa" role="group" aria-label=${t('visor.direccion')}>
        ${ROSA.flat().map(x => x ? html`<button aria-pressed=${dir === x} onClick=${() => setDir(x)}>${x.toUpperCase()}</button>`
          : html`<span class="centro"><${Icono} n="punto" /></span>`)}
      </div>
      <button class="boton chico" onClick=${() => setPausa(!pausa)}><${Icono} n=${pausa ? 'correr' : 'pausa'} />${t(pausa ? 'visor.reproducir' : 'visor.pausa')}</button>
    </div>
  </div>`
}

function Visor({ d }) {
  // en el orden de la cadena (con su número); se abre en el primero de antes: el resultado más terminado
  const porDefecto = [...(d.iso ? [{ id: 'iso_reproductor', paso: 'iso' }] : []), ...d.visuales]
  const num = numeros(d)
  const grupos = porDefecto.map(x => ({ ...x, n: num[x.paso] })).sort((a, b) => (a.n ?? 99) - (b.n ?? 99))
  const [gid, setGid] = useState(porDefecto[0]?.id)
  const [i, setI] = useState(0)
  const [nitido, setNitido] = useState(false)
  useEffect(() => { if (!grupos.some(g => g.id === gid)) setGid(porDefecto[0]?.id) }, [d])
  if (!grupos.length) return html`<div class="vacio"><p>${t('asset.sin_resultado')}</p></div>`
  const g = grupos.find(x => x.id === gid) || grupos[0]
  const v = Math.round(d.modificado)
  const archivo = g.archivos?.[Math.min(i, g.archivos.length - 1)]
  const etiqueta = id => id === 'iso_reproductor' ? t('visor.iso') : id === 'iso' ? t('visor.iso_gif') : t('visor.' + id)
  return html`<div>
    <div class="segmentos desplazable" role="group" style="margin-bottom:14px">${grupos.map(x => html`<button aria-pressed=${x.id === g.id}
      onClick=${() => { setGid(x.id); setI(0) }}>${x.n ? html`<span class="num-paso">${x.n}</span>` : ''}${etiqueta(x.id)}</button>`)}</div>
    ${g.id === 'iso_reproductor'
      ? html`<${ReproductorIso} nombre=${d.nombre} meta=${d.iso} version=${v} />`
      : g.id === '3d'
      ? html`<${Visor3D} url=${urlArchivo(d.nombre, archivo, v)} key=${archivo} />
          <p class="mono tenue" style="margin-top:8px;overflow-wrap:anywhere">${archivo}</p>`
      : html`<div class=${'visor damero' + (nitido ? ' nitido' : '')}>
          <img src=${archivo.endsWith('.gif') ? urlArchivo(d.nombre, archivo, v) : urlMini(d.nombre, archivo, 1400, '', v)} alt=${archivo} />
          <div class="herramientas">
            <button class="icono-boton" style="background:var(--superficie-2)" aria-pressed=${nitido} title=${t('visor.nitido')}
              onClick=${() => setNitido(!nitido)}><${Icono} n="biblioteca" titulo=${t('visor.nitido')} /></button>
            <button class="icono-boton" style="background:var(--superficie-2)" title=${t('visor.ampliar')}
              onClick=${() => verGrande(urlArchivo(d.nombre, archivo, v), archivo)}><${Icono} n="ampliar" titulo=${t('visor.ampliar')} /></button>
          </div>
        </div>
        ${g.archivos.length > 1 && html`<div class="tira">${g.archivos.map((x, k) => html`<button class="damero" aria-pressed=${k === i}
          onClick=${() => setI(k)} title=${x}><img src=${urlMini(d.nombre, x, 160, '', v)} alt=${x} /></button>`)}</div>`}
        <p class="mono tenue" style="margin-top:8px;overflow-wrap:anywhere">${archivo}</p>`}
  </div>`
}

// ---------- archivos y logs ----------
function Archivos({ d, cola }) {
  const [log, setLog] = useState(null)
  const ver = async (titulo, url) => {
    try {
      const r = await fetch(url)
      setLog({ titulo, texto: await r.text() })
    } catch (e) { aviso(e.message, 'error') }
  }
  const trabajos = cola.trabajos.filter(x => x.nombre === d.nombre || (x.paso === 'rehacer' && x.nombre.split(',').includes(d.nombre))).reverse()
  const lic = d.licencias
  return html`<div style="display:grid;gap:20px">
    ${lic && html`<section class="panel"><header><h2>${t('asset.licencias')}</h2>
        <${Chip} clase=${lic.comercial ? 'hecho' : 'fallo'}>${t(lic.comercial ? 'asset.comercial' : 'asset.no_comercial')}<//></header>
      <ul style="margin:0;padding-left:18px;display:grid;gap:4px">${(lic.modelos || []).map(m => html`<li>
        <b>${m.nombre}</b> <span class="tenue">${m.licencia}</span></li>`)}</ul>
      ${lic.nota && html`<p class="tenue chico" style="margin-top:10px">${lic.nota}</p>`}</section>`}
    <section class="panel">
      <header><h2>${t('asset.carpeta')}</h2></header>
      <p class="mono" style="overflow-wrap:anywhere">${d.carpeta}</p>
      <p class="tenue chico" style="margin-top:6px">${t('asset.json')}: <span class="mono">${d.archivo_json}</span></p>
    </section>
    <section class="panel">
      <header><h2>${t('asset.logs')}</h2></header>
      ${trabajos.length + d.logs.length === 0 && html`<p class="tenue">${t('asset.sin_logs')}</p>`}
      <ul class="lista-cola">
        ${trabajos.map(x => html`<li key=${x.id}>
          <div class="que"><b>${nombrePaso(x.paso, x.tipo)}</b> <span class="tenue chico">${new Date(x.creado * 1000).toLocaleString()}</span></div>
          <${Chip} clase=${x.estado === 'hecho' ? 'hecho' : x.estado === 'fallo' ? 'fallo' : x.estado === 'corriendo' ? 'corriendo' : ''}>${t('cola.estado.' + x.estado)}<//>
          <button class="boton chico" onClick=${() => ver(nombrePaso(x.paso, x.tipo), `/api/trabajos/${x.id}/log`)}><${Icono} n="log" />${t('cola.ver_log')}</button>
        </li>`)}
        ${d.logs.map(r => html`<li key=${r}><div class="que mono">${r}</div>
          <button class="boton chico" onClick=${() => ver(r, `/api/assets/${encodeURIComponent(d.nombre)}/log?ruta=${encodeURIComponent(r)}`)}>
            <${Icono} n="log" />${t('cola.ver_log')}</button></li>`)}
      </ul>
      ${log && html`<div style="margin-top:14px;display:grid;gap:8px">
        <div style="display:flex;align-items:center;gap:8px"><b>${log.titulo}</b>
          <button class="boton chico fantasma" style="margin-left:auto" onClick=${() => setLog(null)}>${t('cola.ocultar_log')}</button></div>
        <pre class="consola">${log.texto || '—'}</pre></div>`}
    </section>
  </div>`
}

// ---------- pantalla ----------
export function Asset({ nombre, pestana }) {
  const g = useGlobal()
  const { d, error, cargar } = useDetalle(nombre)
  const [cambiando, setCambiando] = useState(null)
  if (error) return html`<a class="migas" href="#/"><${Icono} n="atras" />${t('nav.biblioteca')}</a><${Error} error=${error} reintentar=${cargar} />`
  if (!d) return html`<${Cargando} />`
  const { corriendo } = trabajosDe(g.cola, d.nombre)
  const siguiente = d.siguiente?.split(' ')[1]
  const ir = p => { location.hash = `#/a/${encodeURIComponent(nombre)}${p === 'resultado' ? '' : '/' + p}` }
  return html`
    <a class="migas" href="#/"><${Icono} n="atras" />${t('nav.biblioteca')}</a>
    <header class="encabezado">
      <div class="asset-titulo"><h1>${d.nombre}</h1>
        <${Chip}>${t('tipo.' + d.tipo)}<//><${Chip}>${d.estilo}<//>
        ${d.licencias && !d.licencias.comercial && html`<${Chip} clase="fallo">${t('asset.no_comercial')}<//>`}
      </div>
      <div class="acciones">
        ${corriendo
          ? html`<a class="boton" href="#/cola"><${Icono} n="cola" />${nombrePaso(corriendo.paso, d.tipo)}: ${duracion(transcurrido(corriendo, g.cola))}</a>`
          : siguiente
            ? html`<button class="boton primario" disabled=${!!g.doctor?.deshabilitados?.[siguiente]}
                onClick=${() => encolar({ paso: siguiente, nombre: d.nombre })}><${Icono} n="correr" />${t('asset.siguiente', { paso: nombrePaso(siguiente, d.tipo) })}</button>`
            : d.decidir.length
              ? html`<span class="tenue">${t('asset.elegir_primero')}</span>`
              : html`<${Chip} clase="hecho">${t('asset.completo')}<//>`}
      </div>
    </header>
    <${Decidir} d=${d} recargar=${cargar} cambiando=${cambiando} setCambiando=${setCambiando} />
    <${Mirar} d=${d} cola=${g.cola} />
    <div class="dos-columnas">
      <${Cadena} d=${d} cola=${g.cola} doctor=${g.doctor} cambiar=${c => { setCambiando(c); scrollTo({ top: 0, behavior: 'smooth' }) }} />
      <section class="panel" style="min-width:0">
        <div class="pestanas" role="tablist">
          ${['resultado', 'ajustes', 'archivos'].map(p => html`<button role="tab" aria-selected=${pestana === p} onClick=${() => ir(p)}>${t('asset.' + p)}</button>`)}
        </div>
        ${pestana === 'ajustes' ? html`<${Ajustes} d=${d} recargar=${cargar} />`
          : pestana === 'archivos' ? html`<${Archivos} d=${d} cola=${g.cola} />`
          : html`<${Visor} d=${d} />`}
      </section>
    </div>`
}
