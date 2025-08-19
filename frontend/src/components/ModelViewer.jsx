import React, { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

export default function ModelViewer({ url }) {
  const mountRef = useRef(null)
  const rendererRef = useRef(null)

  useEffect(() => {
    const mount = mountRef.current
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xf5f5f7)

    const camera = new THREE.PerspectiveCamera(60, mount.clientWidth / mount.clientHeight, 0.01, 1000)
    camera.position.set(0.4, 0.4, 0.6)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    mount.appendChild(renderer.domElement)
    rendererRef.current = renderer

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true

    // Lights
    const hemi = new THREE.HemisphereLight(0xffffff, 0x444444, 1.0)
    scene.add(hemi)
    const dir = new THREE.DirectionalLight(0xffffff, 0.8)
    dir.position.set(1, 1, 1)
    scene.add(dir)

    // Grid + Axes
    const grid = new THREE.GridHelper(1, 10)
    scene.add(grid)
    const axes = new THREE.AxesHelper(0.2)
    scene.add(axes)

    let mesh

    if (url) {
      const loader = new PLYLoader()
      loader.load(url, geometry => {
        geometry.computeVertexNormals()
        const material = new THREE.MeshStandardMaterial({ metalness: 0.1, roughness: 0.8 })
        mesh = new THREE.Mesh(geometry, material)
        geometry.center()

        // Fit view
        const bbox = new THREE.Box3().setFromObject(mesh)
        const size = bbox.getSize(new THREE.Vector3()).length()
        const center = bbox.getCenter(new THREE.Vector3())
        controls.target.copy(center)
        camera.near = size / 100
        camera.far = size * 10
        camera.updateProjectionMatrix()
        camera.position.copy(center).add(new THREE.Vector3(size * 0.4, size * 0.4, size * 0.6))

        scene.add(mesh)
      })
    }

    const onResize = () => {
      const { clientWidth, clientHeight } = mount
      camera.aspect = clientWidth / clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(clientWidth, clientHeight)
    }
    window.addEventListener('resize', onResize)

    const animate = () => {
      controls.update()
      renderer.render(scene, camera)
      requestAnimationFrame(animate)
    }
    animate()

    return () => {
      window.removeEventListener('resize', onResize)
      if (mesh) mesh.geometry.dispose()
      renderer.dispose()
      mount.removeChild(renderer.domElement)
    }
  }, [url])

  return <div ref={mountRef} style={{ width: '100%', height: '520px', borderRadius: 16, overflow: 'hidden', boxShadow: '0 6px 24px rgba(0,0,0,0.08)', background: '#fff' }} />
}