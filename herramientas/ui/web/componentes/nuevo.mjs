// Crear un asset: tipo (receta), referencia y/o descripción, estilo y nombre. Crea con `crisol nuevo` y lleva al
// asset, donde el primer paso se lanza a mano.
import { html, useState, useEffect, useRef, api, t, aviso, Icono, Cargando, Error } from '../comunes.mjs'

const NOMBRE = /^[a-z0-9][a-z0-9_]{0,47}$/
const ORDEN = ['humanoide', 'chibi', 'robot', 'juguete', 'objeto', 'vegetacion', 'vehiculo', 'escenario']

function sugerirNombre(texto) {
  return (texto || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').split('_').slice(0, 3).join('_').slice(0, 40)
}

function Soltar({ subida, setSubida }) {
  const [encima, setEncima] = useState(false)
  const [subiendo, setSubiendo] = useState(false)
  const entrada = useRef(null)
  const subir = async archivo => {
    if (!archivo || !archivo.type.startsWith('image/')) return
    setSubiendo(true)
    try {
      const { id } = await api('subidas', { metodo: 'POST', crudo: archivo })
      setSubida({ id, url: URL.createObjectURL(archivo), nombre: archivo.name })
    } catch (e) { aviso(e.message, 'error') }
    setSubiendo(false)
  }
  if (subida) {
    return html`<div class="soltar" style="cursor:default">
      <img src=${subida.url} alt=${subida.nombre} />
      <span class="chico">${subida.nombre}</span>
      <button class="boton chico" onClick=${() => setSubida(null)}><${Icono} n="x" />${t('nuevo.quitar_imagen')}</button>
    </div>`
  }
  return html`<div class=${'soltar' + (encima ? ' encima' : '')} role="button" tabindex="0"
      onClick=${() => entrada.current.click()} onKeyDown=${e => (e.key === 'Enter' || e.key === ' ') && entrada.current.click()}
      onDragOver=${e => { e.preventDefault(); setEncima(true) }} onDragLeave=${() => setEncima(false)}
      onDrop=${e => { e.preventDefault(); setEncima(false); subir(e.dataTransfer.files[0]) }}>
    <${Icono} n="subir" />
    <span>${subiendo ? t('nuevo.subiendo') : t('nuevo.soltar')}</span>
    <input ref=${entrada} type="file" accept="image/*" class="oculto" onChange=${e => subir(e.target.files[0])} />
  </div>`
}

export function Nuevo() {
  const [cat, setCat] = useState(null)
  const [error, setError] = useState(null)
  const [receta, setReceta] = useState('humanoide')
  const [subida, setSubida] = useState(null)
  const [descripcion, setDescripcion] = useState('')
  const [estilo, setEstilo] = useState('')
  const [nombre, setNombre] = useState('')
  const [nombreTocado, setNombreTocado] = useState(false)
  const [creando, setCreando] = useState(false)
  const cargar = () => Promise.all([api('recetas'), api('estilos'), api('assets')])
    .then(([recetas, estilos, assets]) => setCat({ recetas, estilos, existentes: new Set(assets.assets.map(a => a.nombre)) }), e => setError(e.message))
  useEffect(() => { cargar() }, [])
  useEffect(() => { if (!nombreTocado) setNombre(sugerirNombre(descripcion) || sugerirNombre(subida?.nombre?.replace(/\.[a-z]+$/i, ''))) }, [descripcion, subida])
  if (error) return html`<${Error} error=${error} reintentar=${cargar} />`
  if (!cat) return html`<${Cargando} />`
  const r = cat.recetas.find(x => x.id === receta)
  const escenario = r?.base === 'escenario'
  const nombreMal = nombre && !NOMBRE.test(nombre)
  const existe = cat.existentes.has(nombre)
  const faltaDescripcion = !escenario && !subida && !descripcion.trim()
  const puede = nombre && !nombreMal && !existe && !faltaDescripcion && !creando
  const crear = async () => {
    setCreando(true)
    try {
      const d = await api('assets', { metodo: 'POST', cuerpo: {
        nombre, receta, descripcion: escenario ? null : descripcion.trim() || null, subida: subida?.id, estilo: estilo || null } })
      aviso(t('nuevo.creado', { n: nombre }))
      location.hash = '#/a/' + encodeURIComponent(d.nombre)
    } catch (e) { aviso(e.message, 'error') }
    setCreando(false)
  }
  return html`
    <header class="encabezado"><h1>${t('nuevo.titulo')}</h1></header>
    <div class="pasos-nuevo">
      <section class="panel">
        <h2>${t('nuevo.tipo')}</h2>
        <div class="recetas" role="group">${ORDEN.map(id => cat.recetas.find(x => x.id === id)).concat(cat.recetas.filter(x => !ORDEN.includes(x.id)))
          .filter(Boolean).map(x => html`<button class="eleccion" aria-pressed=${receta === x.id}
            onClick=${() => setReceta(x.id)} key=${x.id} title=${x.doc}>
          <b>${t('receta.' + x.id) === 'receta.' + x.id ? x.id : t('receta.' + x.id)}</b>
          <p>${t('recetadoc.' + x.id) === 'recetadoc.' + x.id ? x.doc : t('recetadoc.' + x.id)}</p></button>`)}</div>
      </section>
      <section class="panel" style="display:grid;gap:16px">
        <div class="campo"><h2>${t('nuevo.referencia')}</h2><small>${t('nuevo.referencia_ayuda')}</small></div>
        <${Soltar} subida=${subida} setSubida=${setSubida} />
        ${escenario
          ? html`<p class="tenue chico">${t('nuevo.escenario_nota')}</p>`
          : html`<label class="campo"><span>${t('nuevo.descripcion')}</span>
              <textarea class="entrada" lang="en" placeholder="a young blacksmith in a leather apron and work boots, short hair"
                value=${descripcion} onInput=${e => setDescripcion(e.target.value)} aria-invalid=${faltaDescripcion && nombreTocado} />
              <small>${t('nuevo.descripcion_ayuda')}</small>
              ${faltaDescripcion && html`<small>${t('nuevo.descripcion_falta')}</small>`}</label>`}
      </section>
      <section class="panel">
        <h2>${t('nuevo.estilo')}</h2>
        <div class="estilos" role="group">
          <button class="eleccion" aria-pressed=${estilo === ''} onClick=${() => setEstilo('')}>
            <b>${t('nuevo.estilo_receta')}</b><p>${cat.estilos.defecto}</p></button>
          ${cat.estilos.estilos.map(e => html`<button class="eleccion" key=${e.id} aria-pressed=${estilo === e.id} onClick=${() => setEstilo(e.id)} title=${e.doc}>
            <b>${e.id}</b><p>${e.doc}</p></button>`)}
        </div>
      </section>
      <section class="panel" style="display:grid;gap:16px">
        <label class="campo"><span>${t('nuevo.nombre')}</span>
          <input class="entrada mono" value=${nombre} autocapitalize="off" spellcheck="false" aria-invalid=${nombreMal || existe}
            onInput=${e => { setNombre(e.target.value); setNombreTocado(true) }} />
          <small>${nombreMal ? t('nuevo.nombre_mal') : existe ? t('nuevo.nombre_existe') : t('nuevo.nombre_ayuda')}</small></label>
        <div><button class="boton primario" disabled=${!puede} onClick=${crear}>
          <${Icono} n="nuevo" />${creando ? t('nuevo.creando') : t('nuevo.crear')}</button></div>
      </section>
    </div>`
}
