import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { riskColor } from "./riskVisual.js";

function geometryLines(geometry) {
  if (!geometry) return [];
  if (geometry.type === "LineString") return [geometry.coordinates];
  if (geometry.type === "MultiLineString") return geometry.coordinates;
  if (geometry.type === "Polygon") return geometry.coordinates;
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat();
  return [];
}

function disposeGroup(group) {
  if (!group) return;
  group.traverse((child) => {
    child.geometry?.dispose();
    if (Array.isArray(child.material)) child.material.forEach((material) => material.dispose());
    else child.material?.dispose();
  });
}

export default function ParadiseGridScene3D({
  grid,
  geography,
  frame,
  forecast,
  selectedCell,
  onSelect,
  layers,
  onUnavailable,
  resetSignal,
}) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const dataRef = useRef({ grid, geography, frame, forecast, selectedCell, layers });
  const [failed, setFailed] = useState(false);
  const onSelectRef = useRef(onSelect);

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  useEffect(() => { dataRef.current = { grid, geography, frame, forecast, selectedCell, layers }; });

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    } catch {
      setFailed(true);
      onUnavailable?.();
      return undefined;
    }
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a1d17);
    scene.fog = new THREE.Fog(0x0a1d17, 16, 34);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 120);
    camera.position.set(12, 14, 14);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.2, 0);
    controls.enableDamping = true;
    controls.minDistance = 6;
    controls.maxDistance = 34;
    controls.maxPolarAngle = Math.PI / 2.08;
    controls.update();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);
    scene.add(new THREE.AmbientLight(0xdcebdc, 1.75));
    const sun = new THREE.DirectionalLight(0xffe0ac, 2.4);
    sun.position.set(-8, 14, 9);
    scene.add(sun);
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(40, 40),
      new THREE.MeshStandardMaterial({ color: 0x0d241c, roughness: 1 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.08;
    scene.add(ground);

    const state = { scene, camera, controls, renderer, group: null, tiles: null };
    sceneRef.current = state;
    let pointerDown = null;
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const handlePointerDown = (event) => { pointerDown = [event.clientX, event.clientY]; };
    const handlePointerUp = (event) => {
      if (!pointerDown || Math.hypot(event.clientX - pointerDown[0], event.clientY - pointerDown[1]) > 5) return;
      if (!state.tiles) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObject(state.tiles.mesh, false)[0];
      if (hit && hit.instanceId != null) {
        const cellId = state.tiles.cellIds[hit.instanceId];
        if (cellId) onSelectRef.current(cellId);
      }
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
    let frameId;
    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    };
    frameId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(frameId);
      observer.disconnect();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      controls.dispose();
      if (state.group) {
        scene.remove(state.group);
        disposeGroup(state.group);
      }
      ground.geometry.dispose();
      ground.material.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === mount) mount.removeChild(renderer.domElement);
      sceneRef.current = null;
    };
  }, [onUnavailable]);

  useEffect(() => {
    const state = sceneRef.current;
    if (!state || !grid) return;
    if (state.group) {
      state.scene.remove(state.group);
      disposeGroup(state.group);
    }
    const group = new THREE.Group();
    state.scene.add(group);
    const elevations = grid.cells.map((cell) => cell.elevation_m);
    const minElevation = Math.min(...elevations);
    const maxElevation = Math.max(...elevations);
    const centerX = (grid.extent.x_min_m + grid.extent.x_max_m) / 2;
    const centerY = (grid.extent.y_min_m + grid.extent.y_max_m) / 2;
    const observed = new Set(frame?.cumulative_detected_cells || []);
    const predicted = new Map((forecast?.cells || []).map((cell) => [cell.cell_id, cell]));
    const threshold = forecast?.threshold ?? 0.5;
    const cellHeight = (cell) => {
      const base = 0.05 + ((cell.elevation_m - minElevation) / (maxElevation - minElevation || 1)) * 0.62;
      const isObserved = observed.has(cell.id);
      const prediction = predicted.get(cell.id);
      const risk = !isObserved && prediction && prediction.probability >= threshold ? prediction.probability : 0;
      const observedLift = isObserved ? 0.07 : 0;
      return base + risk * 2.1 + observedLift;
    };
    const cellColor = (cell) => {
      if (observed.has(cell.id)) return new THREE.Color(0xb05a24);
      const prediction = predicted.get(cell.id);
      if (prediction && prediction.probability >= threshold) return new THREE.Color(riskColor(prediction.probability));
      if (prediction) return new THREE.Color(0x356b55);
      return new THREE.Color(cell.in_town ? 0x2b5c45 : 0x1b3c2e);
    };
    const positions = grid.cells.map((cell) => ({
      x: (cell.x_m - centerX) / 1000,
      z: (centerY - cell.y_m) / 1000,
    }));
    const tileGeometry = new THREE.BoxGeometry(0.46, 1, 0.46);
    const tileMaterial = new THREE.MeshStandardMaterial({ roughness: 0.82, metalness: 0.03 });
    const tiles = new THREE.InstancedMesh(tileGeometry, tileMaterial, grid.cells.length);
    tiles.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    const matrix = new THREE.Matrix4();
    grid.cells.forEach((cell, index) => {
      const height = cellHeight(cell);
      const prediction = predicted.get(cell.id);
      const isRisk = !observed.has(cell.id) && prediction && prediction.probability >= threshold;
      const footprint = isRisk ? 0.28 : 0.46;
      matrix.compose(
        new THREE.Vector3(positions[index].x, height / 2, positions[index].z),
        new THREE.Quaternion(),
        new THREE.Vector3(footprint, height, footprint),
      );
      tiles.setMatrixAt(index, matrix);
      tiles.setColorAt(index, cellColor(cell));
    });
    tiles.instanceMatrix.needsUpdate = true;
    if (tiles.instanceColor) tiles.instanceColor.needsUpdate = true;
    tiles.userData.cellIds = grid.cells.map((cell) => cell.id);
    group.add(tiles);
    state.tiles = { mesh: tiles, cellIds: tiles.userData.cellIds };

    const selected = grid.cells.find((cell) => cell.id === selectedCell);
    if (selected) {
      const height = cellHeight(selected);
      const position = positions[grid.cells.indexOf(selected)];
      const highlightBox = new THREE.BoxGeometry(0.5, height + 0.05, 0.5);
      const highlightEdges = new THREE.EdgesGeometry(highlightBox);
      highlightBox.dispose();
      const highlight = new THREE.LineSegments(
        highlightEdges,
        new THREE.LineBasicMaterial({ color: 0xf5ffdf }),
      );
      highlight.position.set(position.x, height / 2, position.z);
      group.add(highlight);
    }

    if (layers.roads && geography) {
      const altitudeAt = (longitude, latitude) => {
        const x = (longitude - grid.crs.origin.longitude) * grid.crs.meters_per_degree_longitude;
        const y = (latitude - grid.crs.origin.latitude) * grid.crs.meters_per_degree_latitude;
        const col = Math.floor((x - grid.extent.x_min_m) / grid.resolution_m);
        const row = Math.floor((y - grid.extent.y_min_m) / grid.resolution_m);
        if (row < 0 || col < 0 || row >= grid.extent.rows || col >= grid.extent.cols) return 0.2;
        const cell = grid.cells[row * grid.extent.cols + col];
        return 0.05 + ((cell.elevation_m - minElevation) / (maxElevation - minElevation || 1)) * 0.62 + 0.03;
      };
      const positionsRoad = [];
      for (const feature of geography.features.slice(1)) {
        for (const line of geometryLines(feature.geometry)) {
          for (let index = 1; index < line.length; index += 1) {
            for (const point of [line[index - 1], line[index]]) {
              positionsRoad.push(
                (point[0] - grid.crs.origin.longitude) * grid.crs.meters_per_degree_longitude / 1000 - centerX / 1000,
                altitudeAt(point[0], point[1]),
                (centerY - (point[1] - grid.crs.origin.latitude) * grid.crs.meters_per_degree_latitude) / 1000,
              );
            }
          }
        }
      }
      if (positionsRoad.length) {
        const roadGeometry = new THREE.BufferGeometry();
        roadGeometry.setAttribute("position", new THREE.Float32BufferAttribute(positionsRoad, 3));
        group.add(new THREE.LineSegments(
          roadGeometry,
          new THREE.LineBasicMaterial({ color: 0xd7c58f, transparent: true, opacity: 0.46 }),
        ));
      }
      const boundaryPoints = [];
      for (const line of geometryLines(grid.town.boundary)) {
        for (let index = 1; index < line.length; index += 1) {
          for (const point of [line[index - 1], line[index]]) {
            boundaryPoints.push(
              (point[0] - grid.crs.origin.longitude) * grid.crs.meters_per_degree_longitude / 1000 - centerX / 1000,
              altitudeAt(point[0], point[1]) + 0.02,
              (centerY - (point[1] - grid.crs.origin.latitude) * grid.crs.meters_per_degree_latitude) / 1000,
            );
          }
        }
      }
      if (boundaryPoints.length) {
        const boundaryGeometry = new THREE.BufferGeometry();
        boundaryGeometry.setAttribute("position", new THREE.Float32BufferAttribute(boundaryPoints, 3));
        group.add(new THREE.LineSegments(
          boundaryGeometry,
          new THREE.LineBasicMaterial({ color: 0xbde5a8, transparent: true, opacity: 0.95 }),
        ));
      }
    }

    if (layers.hotspots && frame?.new_detections) {
      const points = frame.new_detections.filter((item) => item.cell_id);
      if (points.length) {
        const hotspotGeometry = new THREE.SphereGeometry(0.1, 10, 8);
        const hotspotMaterial = new THREE.MeshBasicMaterial({ color: 0xffd05a });
        const spots = new THREE.InstancedMesh(hotspotGeometry, hotspotMaterial, points.length);
        points.forEach((point, index) => {
          const x = (point.longitude - grid.crs.origin.longitude) * grid.crs.meters_per_degree_longitude / 1000 - centerX / 1000;
          const z = (centerY - (point.latitude - grid.crs.origin.latitude) * grid.crs.meters_per_degree_latitude) / 1000;
          const cell = grid.cells.find((item) => item.id === point.cell_id);
          const height = cell ? cellHeight(cell) : 0.6;
          matrix.compose(
            new THREE.Vector3(x, height + 0.22, z),
            new THREE.Quaternion(),
            new THREE.Vector3(1, 1, 1),
          );
          spots.setMatrixAt(index, matrix);
          spots.setColorAt(index, new THREE.Color(0xffd05a));
        });
        spots.instanceMatrix.needsUpdate = true;
        if (spots.instanceColor) spots.instanceColor.needsUpdate = true;
        group.add(spots);
      }
    }

    state.group = group;
    state.camera.far = 120;
    state.camera.updateProjectionMatrix();
  }, [grid, geography, frame, forecast, selectedCell, layers]);

  useEffect(() => {
    if (!sceneRef.current) return;
    const { camera, controls } = sceneRef.current;
    camera.position.set(12, 14, 14);
    controls.target.set(0, 1.2, 0);
    controls.update();
  }, [resetSignal]);

  return <div className="prScene">
    <div className="prSceneCanvas" ref={mountRef} role="img" aria-label="Three-dimensional terrain, roads and predicted wildfire risk on the shared Paradise grid" />
    {failed && <div className="prSceneFallback">WebGL is unavailable. The 2D map remains available.</div>}
    {!grid && <div className="prSceneFallback">Loading the shared Paradise grid…</div>}
    <div className="prSceneHint">Drag to rotate · Scroll to zoom · Click a cell</div>
    <div className="prSceneLegend">Flat base = coarse elevation · orange tiles = observed cells · columns = predicted new risk</div>
  </div>;
}
