// Visor 3D de un .glb (la malla, un candidato, el vehículo armado): three.js vendorizado (vendor/three/), que se carga
// recién cuando se abre un visor. Sin fondo (el damero de la página queda detrás), luces suaves, girar y zoom con el
// mouse o el dedo, encuadre por la caja del modelo. Al desmontar libera geometrías, texturas y el contexto WebGL.
// Con `animaciones` (el personaje con rig, trabajo/animado.glb) reproduce la elegida al ritmo de los sprites.
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

// El tiempo del glTF para `s` segundos de reproducción: los cuadros de los sprites a su fps, interpolando entre uno y
// el siguiente (en loop, el último va hacia `fin`, la pose que cierra el ciclo); sin loop, 700 ms quieto en el último
// y vuelve a empezar, como el reproductor iso. a: {tiempos, fin, fps, loop} (servidor.animado)
export function tiempoAnimado(a, s) {
  const n = a.tiempos.length
  if (n < 2) return a.tiempos[0] || 0
  let x
  if (a.loop) x = (s * a.fps) % n
  else {
    const dur = (n - 1) / a.fps, u = s % (dur + 0.7)
    if (u >= dur) return a.tiempos[n - 1]
    x = u * a.fps
  }
  const i = Math.floor(x), f = x - i
  const sig = i + 1 < n ? a.tiempos[i + 1] : a.fin
  return a.tiempos[i] + (sig - a.tiempos[i]) * f
}

function liberar(obj) {
  obj.traverse(o => {
    o.geometry?.dispose()
    for (const m of [].concat(o.material || [])) {
      for (const v of Object.values(m)) if (v?.isTexture) v.dispose()
      m.dispose()
    }
  })
}

export function Visor3D({ url, titulo, alto, animaciones }) {
  const caja = useRef(null)
  const api = useRef(null)   // {reiniciar, girar(bool)}
  const [estado, setEstado] = useState('cargando')   // cargando | listo | error
  const [progreso, setProgreso] = useState(0)
  const [error, setError] = useState(null)
  const [girar, setGirar] = useState(false)
  const nombres = Object.keys(animaciones || {})
  const [anim, setAnim] = useState(nombres.includes('walk') ? 'walk' : nombres[0])
  const [pausa, setPausa] = useState(quieto())
  const reproduccion = useRef({ s: 0, antes: null })   // segundos reproducidos de la animación elegida

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
      let mixer = null, clip = null
      const dibujar = () => {
        cuadro = requestAnimationFrame(dibujar)
        const r = reproduccion.current, ahora = performance.now()
        if (mixer && clip && r.a) {
          if (!r.pausa && r.antes !== null) r.s += (ahora - r.antes) / 1000
          mixer.setTime(Math.max(0, Math.min(tiempoAnimado(r.a, r.s), clip.duration - 1e-4)))
        }
        r.antes = ahora
        controles.update()
        renderer.render(escena, camara)
      }
      let modelo = null
      new GLTFLoader().load(url, gltf => {
        if (!vivo) { liberar(gltf.scene); return }
        modelo = gltf.scene
        escena.add(modelo)
        // en poses que salen de la caja de reposo (rodar, saltar) three la tomaba como fuera de cámara
        modelo.traverse(o => { if (o.isSkinnedMesh) o.frustumCulled = false })
        if (gltf.animations.length) {
          mixer = new THREE.AnimationMixer(modelo)
          api.current.clips = Object.fromEntries(gltf.animations.map(c => [c.name, c]))
        }
        // encuadre: el modelo centrado, la cámara a una distancia que lo muestra entero, un poco desde arriba
        // (con la geometría en reposo: en una malla con rig, setFromObject usa los huesos, que al cargar no están
        // puestos, y la caja quedaba en los pies)
        modelo.updateMatrixWorld(true)
        const bb = new THREE.Box3()
        modelo.traverse(o => {
          if (!o.isMesh) return
          o.geometry.computeBoundingBox()
          bb.union(o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld))
        })
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
        animar: nombreClip => {
          if (!mixer) return
          mixer.stopAllAction()
          clip = api.current.clips[nombreClip] || null
          if (clip) mixer.clipAction(clip).play()
        },
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
  useEffect(() => {   // la animación elegida desde el principio; la pausa la deja donde está
    const a = animaciones?.[anim]
    Object.assign(reproduccion.current, { a, s: 0 })
    if (estado === 'listo' && a) api.current?.animar(a.clip)
  }, [anim, estado, animaciones])
  useEffect(() => { reproduccion.current.pausa = pausa }, [pausa])

  const visor = html`<div class="visor3d damero" style=${alto ? { height: alto } : null}>
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
  if (!nombres.length) return visor
  return html`<div>${visor}
    <div class="controles-iso" style="margin-top:10px">
      <select class="entrada" value=${anim} onChange=${e => setAnim(e.target.value)} aria-label=${t('visor.animacion')}>
        ${nombres.map(x => html`<option value=${x}>${x}</option>`)}
      </select>
      <button class="boton chico" onClick=${() => setPausa(!pausa)}><${Icono} n=${pausa ? 'correr' : 'pausa'} />${t(pausa ? 'visor.reproducir' : 'visor.pausa')}</button>
    </div>
  </div>`
}
