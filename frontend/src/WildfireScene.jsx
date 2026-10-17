import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { riskColor } from "./riskVisual.js";

function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose();
    if (Array.isArray(child.material)) child.material.forEach((material) => material.dispose());
    else child.material?.dispose();
  });
}

export default function WildfireScene({
  cells,
  selectedCell,
  onSelect,
  resetSignal,
  showObserved = false,
  showHotspots = false,
  resources = [],
}) {
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
    scene.background = new THREE.Color(0x102d22);
    scene.fog = new THREE.Fog(0x102d22, 13, 28);
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
    scene.add(new THREE.AmbientLight(0xe4eee6, 1.85));
    const sun = new THREE.DirectionalLight(0xd7a84b, 2.4);
    sun.position.set(-5, 10, 6);
    scene.add(sun);
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(30, 30),
      new THREE.MeshStandardMaterial({ color: 0x173a2c, roughness: 1 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.07;
    scene.add(ground);
    const grid = new THREE.GridHelper(22, 22, 0x527765, 0x294f3d);
    grid.position.y = -0.04;
    scene.add(grid);

    const state = { scene, camera, controls, renderer, model: null, tiles: [], flames: [], hotspots: [] };
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

    const animationStartedAt = performance.now();
    let frame;
    const animate = (timestamp) => {
      const time = (timestamp - animationStartedAt) / 1000;
      state.flames.forEach((flame, index) => {
        flame.scale.y = flame.userData.baseScale * (0.88 + Math.sin(time * 5 + index) * 0.12);
        flame.rotation.y += 0.01;
      });
      state.hotspots.forEach((hotspot, index) => {
        const pulse = 0.85 + Math.sin(time * 4.5 + index) * 0.2;
        hotspot.scale.setScalar(pulse);
      });
      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);

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
    const hotspots = [];
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
        emissive: cell.id === selectedCell ? 0xb05a24 : 0x000000,
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
        new THREE.LineBasicMaterial({ color: cell.id === selectedCell ? 0xe4eee6 : 0x719180 }),
      );
      border.position.copy(tile.position);
      model.add(border);

      if (showObserved && cell.observed) {
        const observedTop = new THREE.Mesh(
          new THREE.PlaneGeometry(1.48, 1.48),
          new THREE.MeshBasicMaterial({ color: 0xffdac1, transparent: true, opacity: 0.36, side: THREE.DoubleSide }),
        );
        observedTop.rotation.x = -Math.PI / 2;
        observedTop.position.set(x, elevation + 0.025, z);
        model.add(observedTop);
        const observedBox = new THREE.BoxGeometry(1.55, 0.06, 1.55);
        const observedEdges = new THREE.EdgesGeometry(observedBox);
        observedBox.dispose();
        const ring = new THREE.LineSegments(
          observedEdges,
          new THREE.LineBasicMaterial({ color: 0xff8a42 }),
        );
        ring.position.set(x, elevation + 0.04, z);
        model.add(ring);
      }

      if (showHotspots && cell.hotspot) {
        const hotspot = new THREE.Mesh(
          new THREE.SphereGeometry(0.18, 16, 12),
          new THREE.MeshBasicMaterial({ color: 0xffcf5a }),
        );
        hotspot.position.set(x, elevation + 0.42, z);
        model.add(hotspot);
        hotspots.push(hotspot);
      }

      if (cell.risk >= 0.08) {
        const count = cell.risk >= 0.6 ? 3 : cell.risk >= 0.3 ? 2 : 1;
        for (let index = 0; index < count; index += 1) {
          const height = (0.45 + cell.risk * 1.2) * (index === 0 ? 1 : 0.72);
          const flame = new THREE.Mesh(
            new THREE.ConeGeometry(0.12 + cell.risk * 0.14, height, 5),
            new THREE.MeshBasicMaterial({
              color: index === 0 ? 0xd7a84b : 0xb05a24,
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

    resources.forEach((resource, index) => {
      const cell = cells.find((item) => item.id === resource.cell_id);
      if (!cell) return;
      const x = (cell.col - centerCol) * 1.85 + 0.48;
      const z = (cell.row - centerRow) * 1.85 - 0.48;
      const elevation = 0.25 + Math.max(0, Math.min(1, cell.slope || 0)) * 0.9;
      const geometry = resource.kind === "drone"
        ? new THREE.OctahedronGeometry(0.24, 0)
        : new THREE.BoxGeometry(0.42, 0.26, 0.28);
      const marker = new THREE.Mesh(
        geometry,
        new THREE.MeshStandardMaterial({ color: resource.kind === "drone" ? 0xe4eee6 : 0x6fbf91, emissive: 0x183c2a, emissiveIntensity: 0.35 }),
      );
      marker.position.set(x, elevation + (resource.kind === "drone" ? 1.1 : 0.24), z);
      marker.userData.resourceId = resource.resource_id;
      marker.rotation.y = index * 0.7;
      model.add(marker);
    });
    state.model = model;
    state.tiles = tiles;
    state.flames = flames;
    state.hotspots = hotspots;
    state.scene.add(model);
  }, [cells, selectedCell, showObserved, showHotspots, resources]);

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
      {(showObserved || showHotspots || resources.length > 0) && <div className="sceneStatus">{showObserved ? "Observed edge" : ""}{showObserved && (showHotspots || resources.length) ? " · " : ""}{showHotspots ? "Thermal hotspots" : ""}{showHotspots && resources.length ? " · " : ""}{resources.length ? `${resources.length} resources` : ""}</div>}
    </div>
  );
}
