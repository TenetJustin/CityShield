import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

function geometryLines(geometry) {
  if (!geometry) return [];
  if (geometry.type === "LineString") return [geometry.coordinates];
  if (geometry.type === "MultiLineString" || geometry.type === "Polygon") return geometry.coordinates;
  if (geometry.type === "MultiPolygon") return geometry.coordinates.flat();
  return [];
}

export default function ParadiseTerrain3D({ geography, terrain, live }) {
  const mount = useRef(null);
  const [supported, setSupported] = useState(true);

  useEffect(() => {
    const target = mount.current;
    if (!target || !geography || !terrain) return undefined;
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true }); }
    catch { setSupported(false); return undefined; }

    const [west, south, east, north] = terrain.bbox;
    const cosine = Math.cos((south + north) * Math.PI / 360);
    const spanX = (east - west) * cosine;
    const spanZ = north - south;
    const scale = 11 / Math.max(spanX, spanZ);
    const size = terrain.grid_size;
    const elevations = terrain.samples.map((point) => point.elevation_m);
    const minElevation = Math.min(...elevations);
    const relief = (elevation) => (elevation - minElevation) * 0.01;
    const xy = ([lon, lat]) => [((lon - west) * cosine - spanX / 2) * scale, ((north - lat) - spanZ / 2) * scale];
    const altitude = ([lon, lat]) => {
      const row = Math.max(0, Math.min(size - 1.000001, (north - lat) / (north - south) * (size - 1)));
      const col = Math.max(0, Math.min(size - 1.000001, (lon - west) / (east - west) * (size - 1)));
      const r = Math.floor(row), c = Math.floor(col), fr = row - r, fc = col - c;
      const at = (rr, cc) => elevations[rr * size + cc];
      return relief(at(r, c) * (1 - fr) * (1 - fc) + at(r + 1, c) * fr * (1 - fc)
        + at(r, c + 1) * (1 - fr) * fc + at(r + 1, c + 1) * fr * fc);
    };

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a1e19);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 80);
    camera.position.set(10, 12, 12);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.8, 0);
    controls.enableDamping = true;
    controls.minDistance = 7;
    controls.maxDistance = 35;
    controls.maxPolarAngle = Math.PI / 2.05;
    controls.update();
    scene.add(new THREE.AmbientLight(0xcce1c9, 1.8));
    const sun = new THREE.DirectionalLight(0xffe3ab, 2.4);
    sun.position.set(-4, 12, 5);
    scene.add(sun);
    const group = new THREE.Group();
    scene.add(group);

    const vertices = [];
    const colors = [];
    const indices = [];
    for (const sample of terrain.samples) {
      const [x, z] = xy([sample.longitude, sample.latitude]);
      vertices.push(x, relief(sample.elevation_m), z);
      const t = (sample.elevation_m - minElevation) / (Math.max(...elevations) - minElevation || 1);
      const color = new THREE.Color().lerpColors(new THREE.Color(0x244e3d), new THREE.Color(0x739478), t);
      colors.push(color.r, color.g, color.b);
    }
    for (let row = 0; row < size - 1; row++) for (let col = 0; col < size - 1; col++) {
      const a = row * size + col, b = a + 1, c = a + size, d = c + 1;
      indices.push(a, c, b, b, c, d);
    }
    const meshGeometry = new THREE.BufferGeometry();
    meshGeometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    meshGeometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    meshGeometry.setIndex(indices);
    meshGeometry.computeVertexNormals();
    const mesh = new THREE.Mesh(meshGeometry, new THREE.MeshStandardMaterial({ vertexColors: true, side: THREE.DoubleSide, roughness: 1 }));
    group.add(mesh);

    function addLines(features, color, opacity, lift) {
      const positions = [];
      for (const feature of features) for (const line of geometryLines(feature.geometry)) {
        for (let index = 1; index < line.length; index++) {
          for (const point of [line[index - 1], line[index]]) {
            const [x, z] = xy(point);
            positions.push(x, altitude(point) + lift, z);
          }
        }
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      group.add(new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity })));
    }
    addLines(geography.features.slice(1), 0xd3c89a, 0.8, 0.04);
    addLines(geography.features.slice(0, 1), 0xbdf0aa, 1, 0.09);

    for (const incident of live?.incidents || []) if (incident.geometry?.type === "Point") {
      const point = incident.geometry.coordinates;
      const [x, z] = xy(point);
      const marker = new THREE.Mesh(new THREE.SphereGeometry(0.12, 10, 8), new THREE.MeshBasicMaterial({ color: 0xff7447 }));
      marker.position.set(x, altitude(point) + 0.18, z);
      group.add(marker);
    }
    for (const detection of live?.satellite_detections || []) {
      const point = [detection.longitude, detection.latitude];
      const [x, z] = xy(point);
      const marker = new THREE.Mesh(new THREE.SphereGeometry(0.08, 8, 6), new THREE.MeshBasicMaterial({ color: 0xffd05a }));
      marker.position.set(x, altitude(point) + 0.12, z);
      group.add(marker);
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    target.appendChild(renderer.domElement);
    const resize = () => {
      camera.aspect = Math.max(target.clientWidth, 1) / Math.max(target.clientHeight, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(Math.max(target.clientWidth, 1), Math.max(target.clientHeight, 1));
    };
    const observer = new ResizeObserver(resize);
    observer.observe(target);
    resize();
    let frame;
    const animate = () => { controls.update(); renderer.render(scene, camera); frame = requestAnimationFrame(animate); };
    animate();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      group.traverse((object) => { object.geometry?.dispose(); object.material?.dispose(); });
      renderer.dispose();
      target.removeChild(renderer.domElement);
    };
  }, [geography, terrain, live]);

  return <div className="paradiseTerrain" ref={mount} role="img" aria-label="Three-dimensional Paradise terrain and roads from USGS and Census data">{!supported && <span>3D graphics are unavailable on this device.</span>}</div>;
}
