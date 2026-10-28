// Visor 3D de un .glb (la malla, un candidato, el vehículo armado): three.js vendorizado (vendor/three/), que se carga
// recién cuando se abre un visor. Sin fondo (el damero de la página queda detrás), luces suaves, girar y zoom con el
// mouse o el dedo, encuadre por la caja del modelo. Al desmontar libera geometrías, texturas y el contexto WebGL.
import { html, useState, useEffect, useRef, t, Icono } from '../comunes.mjs'

let three = null   // los módulos, una sola vez
function cargarThree() {
  three ??= Promise.all([
    import('../vendor/three/three.module.min.js'),
    import('../vendor/three/GLTFLoader.js'),
    import('../vendor/three/OrbitControls.js'),
  ]).then(([THREE, { GLTFLoader }, { OrbitControls }]) => ({ THREE, GLTFLoader, OrbitControls }))
  return three
}

const quieto = () => matchMedia('(prefers-reduced-motion: reduce)').matches

function liberar(obj) {
  obj.traverse(o => {
    o.geometry?.dispose()
    for (const m of [].concat(o.material || [])) {
      for (const v of Object.values(m)) if (v?.isTexture) v.dispose()
      m.dispose()
    }
  })
}

export function Visor3D({ url, titulo, alto }) {
  const caja = useRef(null)
  const api = useRef(null)   // {reiniciar, girar(bool)}
  const [estado, setEstado] = useState('cargando')   // cargando | listo | error
  const [progreso, setProgreso] = useState(0)
  const [error, setError] = useState(null)
  const [girar, setGirar] = useState(false)

  useEffect(() => {
    let vivo = true, cuadro = 0, limpiar = () => {}
    setEstado('cargando'); setProgreso(0); setError(null)
    cargarThree().then(({ THREE, GLTFLoader, OrbitControls }) => {
      if (!vivo) return
      const el = caja.current
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
      renderer.outputColorSpace = THREE.SRGBColorSpace
      renderer.setClearColor(0x000000, 0)
      el.appendChild(renderer.domElement)
      const escena = new THREE.Scene()
      escena.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 2.2))
      const sol = new THREE.DirectionalLight(0xffffff, 1.6)
      sol.position.set(2, 4, 3)
      escena.add(sol)
      const camara = new THREE.PerspectiveCamera(35, 1, 0.01, 1000)
      const controles = new OrbitControls(camara, renderer.domElement)
      controles.enableDamping = true
      controles.screenSpacePanning = true
      controles.autoRotateSpeed = 1.5
      // con el dedo: deslizar de costado gira y en vertical baja la página (touch-action: pan-y en el CSS); dos
      // dedos acercan y giran
      controles.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_ROTATE }
      let inicial = null   // {pos, centro} para reiniciar
      const medir = () => {
        const w = el.clientWidth || 300, h = el.clientHeight || 300
        renderer.setSize(w, h, false)
        camara.aspect = w / h
        camara.updateProjectionMatrix()
      }
      const obs = new ResizeObserver(medir)
      obs.observe(el)
      medir()
      const dibujar = () => {
        cuadro = requestAnimationFrame(dibujar)
        controles.update()
        renderer.render(escena, camara)
      }
      let modelo = null
      new GLTFLoader().load(url, gltf => {
        if (!vivo) { liberar(gltf.scene); return }
        modelo = gltf.scene
        escena.add(modelo)
        // encuadre: el modelo centrado, la cámara a una distancia que lo muestra entero, un poco desde arriba
        const bb = new THREE.Box3().setFromObject(modelo)
        const centro = bb.getCenter(new THREE.Vector3()), tam = bb.getSize(new THREE.Vector3())
        const radio = Math.max(tam.length() / 2, 1e-3)
        const dist = radio / Math.sin((camara.fov * Math.PI) / 360) * 1.05
        const dir = new THREE.Vector3(0.35, 0.3, 1).normalize()
        inicial = { pos: centro.clone().addScaledVector(dir, dist), centro }
        camara.near = dist / 100; camara.far = dist * 100
        controles.minDistance = radio * 0.3; controles.maxDistance = dist * 4
        api.current.reiniciar()
        setEstado('listo')
      }, ev => { if (ev.total) setProgreso(ev.loaded / ev.total) },
      e => { if (vivo) { setError(e?.message || String(e)); setEstado('error') } })
      api.current = {
        reiniciar: () => {
          if (!inicial) return
          camara.position.copy(inicial.pos)
          controles.target.copy(inicial.centro)
          camara.updateProjectionMatrix()
          controles.update()
        },
        girar: si => { controles.autoRotate = si },
      }
      dibujar()
      limpiar = () => {
        cancelAnimationFrame(cuadro)
        obs.disconnect()
        controles.dispose()
        if (modelo) liberar(modelo)
        renderer.dispose()
        renderer.forceContextLoss()
        renderer.domElement.remove()
      }
    }, e => { if (vivo) { setError(e?.message || String(e)); setEstado('error') } })
    return () => { vivo = false; limpiar(); api.current = null }
  }, [url])

  useEffect(() => { api.current?.girar(girar && !quieto()) }, [girar, estado])

  return html`<div class="visor3d damero" style=${alto ? { height: alto } : null}>
    <div class="lienzo3d" ref=${caja} aria-label=${titulo || t('visor.3d')} role="img" />
    ${estado === 'cargando' && html`<div class="estado3d" role="status">
      <span>${t('visor.3d_cargando')}${progreso ? ` ${Math.round(progreso * 100)} %` : ''}</span>
      <div class="colada"><i style=${{ width: progreso * 100 + '%' }} /></div></div>`}
    ${estado === 'error' && html`<div class="estado3d error" role="alert"><${Icono} n="alerta" /><span>${t('visor.3d_error', { e: error })}</span></div>`}
    ${titulo && html`<span class="titulo3d mono">${titulo}</span>`}
    ${estado === 'listo' && html`<div class="herramientas">
      <button class="icono-boton" style="background:var(--superficie-2)" aria-pressed=${girar} title=${t('visor.3d_girar')}
        onClick=${() => setGirar(!girar)}><${Icono} n="rehacer" titulo=${t('visor.3d_girar')} /></button>
      <button class="icono-boton" style="background:var(--superficie-2)" title=${t('visor.3d_reiniciar')}
        onClick=${() => api.current?.reiniciar()}><${Icono} n="centrar" titulo=${t('visor.3d_reiniciar')} /></button>
    </div>`}
    ${estado === 'listo' && html`<span class="ayuda3d">${t(matchMedia('(pointer: coarse)').matches ? 'visor.3d_ayuda_tactil' : 'visor.3d_ayuda')}</span>`}
  </div>`
}
