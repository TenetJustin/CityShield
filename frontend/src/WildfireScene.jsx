import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const COLORS = {
  low: 0x245f4d,
  watch: 0xbda449,
  elevated: 0xee8139,
  severe: 0xe5422d,
};

function riskColor(risk) {
  if (risk >= 0.6) return COLORS.severe;
  if (risk >= 0.3) return COLORS.elevated;
  if (risk >= 0.1) return COLORS.watch;
  return COLORS.low;
}

function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose();
    if (Array.isArray(child.material)) child.material.forEach((material) => material.dispose());
    else child.material?.dispose();
  });
}

export default function WildfireScene({ cells, selectedCell, onSelect, resetSignal }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const onSelectRef = useRef(onSelect);
  const [supported, setSupported] = useState(true);

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      setSupported(false);
      return undefined;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b1b19);
    scene.fog = new THREE.Fog(0x0b1b19, 13, 28);
    const camera = new THREE.PerspectiveCamera(43, 1, 0.1, 100);
    camera.position.set(8, 10, 10);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0);
    controls.enableDamping = true;
    controls.minDistance = 5;
    controls.maxDistance = 22;
    controls.maxPolarAngle = Math.PI / 2.15;
    controls.update();

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);
    scene.add(new THREE.AmbientLight(0xa8c9ba, 2.1));
    const sun = new THREE.DirectionalLight(0xffc98d, 2.5);
    sun.position.set(-5, 10, 6);
    scene.add(sun);
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(30, 30),
      new THREE.MeshStandardMaterial({ color: 0x122d27, roughness: 1 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.07;
    scene.add(ground);
    const grid = new THREE.GridHelper(22, 22, 0x315b50, 0x22483f);
    grid.position.y = -0.04;
    scene.add(grid);

    const state = { scene, camera, controls, renderer, model: null, tiles: [], flames: [] };
    sceneRef.current = state;
    let pointerDown = null;
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const handlePointerDown = (event) => { pointerDown = [event.clientX, event.clientY]; };
    const handlePointerUp = (event) => {
      if (!pointerDown || Math.hypot(event.clientX - pointerDown[0], event.clientY - pointerDown[1]) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(state.tiles, false)[0];
      if (hit) onSelectRef.current(hit.object.userData.cellId);
    };
    renderer.domElement.addEventListener("pointerdown", handlePointerDown);
    renderer.domElement.addEventListener("pointerup", handlePointerUp);

    const resize = () => {
      const width = Math.max(mount.clientWidth, 1);
      const height = Math.max(mount.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(mount);
    resize();

    const clock = new THREE.Clock();
    let frame;
    const animate = () => {
      const time = clock.getElapsedTime();
      state.flames.forEach((flame, index) => {
        flame.scale.y = flame.userData.baseScale * (0.88 + Math.sin(time * 5 + index) * 0.12);
        flame.rotation.y += 0.01;
      });
      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      controls.dispose();
      if (state.model) disposeObject(state.model);
      ground.geometry.dispose();
      ground.material.dispose();
      grid.geometry.dispose();
      grid.material.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      sceneRef.current = null;
    };
  }, []);

  useEffect(() => {
    const state = sceneRef.current;
    if (!state) return;
    if (state.model) {
      state.scene.remove(state.model);
      disposeObject(state.model);
    }
    const model = new THREE.Group();
    const tiles = [];
    const flames = [];
    const rows = cells.map((cell) => cell.row);
    const cols = cells.map((cell) => cell.col);
    const centerRow = rows.length ? (Math.min(...rows) + Math.max(...rows)) / 2 : 1;
    const centerCol = cols.length ? (Math.min(...cols) + Math.max(...cols)) / 2 : 1;

    cells.forEach((cell) => {
      const x = (cell.col - centerCol) * 1.85;
      const z = (cell.row - centerRow) * 1.85;
      const elevation = 0.25 + Math.max(0, Math.min(1, cell.slope || 0)) * 0.9;
      const material = new THREE.MeshStandardMaterial({
        color: riskColor(cell.risk), roughness: 0.78, metalness: 0.02,
        emissive: cell.id === selectedCell ? 0x276d67 : 0x000000,
        emissiveIntensity: 0.55,
      });
      const tile = new THREE.Mesh(new THREE.BoxGeometry(1.7, elevation, 1.7), material);
      tile.position.set(x, elevation / 2, z);
      tile.userData.cellId = cell.id;
      model.add(tile);
      tiles.push(tile);

      const borderSource = new THREE.BoxGeometry(1.72, elevation + 0.02, 1.72);
      const borderGeometry = new THREE.EdgesGeometry(borderSource);
      borderSource.dispose();
      const border = new THREE.LineSegments(
        borderGeometry,
        new THREE.LineBasicMaterial({ color: cell.id === selectedCell ? 0xf6f3cb : 0x5f8879 }),
      );
      border.position.copy(tile.position);
      model.add(border);

      if (cell.risk >= 0.08) {
        const count = cell.risk >= 0.6 ? 3 : cell.risk >= 0.3 ? 2 : 1;
        for (let index = 0; index < count; index += 1) {
          const height = (0.45 + cell.risk * 1.2) * (index === 0 ? 1 : 0.72);
          const flame = new THREE.Mesh(
            new THREE.ConeGeometry(0.12 + cell.risk * 0.14, height, 5),
            new THREE.MeshBasicMaterial({
              color: index === 0 ? 0xffd56b : 0xff673d,
              transparent: true, opacity: 0.92,
            }),
          );
          flame.position.set(x + (index - 1) * 0.35, elevation + height / 2, z + (index % 2) * 0.22);
          flame.userData.baseScale = 1;
          flames.push(flame);
          model.add(flame);
        }
      }
    });
    state.model = model;
    state.tiles = tiles;
    state.flames = flames;
    state.scene.add(model);
  }, [cells, selectedCell]);

  useEffect(() => {
    if (!sceneRef.current) return;
    const { camera, controls } = sceneRef.current;
    camera.position.set(8, 10, 10);
    controls.target.set(0, 0, 0);
    controls.update();
  }, [resetSignal]);

  return (
    <div className="sceneWrap">
      <div className="sceneCanvas" ref={mountRef} role="img" aria-label="Interactive three-dimensional wildfire risk grid" />
      {!supported && <div className="sceneFallback">This browser cannot display WebGL. Use the risk list below.</div>}
      {!cells.length && <div className="sceneFallback">Start the demo to see the wildfire world state.</div>}
      <div className="sceneHint">Drag to rotate · Scroll to zoom · Click a cell</div>
    </div>
  );
}
