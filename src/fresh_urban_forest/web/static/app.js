import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const state = {
  dataset: null,
  scene: null,
  treeById: new Map(),
  scenarios: [],
  scenarioId: "",
  edits: [],
  sentEditCount: 0,
  revision: 0,
  years: 25,
  mode: null,
  selectedId: "",
  recommendations: [],
  map: null,
  selectedSourceReady: false,
  three: null,
  result: null,
  assistant: { enabled: false, available: false, busy: false, session: null },
  changeMap: null,
  changeData: null,
  changeProduct: "change.json",
  changeProductsLoaded: false,
  lightMap: null,
  lightData: null,
  lightDate: "2026-06-21",
  lightTime: 12,
  lightMode: "instant",
  lightTimer: null,
  lightDebounce: null,
  lightRequest: 0,
  lastSolar: null,
  optimize: {
    jobId: null,
    result: null,
    selected: null,
    chart: null,
    mesh: null,
    pollTimer: null,
    filtered: [],
  },
  previewYear: 0,
  playTimer: null,
};

const $ = (id) => document.getElementById(id);

function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const relative = String(path).replace(/^\/+/, "");
  return fetch(relative, { ...options, headers }).then(async (response) => {
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (_error) {
        // keep the status text
      }
      throw new Error(detail);
    }
    return response.json();
  });
}

function toast(message, isError = false) {
  const element = $("toast");
  element.textContent = message;
  element.classList.toggle("error", isError);
  element.classList.add("show");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => element.classList.remove("show"), 3200);
}

function formatNumber(value, digits = 0) {
  return Number(value || 0).toLocaleString("en-CA", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatCompact(value, unit = "") {
  const number = Number(value || 0);
  if (Math.abs(number) >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M${unit}`;
  if (Math.abs(number) >= 1_000) return `${(number / 1_000).toFixed(1)}k${unit}`;
  return `${number.toFixed(0)}${unit}`;
}

function setStatus(text, error = false) {
  const pill = $("status-pill");
  pill.textContent = text;
  pill.classList.toggle("error", error);
}

function treeFeature(tree) {
  return {
    type: "Feature",
    geometry: { type: "Point", coordinates: [tree.lon, tree.lat] },
    properties: {
      tree_id: tree.id,
      species: tree.species,
      common_name: tree.common_name,
      height_m: tree.height,
      crown_width_m: tree.crown_width,
      dbh_cm: tree.dbh_cm,
      group: tree.group,
      native: tree.native,
      color: tree.color,
      status: tree.status,
    },
  };
}

function treesToFeatureCollection(trees) {
  return { type: "FeatureCollection", features: trees.map(treeFeature) };
}

function buildingFeatures() {
  return {
    type: "FeatureCollection",
    features: (state.scene.buildings || []).map((building) => ({
      type: "Feature",
      properties: { name: building.name, height_m: building.height_m },
      geometry: { type: "Polygon", coordinates: building.rings },
    })),
  };
}

function boundaryFeatures() {
  const boundary = state.scene.boundary || [];
  return {
    type: "FeatureCollection",
    features: boundary.length
      ? [
          {
            type: "Feature",
            properties: { name: "analysis boundary" },
            geometry: { type: "Polygon", coordinates: [boundary] },
          },
        ]
      : [],
  };
}

function selectedFeatures() {
  if (!state.selectedId) return { type: "FeatureCollection", features: [] };
  const tree = state.treeById.get(state.selectedId);
  return tree ? treesToFeatureCollection([tree]) : { type: "FeatureCollection", features: [] };
}

async function init() {
  try {
    const [dataset, scene, scenarios] = await Promise.all([
      api("/api/dataset"),
      api("/api/scene"),
      api("/api/scenarios"),
    ]);
    state.dataset = dataset;
    state.scene = scene;
    state.scenarios = scenarios.scenarios || [];
    state.treeById = new Map(scene.trees.map((tree) => [tree.id, tree]));
    $("dataset-name").textContent = `${dataset.name} · ${dataset.tree_count.toLocaleString("en-CA")} tree records · ${dataset.sources.length} sources`;
    setStatus("live");
    renderKPIs(dataset.metrics);
    await loadCompleteness();
    renderComposition(dataset.metrics);
    renderSize(dataset.metrics);
    renderScenarioOptions();
    renderBaselineTimeline(dataset.metrics);
    initMap();
    bindControls();
    initLightControls();
    initOptimizeControls();
    updateSunForTime();
    updateHud();
    window.__freshLab = {
      selectTree,
      switchView,
      loadLight,
      selectPareto: (index) => {
        const solution = state.optimize.result?.archive?.solutions?.[index];
        if (solution) renderParetoInfo(solution);
      },
      paretoScreenPositions,
    };
    await loadAssistantInfo();
  } catch (error) {
    console.error(error);
    setStatus("offline", true);
    toast(`Could not load the dataset: ${error.message}`, true);
  }
}

function renderKPIs(metrics) {
  if (!metrics) return;
  $("kpi-cover").textContent = `${formatNumber(metrics.canopy_cover_pct, 1)}%`;
  $("kpi-trees").textContent = formatNumber(metrics.tree_count);
  $("kpi-volume").textContent = formatCompact(metrics.canopy_volume_m3, " m³");
  $("kpi-carbon").textContent = formatCompact(metrics.total_carbon_kg / 1000, " t");
  $("kpi-species").textContent = formatNumber(metrics.species_count);
  $("kpi-native").textContent = `${formatNumber(metrics.native_fraction * 100, 0)}%`;
}

async function loadCompleteness() {
  try {
    const data = await api("api/completeness");
    const rows = Object.entries(data.fields || {})
      .map(([, field]) => {
        const fraction = Number(field.fraction || 0);
        return `<div class="completeness-row">
          <span>${escapeHtml(field.label)}</span>
          <div class="completeness-track"><div class="completeness-fill" style="width:${(fraction * 100).toFixed(0)}%"></div></div>
          <code>${(fraction * 100).toFixed(0)}%</code>
        </div>`;
      })
      .join("");
    $("completeness").innerHTML =
      `<div class="completeness-head"><span>Inventory completeness</span><span>${formatNumber(data.total)} live</span></div>${rows}`;
  } catch (error) {
    $("completeness").innerHTML = '<p class="hint">Completeness unavailable.</p>';
  }
}

function measuredTag(measured) {
  return measured
    ? '<span class="measure-tag">measured</span>'
    : '<span class="measure-tag imputed">imputed</span>';
}

function renderComposition(metrics) {
  const container = $("composition-chart");
  const rows = (metrics.species_composition || []).slice(0, 12);
  const max = Math.max(...rows.map((row) => row[1]), 1);
  container.innerHTML = rows
    .map(
      ([name, count]) => `
        <div class="bar-row">
          <span title="${escapeHtml(name)}">${escapeHtml(name || "Unknown")}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(count / max) * 100}%"></div></div>
          <code>${formatNumber(count)}</code>
        </div>`
    )
    .join("");
}

function renderSize(metrics) {
  const container = $("size-chart");
  const rows = metrics.size_classes || [];
  const max = Math.max(...rows.map((row) => row[1]), 1);
  container.innerHTML = rows
    .map(
      ([label, count]) => `
        <div class="bar-row">
          <span>${escapeHtml(label)} cm</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(count / max) * 100}%"></div></div>
          <code>${formatNumber(count)}</code>
        </div>`
    )
    .join("");
}

function renderBaselineTimeline(metrics) {
  renderTimeline([{ year: 0, ...metrics }]);
  $("scenario-verdict").textContent = "Baseline dataset";
  $("delta-strip").innerHTML = `
    <span class="delta"><b>${formatNumber(metrics.canopy_cover_pct, 1)}%</b> cover</span>
    <span class="delta"><b>${formatCompact(metrics.canopy_volume_m3)}</b> m³</span>
    <span class="delta"><b>${formatCompact(metrics.total_carbon_kg / 1000)}</b> t carbon</span>
    <span class="delta"><b>${formatNumber(metrics.native_fraction * 100, 0)}%</b> native</span>`;
}

function renderTimeline(timeline) {
  const svg = $("timeline-chart");
  const width = 640;
  const height = 220;
  const padding = { left: 38, right: 14, top: 18, bottom: 28 };
  const values = timeline.map((item) => Number(item.canopy_cover_pct || 0));
  const years = timeline.map((item) => Number(item.year || 0));
  const maxValue = Math.max(30, ...values) * 1.08;
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const x = (year) => padding.left + (year / Math.max(years[years.length - 1] || 1, 1)) * plotWidth;
  const y = (value) => padding.top + plotHeight - (value / maxValue) * plotHeight;
  const points = timeline
    .map((item, index) => `${index === 0 ? "M" : "L"}${x(years[index]).toFixed(1)},${y(values[index]).toFixed(1)}`)
    .join(" ");
  const area = `${points} L${x(years[years.length - 1] || 0).toFixed(1)},${(padding.top + plotHeight).toFixed(1)} L${x(0).toFixed(1)},${(padding.top + plotHeight).toFixed(1)} Z`;
  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((fraction) => {
      const value = maxValue * fraction;
      const yPos = y(value);
      return `<line x1="${padding.left}" y1="${yPos}" x2="${width - padding.right}" y2="${yPos}" stroke="#e6ebe1" stroke-width="1"/>
        <text x="${padding.left - 7}" y="${yPos + 4}" text-anchor="end" font-size="10" fill="#6b7a70">${value.toFixed(0)}%</text>`;
    })
    .join("");
  const labels = years
    .filter((year, index) => index === 0 || index === years.length - 1 || index % Math.max(1, Math.floor(years.length / 4)) === 0)
    .map((year, index) => {
      const position = x(year);
      return `<text x="${position}" y="${height - 8}" text-anchor="${index === 0 ? "start" : "middle"}" font-size="10" fill="#6b7a70">${year}</text>`;
    })
    .join("");
  svg.innerHTML = `
    <defs>
      <linearGradient id="canopy-fill" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#68a357" stop-opacity="0.45"/>
        <stop offset="100%" stop-color="#68a357" stop-opacity="0.02"/>
      </linearGradient>
    </defs>
    ${grid}
    <path d="${area}" fill="url(#canopy-fill)"></path>
    <path d="${points}" fill="none" stroke="#2f6b4f" stroke-width="2.5" stroke-linejoin="round"></path>
    ${labels}`;
}

function initMap() {
  const [west, south, east, north] = state.scene.bounds_wgs84;
  const coordinates = state.scene.corners_wgs84 || [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
  const map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        hillshade: { type: "image", url: "api/hillshade.png?width=1400", coordinates },
        canopy: { type: "image", url: "api/canopy.png?width=1400", coordinates },
        buildings: { type: "geojson", data: buildingFeatures() },
        boundary: { type: "geojson", data: boundaryFeatures() },
        trees: { type: "geojson", data: treesToFeatureCollection(state.scene.trees) },
        selected: { type: "geojson", data: selectedFeatures() },
      },
      layers: [
        { id: "background", type: "background", paint: { "background-color": "#e6eae2" } },
        {
          id: "hillshade",
          type: "raster",
          source: "hillshade",
          paint: { "raster-opacity": 0.55, "raster-resampling": "linear" },
        },
        {
          id: "canopy",
          type: "raster",
          source: "canopy",
          paint: { "raster-opacity": 0.72, "raster-resampling": "linear" },
        },
        {
          id: "buildings",
          type: "fill",
          source: "buildings",
          paint: { "fill-color": "#b6beb3", "fill-opacity": 0.9 },
        },
        {
          id: "buildings-outline",
          type: "line",
          source: "buildings",
          paint: { "line-color": "#7d887c", "line-width": 0.7 },
        },
        {
          id: "boundary",
          type: "line",
          source: "boundary",
          paint: { "line-color": "#2f6b4f", "line-width": 1.4, "line-dasharray": [2, 2] },
        },
        {
          id: "trees",
          type: "circle",
          source: "trees",
          paint: {
            "circle-color": ["get", "color"],
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 13, 1.6, 16, 3.2, 19, 6],
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 0.45,
            "circle-opacity": 0.9,
          },
        },
        {
          id: "selected-tree",
          type: "circle",
          source: "selected",
          paint: {
            "circle-color": "#ffffff",
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 13, 5, 16, 9, 19, 16],
            "circle-stroke-color": "#17231d",
            "circle-stroke-width": 2,
          },
        },
      ],
    },
    center: [(west + east) / 2, (south + north) / 2],
    zoom: 14,
    attributionControl: false,
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  map.on("load", () => {
    map.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding: 28, duration: 0 }
    );
  });
  map.on("click", "trees", (event) => {
    const feature = event.features && event.features[0];
    if (!feature) return;
    selectTree(feature.properties.tree_id);
  });
  map.on("click", (event) => {
    if (state.mode === "zone") {
      placeAt(event.lngLat.lng, event.lngLat.lat);
      return;
    }
    const hits = map.queryRenderedFeatures(event.point, { layers: ["trees"] });
    if (hits.length) return;
    if (state.mode === "plant" || state.mode === "move") {
      placeAt(event.lngLat.lng, event.lngLat.lat);
    }
  });
  map.on("mousemove", "trees", () => {
    map.getCanvas().style.cursor = "pointer";
  });
  map.on("mouseleave", "trees", () => {
    map.getCanvas().style.cursor = "";
  });
  state.map = map;
  state.selectedSourceReady = true;
}

function ensureThree() {
  if (state.three) {
    state.three.renderer.setSize(state.three.container.clientWidth, state.three.container.clientHeight, false);
    return state.three;
  }
  const container = $("view-scene");
  const canvas = $("scene-canvas");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(container.clientWidth, container.clientHeight, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#dfe7dc");
  scene.fog = new THREE.Fog("#dfe7dc", 900, 2400);

  const camera = new THREE.PerspectiveCamera(46, container.clientWidth / Math.max(container.clientHeight, 1), 0.5, 9000);
  camera.position.set(240, 170, 280);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 14, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = Math.PI / 2.04;
  controls.minDistance = 30;
  controls.maxDistance = 2400;

  const ambient = new THREE.HemisphereLight(0xf7fbf4, 0x495243, 1.3);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(0xfff4dc, 1.8);
  sun.position.set(-320, 520, 240);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.left = -420;
  sun.shadow.camera.right = 420;
  sun.shadow.camera.top = 420;
  sun.shadow.camera.bottom = -420;
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = 2400;
  scene.add(sun);
  scene.add(sun.target);
  const sunSphere = new THREE.Mesh(
    new THREE.SphereGeometry(9, 18, 12),
    new THREE.MeshBasicMaterial({ color: 0xffe6a0 })
  );
  sunSphere.position.set(-520, 620, 320);
  scene.add(sunSphere);

  const terrain = buildTerrainMesh();
  scene.add(terrain);
  const buildings = buildBuildingMeshes();
  buildings.forEach((mesh) => scene.add(mesh));

  const three = {
    renderer,
    scene,
    camera,
    controls,
    container,
    terrain,
    buildingMeshes: buildings,
    crownMeshes: [],
    trunkMeshes: [],
    treeGroups: new Map(),
    selectedMarker: null,
    sunLight: sun,
    sunSphere,
  };
  state.three = three;
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  renderer.domElement.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    if (state.mode === "zone") {
      const terrainHits = raycaster.intersectObject(terrain, false);
      if (!terrainHits.length) return;
      const local = terrainHits[0].point;
      const origin = state.scene.origin_lonlat;
      const metres = state.scene.meters_per_degree;
      placeAt(origin[0] + local.x / metres[0], origin[1] + local.z / metres[1]);
      return;
    }
    const targets = [...three.crownMeshes, ...three.trunkMeshes, terrain];
    const hits = raycaster.intersectObjects(targets, false);
    if (!hits.length) return;
    const hit = hits[0];
    if (hit.object.userData.kind === "crown" || hit.object.userData.kind === "trunk") {
      const tree = hit.object.userData.trees[hit.instanceId];
      if (tree) {
        selectTree(tree.id);
        return;
      }
    }
    if (state.mode === "plant" || state.mode === "move") {
      const local = hit.point;
      const origin = state.scene.origin_lonlat;
      const metres = state.scene.meters_per_degree;
      const lon = origin[0] + local.x / metres[0];
      const lat = origin[1] + local.z / metres[1];
      placeAt(lon, lat);
    }
  });
  renderer.domElement.addEventListener("pointerdown", () => {
    renderer.domElement.style.cursor = "default";
  });
  window.addEventListener("resize", () => {
    if (!state.three) return;
    const width = state.three.container.clientWidth;
    const height = Math.max(state.three.container.clientHeight, 1);
    state.three.renderer.setSize(width, height, false);
    state.three.camera.aspect = width / height;
    state.three.camera.updateProjectionMatrix();
  });
  rebuildThreeTrees(state.scene.trees);
  applySun();
  animateThree();
  return three;
}

function buildTerrainMesh() {
  const sceneData = state.scene;
  const { width, height, elevation, canopy_height: canopy } = sceneData.terrain;
  const [left, bottom, right, top] = sceneData.bounds;
  const spanX = right - left;
  const spanZ = top - bottom;
  const originZ = sceneData.origin.z;
  const positions = [];
  const colors = [];
  const indices = [];
  const color = new THREE.Color();
  for (let row = 0; row < height; row += 1) {
    for (let col = 0; col < width; col += 1) {
      const index = row * width + col;
      const x = -spanX / 2 + (col / Math.max(width - 1, 1)) * spanX;
      const z = spanZ / 2 - (row / Math.max(height - 1, 1)) * spanZ;
      const y = elevation[index] - originZ;
      positions.push(x, y, z);
      const canopyValue = canopy ? canopy[index] : 0;
      if (canopyValue > 2) {
        const t = Math.min(canopyValue / 38, 1);
        color.setHSL(0.29 - t * 0.05, 0.34 + t * 0.12, 0.38 - t * 0.1);
      } else {
        color.setHSL(0.24, 0.12, 0.64 + Math.min(Math.max(y / 120, 0), 0.18));
      }
      colors.push(color.r, color.g, color.b);
    }
  }
  for (let row = 0; row < height - 1; row += 1) {
    for (let col = 0; col < width - 1; col += 1) {
      const a = row * width + col;
      const b = a + 1;
      const c = a + width;
      const d = c + 1;
      indices.push(a, c, b, b, c, d);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const material = new THREE.MeshStandardMaterial({
    vertexColors: true,
    roughness: 0.96,
    metalness: 0.0,
    side: THREE.DoubleSide,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.userData.kind = "terrain";
  mesh.receiveShadow = true;
  mesh.name = "terrain";
  return mesh;
}

function buildBuildingMeshes() {
  const meshes = [];
  for (const building of state.scene.buildings || []) {
    const ring = (building.rings_local || [])[0] || [];
    if (ring.length < 3) continue;
    const height = Math.max(Number(building.height_m) || 10, 2);
    const shape = new THREE.Shape();
    ring.forEach((point, index) => {
      const x = Number(point[0]);
      const y = -Number(point[1]);
      if (index === 0) shape.moveTo(x, y);
      else shape.lineTo(x, y);
    });
    shape.closePath();
    let geometry;
    try {
      geometry = new THREE.ExtrudeGeometry(shape, {
        depth: height,
        bevelEnabled: false,
        curveSegments: 1,
      });
      geometry.rotateX(-Math.PI / 2);
    } catch (_error) {
      continue;
    }
    const material = new THREE.MeshStandardMaterial({
      color: 0xc3c9bd,
      roughness: 0.82,
      metalness: 0.03,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.y = Number(building.base_z) || 0;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.kind = "building";
    mesh.name = building.name || building.id || "building";
    meshes.push(mesh);
  }
  return meshes;
}

function rebuildThreeTrees(trees) {
  if (!state.three) return;
  const three = state.three;
  for (const mesh of [...three.crownMeshes, ...three.trunkMeshes]) {
    three.scene.remove(mesh);
    mesh.geometry.dispose();
    mesh.material.dispose();
  }
  three.crownMeshes = [];
  three.trunkMeshes = [];
  three.treeGroups = new Map();
  const groups = { conifer: [], deciduous: [], unknown: [] };
  for (const tree of trees) {
    if (tree.status === "removed" || tree.status === "dead") continue;
    const group = groups[tree.group] || groups.unknown;
    group.push(tree);
  }
  for (const [groupName, groupTrees] of Object.entries(groups)) {
    if (!groupTrees.length) continue;
    const crownGeometry =
      groupName === "conifer"
        ? new THREE.ConeGeometry(0.5, 1, 8, 1, false)
        : new THREE.SphereGeometry(0.5, 9, 7);
    const trunkGeometry = new THREE.CylinderGeometry(0.12, 0.2, 1, 5);
    const crownMaterial = new THREE.MeshStandardMaterial({
      roughness: 0.9,
      metalness: 0.0,
      vertexColors: false,
    });
    const trunkMaterial = new THREE.MeshStandardMaterial({ color: 0x6d5a45, roughness: 1 });
    const crowns = new THREE.InstancedMesh(crownGeometry, crownMaterial, groupTrees.length);
    const trunks = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, groupTrees.length);
    crowns.castShadow = true;
    crowns.receiveShadow = true;
    trunks.castShadow = true;
    trunks.receiveShadow = true;
    crowns.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    trunks.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    const matrix = new THREE.Matrix4();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    const position = new THREE.Vector3();
    const color = new THREE.Color();
    groupTrees.forEach((tree, index) => {
      const height = Math.max(tree.height || 2, 1.5);
      const crownRatio = Math.min(Math.max(tree.crown_ratio || 0.55, 0.2), 0.95);
      const crownDepth = Math.max(height * crownRatio, 1.0);
      const trunkHeight = Math.max(height - crownDepth, 0.8);
      const crownWidth = Math.max(tree.crown_width || height * 0.35, 0.8);
      position.set(tree.x, tree.z + trunkHeight + crownDepth * 0.5, tree.y);
      scale.set(crownWidth, crownDepth, crownWidth);
      matrix.compose(position, quaternion, scale);
      crowns.setMatrixAt(index, matrix);
      color.set(tree.color || "#68a357");
      crowns.setColorAt(index, color);
      position.set(tree.x, tree.z + trunkHeight * 0.5, tree.y);
      scale.set(1, trunkHeight, 1);
      matrix.compose(position, quaternion, scale);
      trunks.setMatrixAt(index, matrix);
    });
    crowns.instanceMatrix.needsUpdate = true;
    if (crowns.instanceColor) crowns.instanceColor.needsUpdate = true;
    trunks.instanceMatrix.needsUpdate = true;
    crowns.userData = { kind: "crown", group: groupName, trees: groupTrees };
    trunks.userData = { kind: "trunk", group: groupName, trees: groupTrees };
    three.scene.add(crowns, trunks);
    three.crownMeshes.push(crowns);
    three.trunkMeshes.push(trunks);
    three.treeGroups.set(groupName, groupTrees);
  }
  updateSelectedMarker();
}

function updateSelectedMarker() {
  if (!state.three) return;
  const three = state.three;
  if (three.selectedMarker) {
    three.scene.remove(three.selectedMarker);
    three.selectedMarker.geometry.dispose();
    three.selectedMarker.material.dispose();
    three.selectedMarker = null;
  }
  const tree = state.treeById.get(state.selectedId);
  if (!tree) return;
  const radius = Math.max(tree.crown_width || 4, 2) * 0.8;
  const geometry = new THREE.RingGeometry(radius, radius + 0.8, 24);
  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.95,
  });
  const marker = new THREE.Mesh(geometry, material);
  marker.rotation.x = -Math.PI / 2;
  marker.position.set(tree.x, tree.z + 0.25, tree.y);
  three.scene.add(marker);
  three.selectedMarker = marker;
}

function animateThree() {
  if (!state.three) return;
  const three = state.three;
  three.controls.update();
  three.renderer.render(three.scene, three.camera);
  requestAnimationFrame(animateThree);
}

function selectTree(treeId) {
  const tree = state.treeById.get(treeId);
  if (!tree) return;
  state.selectedId = treeId;
  updateMapSelection();
  updateSelectedMarker();
  $("selected-label").textContent = tree.common_name || tree.species || treeId;
  $("tree-detail").innerHTML = `
    <dl>
      <dt>ID</dt><dd>${escapeHtml(tree.id)}</dd>
      <dt>Species</dt><dd>${escapeHtml(tree.species || "Unknown")}</dd>
      <dt>Group</dt><dd>${escapeHtml(tree.group)}</dd>
      <dt>DBH</dt><dd>${tree.dbh_cm ? `${formatNumber(tree.dbh_cm, 1)} cm` : "n/a"}${measuredTag(tree.measured?.dbh)}</dd>
      <dt>Height</dt><dd>${tree.height ? `${formatNumber(tree.height, 1)} m` : "n/a"}${measuredTag(tree.measured?.height)}</dd>
      <dt>Crown</dt><dd>${tree.crown_width ? `${formatNumber(tree.crown_width, 1)} m` : "n/a"}${measuredTag(tree.measured?.crown_width)}</dd>
      <dt>Carbon</dt><dd>${formatNumber(tree.carbon_kg / 1000, 2)} t</dd>
      <dt>Source</dt><dd>${escapeHtml(tree.source || "unknown")}</dd>
    </dl>`;
  $("remove-tree").disabled = false;
  $("replace-tree").disabled = false;
  $("move-tree").disabled = false;
  loadTreeLight(treeId);
}

function updateMapSelection() {
  if (!state.map || !state.map.getSource("selected")) return;
  state.map.getSource("selected").setData(selectedFeatures());
}

function bindControls() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });
  $("change-product").addEventListener("change", (event) => switchChangeProduct(event.target.value));
  $("assistant-button").addEventListener("click", openAssistant);
  $("assistant-close").addEventListener("click", closeAssistant);
  $("assistant-new").addEventListener("click", newAssistantChat);
  $("assistant-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $("assistant-input");
    const message = input.value;
    input.value = "";
    sendAssistantMessage(message);
  });
  document.querySelectorAll("[data-assistant-prompt]").forEach((button) => {
    button.addEventListener("click", () => sendAssistantMessage(button.dataset.assistantPrompt));
  });
  $("scenario-years").addEventListener("input", (event) => {
    state.years = Number(event.target.value);
    $("scenario-years-value").textContent = `${state.years} year${state.years === 1 ? "" : "s"}`;
    $("preview-year").max = String(state.years);
  });
  $("preview-year").addEventListener("input", (event) => {
    const year = Number(event.target.value);
    state.previewYear = year;
    $("preview-year-value").textContent = `${year} year${year === 1 ? "" : "s"}`;
    if (state.playTimer) {
      window.clearInterval(state.playTimer);
      state.playTimer = null;
      $("play-year").textContent = "Play years";
    }
    loadSceneAtYear(year);
  });
  $("export-geojson").addEventListener("click", () => {
    if (state.scenarioId) window.location.href = `api/scenarios/${state.scenarioId}/export.geojson`;
  });
  $("export-csv").addEventListener("click", () => {
    if (state.scenarioId) window.location.href = `api/scenarios/${state.scenarioId}/export.csv`;
  });
  $("preview").addEventListener("click", previewScenario);
  $("reset-edits").addEventListener("click", clearEdits);
  $("new-scenario").addEventListener("click", newScenario);
  $("scenario-select").addEventListener("change", (event) => {
    if (event.target.value) loadScenario(event.target.value);
    else showBaseline();
  });
  $("remove-tree").addEventListener("click", () => {
    if (!state.selectedId) return;
    addEdit({ kind: "remove", tree_id: state.selectedId, note: "Removed in scenario" });
  });
  $("replace-tree").addEventListener("click", () => {
    if (!state.selectedId) return;
    addEdit({
      kind: "replace",
      tree_id: state.selectedId,
      species: $("plant-species").value,
      common_name: $("plant-species").value,
      dbh_cm: 8,
      note: "Replacement planting",
    });
  });
  $("move-tree").addEventListener("click", () => setMode("move"));
  $("plant-tree").addEventListener("click", () => setMode("plant"));
  $("recommend").addEventListener("click", () => recommendPlanting());
  $("plant-zone").addEventListener("click", () => setMode("zone"));
  $("play-year").addEventListener("click", togglePlay);
  $("apply-recommend").addEventListener("click", applyRecommendations);
  $("scene-reset").addEventListener("click", resetCamera);
  $("toggle-canopy").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("canopy")) {
      state.map.setLayoutProperty("canopy", "visibility", event.target.checked ? "visible" : "none");
    }
  });
  $("toggle-hillshade").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("hillshade")) {
      state.map.setLayoutProperty("hillshade", "visibility", event.target.checked ? "visible" : "none");
    }
  });
  $("toggle-buildings").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("buildings")) {
      const visibility = event.target.checked ? "visible" : "none";
      state.map.setLayoutProperty("buildings", "visibility", visibility);
      state.map.setLayoutProperty("buildings-outline", "visibility", visibility);
    }
  });
}

async function loadAssistantInfo() {
  try {
    const info = await api("api/agent");
    state.assistant.enabled = Boolean(info.enabled);
    state.assistant.available = Boolean(info.available);
    if (!info.enabled) {
      $("assistant-button").hidden = true;
      return;
    }
    $("assistant-button").hidden = false;
    const model = info.model ? String(info.model).split("/").pop() : "agent";
    $("assistant-model").textContent = info.available ? model : "opencode unavailable";
    if (!info.available) {
      $("assistant-input").disabled = true;
      $("assistant-send").disabled = true;
      $("assistant-status").textContent = "opencode is not on the service PATH";
    }
  } catch (error) {
    $("assistant-button").hidden = true;
    console.warn("Assistant info unavailable", error);
  }
}

function openAssistant() {
  if (!state.assistant.enabled) return;
  $("assistant-panel").hidden = false;
  $("assistant-button").setAttribute("aria-expanded", "true");
  $("assistant-input").focus();
}

function closeAssistant() {
  $("assistant-panel").hidden = true;
  $("assistant-button").setAttribute("aria-expanded", "false");
}

function newAssistantChat() {
  state.assistant.session = null;
  const log = $("assistant-log");
  log.replaceChildren();
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent =
    "New conversation. Ask about the dataset, a selected tree, a scenario, or the method behind a number.";
  log.append(hint);
  $("assistant-status").textContent = "";
  $("assistant-input").focus();
}

function appendAssistantMessage(role, content, options = {}) {
  const node = document.createElement("div");
  node.className = `assistant-msg ${role}`;
  if (options.html) {
    node.innerHTML = content;
  } else {
    node.textContent = content;
  }
  $("assistant-log").append(node);
  $("assistant-log").scrollTop = $("assistant-log").scrollHeight;
  return node;
}

function renderAssistantMarkdown(text) {
  const value = String(text || "");
  return value
    .split(/```/)
    .map((segment, index) => {
      if (index % 2 === 1) {
        return `<pre><code>${escapeHtml(segment.trim())}</code></pre>`;
      }
      return renderAssistantInline(segment);
    })
    .join("");
}

function renderAssistantInline(text) {
  let escaped = escapeHtml(text);
  escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");
  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  escaped = escaped.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)\s]+|\/[^)\s]+)\)|(https?:\/\/[^\s<]+|\/api\/[^\s<]+)/g,
    (_match, label, href, bare) => {
      const url = href || bare;
      if (!url) return _match;
      return `<a href="${url}" target="_blank" rel="noreferrer">${label || url}</a>`;
    }
  );
  return escaped.replace(/\n/g, "<br>");
}

function assistantContext() {
  const selected = state.treeById.get(state.selectedId);
  const metrics = state.result?.final || state.dataset?.metrics || null;
  const activeTab = document.querySelector(".tab.active")?.dataset.view || "map";
  return {
    view: activeTab,
    dataset_id: state.dataset?.dataset_id || null,
    dataset_name: state.dataset?.name || null,
    baseline_metrics: state.dataset?.metrics || null,
    selected_tree: selected
      ? {
          id: selected.id,
          species: selected.species,
          common_name: selected.common_name,
          dbh_cm: selected.dbh_cm,
          height_m: selected.height,
          crown_width_m: selected.crown_width,
          native: selected.native,
          carbon_kg: selected.carbon_kg,
        }
      : null,
    scenario_id: state.scenarioId || null,
    scenario_edits: state.edits.length,
    scenario_years: state.years,
    scenario_result: state.result
      ? {
          score: state.result.score,
          cost_cad: state.result.cost_cad,
          baseline: state.result.baseline,
          final: state.result.final,
          notes: state.result.notes,
        }
      : null,
    recommendations: state.recommendations.length,
    current_metrics: metrics,
  };
}

async function sendAssistantMessage(text) {
  if (!state.assistant.enabled || state.assistant.busy) return;
  if (!state.assistant.available) {
    $("assistant-status").textContent = "The assistant process is not available.";
    return;
  }
  const message = String(text || "").trim();
  if (!message) return;
  appendAssistantMessage("user", message);
  const thinking = appendAssistantMessage("agent", "thinking…");
  thinking.classList.add("thinking");
  state.assistant.busy = true;
  $("assistant-send").disabled = true;
  $("assistant-status").textContent = "Running the local assistant…";
  try {
    const payload = await api("api/agent/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        session: state.assistant.session,
        context: assistantContext(),
      }),
    });
    state.assistant.session = payload.session || state.assistant.session;
    thinking.remove();
    const reply = appendAssistantMessage(
      "agent",
      renderAssistantMarkdown(payload.reply || "(no reply)"),
      { html: true }
    );
    if (Array.isArray(payload.actions) && payload.actions.length) {
      const row = document.createElement("div");
      row.className = "assistant-actions";
      for (const action of payload.actions) {
        const chip = document.createElement("span");
        chip.className = "assistant-action";
        chip.textContent = `${action.tool}${action.summary ? `: ${action.summary}` : ""}`;
        chip.title = chip.textContent;
        row.append(chip);
      }
      reply.append(row);
    }
    $("assistant-status").textContent = "";
  } catch (error) {
    thinking.remove();
    const node = appendAssistantMessage("error", `Assistant unavailable: ${error.message}`);
    node.classList.add("error");
    $("assistant-status").textContent = "";
  } finally {
    state.assistant.busy = false;
    $("assistant-send").disabled = false;
    $("assistant-input").focus();
    $("assistant-log").scrollTop = $("assistant-log").scrollHeight;
  }
}

function switchView(view) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === view);
    tab.setAttribute("aria-selected", tab.dataset.view === view ? "true" : "false");
  });
  document.querySelectorAll(".view").forEach((element) => {
    element.classList.toggle("active", element.id === `view-${view}`);
  });
  if (view === "map" && state.map) {
    window.setTimeout(() => state.map.resize(), 50);
  }
  if (view === "scene") {
    ensureThree();
    window.setTimeout(() => {
      if (state.three) {
        const width = state.three.container.clientWidth;
        const height = Math.max(state.three.container.clientHeight, 1);
        state.three.renderer.setSize(width, height, false);
        state.three.camera.aspect = width / height;
        state.three.camera.updateProjectionMatrix();
      }
    }, 60);
  }
  if (view === "light") {
    ensureLightView();
    window.setTimeout(() => {
      if (state.lightMap) state.lightMap.resize();
    }, 60);
  }
  if (view === "optimize") {
    ensureOptimizeChart();
    window.setTimeout(() => {
      if (state.optimize.chart) {
        const chart = state.optimize.chart;
        const width = chart.canvas.clientWidth;
        const height = Math.max(chart.canvas.clientHeight, 1);
        chart.renderer.setSize(width, height, false);
        chart.camera.aspect = width / height;
        chart.camera.updateProjectionMatrix();
      }
    }, 60);
  }
  if (view === "change") {
    ensureChangeView();
    window.setTimeout(() => {
      if (state.changeMap) state.changeMap.resize();
    }, 60);
  }
}

function initLightControls() {
  const dateInput = $("light-date");
  dateInput.value = state.lightDate;
  const timeInput = $("light-time");
  timeInput.value = String(state.lightTime);
  $("light-time-value").textContent = formatClock(state.lightTime);
  timeInput.addEventListener("input", () => {
    state.lightTime = Number(timeInput.value);
    $("light-time-value").textContent = formatClock(state.lightTime);
    updateSunForTime();
    debounceLoadLight();
  });
  dateInput.addEventListener("change", () => {
    state.lightDate = dateInput.value;
    loadLight();
  });
  $("light-mode").addEventListener("change", (event) => {
    state.lightMode = event.target.value;
    loadLight();
  });
  $("light-refresh").addEventListener("click", loadLight);
  $("light-play").addEventListener("click", toggleLightPlay);
}

function formatClock(value) {
  const hour = Math.floor(value);
  const minute = Math.round((value - hour) * 60);
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function debounceLoadLight() {
  window.clearTimeout(state.lightDebounce);
  state.lightDebounce = window.setTimeout(loadLight, 420);
}

function ensureLightView() {
  if (state.lightMap) {
    loadLight();
    return;
  }
  const [west, south, east, north] = state.scene.bounds_wgs84;
  const coordinates = state.scene.corners_wgs84 || [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
  const map = new maplibregl.Map({
    container: "map-light",
    style: {
      version: 8,
      sources: {
        canopy: { type: "image", url: "api/canopy.png?width=1400", coordinates },
        shade: { type: "image", url: "api/shade.png?width=1400", coordinates },
        buildings: { type: "geojson", data: buildingFeatures() },
        boundary: { type: "geojson", data: boundaryFeatures() },
      },
      layers: [
        { id: "background", type: "background", paint: { "background-color": "#e6eae2" } },
        {
          id: "canopy",
          type: "raster",
          source: "canopy",
          paint: { "raster-opacity": 0.24, "raster-resampling": "linear" },
        },
        {
          id: "shade",
          type: "raster",
          source: "shade",
          paint: { "raster-opacity": 0.92, "raster-resampling": "nearest" },
        },
        {
          id: "buildings-outline",
          type: "line",
          source: "buildings",
          paint: { "line-color": "#8b948a", "line-width": 0.7, "line-opacity": 0.75 },
        },
        {
          id: "boundary",
          type: "line",
          source: "boundary",
          paint: { "line-color": "#2f6b4f", "line-width": 1.3, "line-dasharray": [2, 2] },
        },
      ],
    },
    center: [(west + east) / 2, (south + north) / 2],
    zoom: 14,
    attributionControl: false,
  });
  map.addControl(new maplibregl.NavigationControl(), "bottom-right");
  map.on("load", () => {
    map.fitBounds(
      [
        [west, south],
        [east, north],
      ],
      { padding: 36, duration: 0 }
    );
    loadLight();
  });
  state.lightMap = map;
}

async function loadLight() {
  if (!state.lightMap || !state.lightMap.getSource("shade")) return;
  const request = ++state.lightRequest;
  const mode = $("light-mode").value;
  const date = $("light-date").value || state.lightDate;
  const params = new URLSearchParams({ date, mode });
  if (mode === "instant") params.set("times", formatClock(state.lightTime));
  if (mode === "day") params.set("times", "09:00,12:00,15:00,18:00");
  $("light-status").textContent = "computing";
  try {
    const data = await api(`api/shade?${params.toString()}`);
    if (request !== state.lightRequest) return;
    state.lightData = data;
    renderLightStats(data);
    renderLightLegend(data.legend || []);
    const url = `api/shade.png?${params.toString()}&v=${encodeURIComponent(data.image_version || Date.now())}`;
    updateLightImage(url, data.image_corners_wgs84);
    updateSunFromData(data);
    $("light-status").textContent = mode === "annual" ? "annual sample" : mode;
  } catch (error) {
    if (request !== state.lightRequest) return;
    $("light-status").textContent = "unavailable";
    $("light-stats").innerHTML =
      '<div class="change-empty">The shade engine could not build this period.</div>';
    toast(`Shade request failed: ${error.message}`, true);
  }
}

function updateLightImage(url, coordinates) {
  if (!state.lightMap) return;
  const source = state.lightMap.getSource("shade");
  if (!source) return;
  try {
    source.updateImage({ url, coordinates });
  } catch (_error) {
    if (state.lightMap.getLayer("shade")) state.lightMap.removeLayer("shade");
    if (state.lightMap.getSource("shade")) state.lightMap.removeSource("shade");
    state.lightMap.addSource("shade", { type: "image", url, coordinates });
    state.lightMap.addLayer(
      {
        id: "shade",
        type: "raster",
        source: "shade",
        paint: { "raster-opacity": 0.92, "raster-resampling": "nearest" },
      },
      "buildings-outline"
    );
  }
}

function renderLightStats(data) {
  const metrics = data.metrics || {};
  const solar = data.solar && data.solar.length ? data.solar[0] : {};
  $("light-stats").innerHTML = `
    <div class="change-stat"><span>Sun altitude</span><strong>${formatNumber(solar.altitude_deg, 0)}°</strong></div>
    <div class="change-stat"><span>Sunlit</span><strong>${formatNumber(Number(metrics.sunlit_fraction || 0) * 100, 0)}%</strong></div>
    <div class="change-stat"><span>Tree shade</span><strong>${formatNumber(Number(metrics.tree_shade_fraction || 0) * 100, 1)}%</strong></div>
    <div class="change-stat"><span>Building shade</span><strong>${formatNumber(Number(metrics.building_shade_fraction || 0) * 100, 1)}%</strong></div>
    <div class="change-stat"><span>Marginal tree</span><strong>${formatNumber(Number(metrics.marginal_tree_shade_fraction || 0) * 100, 1)}%</strong></div>
    <div class="change-stat"><span>Annual estimate</span><strong>${formatCompact(Number(metrics.annual_shade_hours_estimate || 0), " h")}</strong></div>`;
}

function renderLightLegend(legend) {
  $("light-legend").innerHTML = legend
    .map(
      (item) =>
        `<span><i class="change-swatch" style="background:${item.colour}"></i>${escapeHtml(item.label)}</span>`
    )
    .join("");
}

function updateSunFromData(data) {
  const solar = data.solar && data.solar.length ? data.solar[0] : null;
  if (solar) updateSun(Number(solar.altitude_deg), Number(solar.azimuth_deg));
}

async function updateSunForTime() {
  try {
    const params = new URLSearchParams({
      date: $("light-date").value || state.lightDate,
      time: formatClock(state.lightTime),
    });
    const data = await api(`api/solar?${params.toString()}`);
    const position = data.position || {};
    updateSun(Number(position.altitude_deg || 0), Number(position.azimuth_deg || 0));
  } catch (_error) {
    // The 3D scene keeps its last sun position.
  }
}

function updateSun(altitude, azimuth) {
  state.lastSolar = { altitude, azimuth };
  $("sun-readout").textContent = `Sun ${altitude.toFixed(0)}° / ${azimuth.toFixed(0)}°`;
  const three = state.three;
  if (!three) return;
  const radius = 760;
  const alt = (altitude * Math.PI) / 180;
  const az = (azimuth * Math.PI) / 180;
  const x = Math.sin(az) * Math.cos(alt) * radius;
  const y = Math.sin(alt) * radius;
  const z = Math.cos(az) * Math.cos(alt) * radius;
  three.sunLight.position.set(x, y, z);
  three.sunLight.target.position.set(0, 0, 0);
  three.sunLight.target.updateMatrixWorld();
  three.sunLight.intensity = altitude > 0 ? 0.35 + 1.65 * Math.min(1, altitude / 65) : 0.06;
  three.sunSphere.position.set(x, y, z);
  three.sunSphere.visible = altitude > -6;
  three.sunSphere.material.color.set(altitude > 0 ? 0xffe6a0 : 0x667788);
}

function applySun() {
  if (state.lastSolar) updateSun(state.lastSolar.altitude, state.lastSolar.azimuth);
}

function toggleLightPlay() {
  if (state.lightTimer) {
    window.clearInterval(state.lightTimer);
    state.lightTimer = null;
    $("light-play").textContent = "Play day";
    return;
  }
  state.lightMode = "instant";
  $("light-mode").value = "instant";
  state.lightTime = 6;
  $("light-play").textContent = "Stop day";
  state.lightTimer = window.setInterval(() => {
    state.lightTime = Math.min(21, state.lightTime + 0.5);
    $("light-time").value = String(state.lightTime);
    $("light-time-value").textContent = formatClock(state.lightTime);
    updateSunForTime();
    if (Math.abs(state.lightTime % 2) < 0.01) loadLight();
    if (state.lightTime >= 21) {
      window.clearInterval(state.lightTimer);
      state.lightTimer = null;
      $("light-play").textContent = "Play day";
      loadLight();
    }
  }, 420);
}

async function loadTreeLight(treeId) {
  const container = $("tree-light");
  container.innerHTML = '<p class="muted">Calculating shade and water…</p>';
  const params = new URLSearchParams({
    date: $("light-date").value || state.lightDate,
    mode: "day",
    times: "09:00,12:00,15:00",
  });
  try {
    const data = await api(`api/light/tree/${encodeURIComponent(treeId)}?${params.toString()}`);
    if (state.selectedId !== treeId) return;
    renderTreeLight(data);
  } catch (error) {
    if (state.selectedId !== treeId) return;
    container.innerHTML = `<p class="hint">${escapeHtml(error.message)}</p>`;
  }
}

function renderTreeLight(data) {
  const shade = data.shade || {};
  const fit = data.fit || {};
  const water = data.water || {};
  const growth = (data.growth && data.growth.response) || {};
  const options = data.irrigation || [];
  const best = options.find((option) => option.recommendation === "best balance") || options[0] || {};
  const evidence = fit.evidence || shade.evidence || {};
  $("tree-light").innerHTML = `
    <div class="mini-grid">
      <div class="mini-card"><span>Sun at base</span><strong>${formatNumber(Number(shade.sun_fraction_at_base || 0) * 100, 0)}%</strong></div>
      <div class="mini-card"><span>Marginal shade</span><strong>${formatCompact(Number(shade.marginal_shade_area_hours || 0), " m²h")}</strong></div>
      <div class="mini-card"><span>Shade efficiency</span><strong>${formatNumber(Number(shade.shade_efficiency_m2h_per_m3 || 0), 1)}</strong></div>
      <div class="mini-card"><span>Species fit</span><strong>${formatNumber(Number(fit.score || 0), 2)}</strong></div>
      <div class="mini-card"><span>Vigour</span><strong>${formatNumber(Number(growth.vigor_score || 0), 2)}</strong></div>
      <div class="mini-card"><span>Stress days</span><strong>${formatNumber(Number(water.stress_days || 0))}</strong></div>
      <div class="mini-card"><span>Water cost</span><strong>$${formatNumber(Number(water.annual_cost_cad || 0))}</strong></div>
      <div class="mini-card"><span>Best policy</span><strong>${escapeHtml(best.policy || "n/a")}</strong></div>
    </div>
    ${evidenceBadge(evidence)}
    <p class="hint">${escapeHtml((fit.limiting_factors || []).length ? `Limiting: ${(fit.limiting_factors || []).join(", ")}` : "No major trait limitation in this screen.")}</p>`;
}

function evidenceBadge(evidence) {
  if (!evidence || !evidence.tier) return "";
  return `<span class="evidence-badge">evidence <strong>${escapeHtml(evidence.tier)}</strong> · ${escapeHtml(evidence.method || "")}</span>`;
}

function initOptimizeControls() {
  $("optimize-run").addEventListener("click", runOptimization);
  $("optimize-reset").addEventListener("click", resetParetoView);
  $("pareto-load").addEventListener("click", loadParetoScenario);
  for (const id of ["pareto-x", "pareto-y", "pareto-z", "pareto-colour", "pareto-size"]) {
    $(id).addEventListener("change", drawPareto);
  }
  $("pareto-slice-objective").addEventListener("change", drawPareto);
  $("pareto-slice").addEventListener("input", () => {
    const value = Number($("pareto-slice").value) / 100;
    $("pareto-slice-value").textContent = value <= 0 ? "all" : `>= ${value.toFixed(2)}`;
    drawPareto();
  });
}

function ensureOptimizeChart() {
  if (state.optimize.chart) return state.optimize.chart;
  const canvas = $("pareto-canvas");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(canvas.clientWidth, Math.max(canvas.clientHeight, 1), false);
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, canvas.clientWidth / Math.max(canvas.clientHeight, 1), 0.1, 100);
  camera.position.set(2.8, 2.2, 2.9);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.set(0, 0, 0);
  controls.minDistance = 1.2;
  controls.maxDistance = 8;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x63705d, 1.4));
  const light = new THREE.DirectionalLight(0xffffff, 1.4);
  light.position.set(3, 5, 4);
  scene.add(light);
  const box = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(3.2, 3.2, 3.2)),
    new THREE.LineBasicMaterial({ color: 0x8fa68a, transparent: true, opacity: 0.55 })
  );
  scene.add(box);
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  canvas.addEventListener("click", (event) => {
    if (!state.optimize.mesh) return;
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObject(state.optimize.mesh, false);
    if (!hits.length) return;
    const index = hits[0].instanceId;
    const solutions = state.optimize.mesh.userData.solutions || [];
    if (index !== undefined && solutions[index]) renderParetoInfo(solutions[index]);
  });
  const chart = { renderer, scene, camera, controls, canvas, mesh: null };
  window.addEventListener("resize", () => {
    if (!chart.canvas.clientWidth) return;
    renderer.setSize(chart.canvas.clientWidth, Math.max(chart.canvas.clientHeight, 1), false);
    camera.aspect = chart.canvas.clientWidth / Math.max(chart.canvas.clientHeight, 1);
    camera.updateProjectionMatrix();
  });
  state.optimize.chart = chart;
  animatePareto();
  return chart;
}

function animatePareto() {
  const chart = state.optimize.chart;
  if (!chart) return;
  chart.controls.update();
  chart.renderer.render(chart.scene, chart.camera);
  requestAnimationFrame(animatePareto);
}

async function runOptimization() {
  $("optimize-run").disabled = true;
  $("optimize-status").textContent = "starting";
  $("pareto-info").innerHTML = '<p class="muted">Building the problem and starting Fresh Solutions...</p>';
  try {
    const payload = await api("api/optimize", {
      method: "POST",
      body: JSON.stringify({
        sites: Number($("opt-sites").value),
        scalarizations: Number($("opt-scalarizations").value),
        population: Number($("opt-population").value),
        generations: Number($("opt-generations").value),
        workers: Number($("opt-workers").value),
        budget_cad: Number($("opt-budget").value),
        max_sites: Number($("opt-max-sites").value),
        horizon: 30,
        seed: 42,
      }),
    });
    state.optimize.jobId = payload.job_id;
    state.optimize.result = null;
    state.optimize.selected = null;
    $("pareto-load").disabled = true;
    clearParetoMesh();
    $("pareto-slice").value = "0";
    $("pareto-slice-value").textContent = "all";
    $("optimize-status").textContent = "queued";
    pollOptimization(payload.job_id);
  } catch (error) {
    $("optimize-run").disabled = false;
    $("optimize-status").textContent = "unavailable";
    $("pareto-info").innerHTML = `<p class="hint">${escapeHtml(error.message)}</p>`;
    toast(`Optimization failed: ${error.message}`, true);
  }
}

async function pollOptimization(jobId) {
  window.clearTimeout(state.optimize.pollTimer);
  try {
    const payload = await api(`api/optimize/${encodeURIComponent(jobId)}`);
    $("optimize-status").textContent =
      payload.status === "running" ? `running ${payload.progress}/${payload.total}` : payload.status;
    renderParetoStats(payload);
    if (payload.status === "done" && payload.result) {
      state.optimize.result = payload.result;
      renderParetoArchive(payload.result);
      $("optimize-run").disabled = false;
      return;
    }
    if (payload.status === "error") {
      $("optimize-run").disabled = false;
      $("pareto-info").innerHTML = `<p class="hint">${escapeHtml(payload.error || "optimization failed")}</p>`;
      return;
    }
    state.optimize.pollTimer = window.setTimeout(() => pollOptimization(jobId), 700);
  } catch (error) {
    $("optimize-run").disabled = false;
    $("optimize-status").textContent = "error";
    $("pareto-info").innerHTML = `<p class="hint">${escapeHtml(error.message)}</p>`;
  }
}

function renderParetoStats(payload) {
  const archive = payload.result && payload.result.archive ? payload.result.archive : null;
  const solutions = archive && archive.solutions ? archive.solutions.length : 0;
  const hypervolume = archive ? Number(archive.hypervolume || 0) : 0;
  $("optimize-stats").innerHTML = `
    <div class="change-stat"><span>Progress</span><strong>${formatNumber(payload.progress)}/${formatNumber(payload.total)}</strong></div>
    <div class="change-stat"><span>Archive</span><strong>${formatNumber(solutions || payload.archive_size || 0)}</strong></div>
    <div class="change-stat"><span>Hypervolume</span><strong>${hypervolume.toFixed(4)}</strong></div>
    <div class="change-stat"><span>Status</span><strong>${escapeHtml(payload.status)}</strong></div>`;
}

function renderParetoArchive(result) {
  const archive = result.archive;
  if (!archive || !archive.solutions || !archive.solutions.length) {
    $("pareto-info").innerHTML = '<p class="hint">No feasible non-dominated solutions were found.</p>';
    return;
  }
  populateParetoSelects(archive.objectives || []);
  renderParetoStats({ status: "done", progress: result.scalarizations, total: result.scalarizations, result });
  drawPareto();
  $("optimize-status").textContent = "done";
}

function populateParetoSelects(objectives) {
  const names = objectives.map((objective) => objective.label || objective.name);
  const fill = (id, defaultIndex, includeUniform = false) => {
    const select = $(id);
    const previous = select.value;
    select.innerHTML =
      (includeUniform ? '<option value="-1">uniform</option>' : "") +
      names
        .map((name, index) => `<option value="${index}">${escapeHtml(name)}</option>`)
        .join("");
    select.value = previous && previous !== "" ? previous : String(defaultIndex);
  };
  fill("pareto-x", 0);
  fill("pareto-y", 1);
  fill("pareto-z", 2);
  fill("pareto-colour", Math.min(3, names.length - 1));
  fill("pareto-size", -1, true);
  fill("pareto-slice-objective", 0);
}

function paretoNorm(archive, objectiveIndex, value) {
  const ideal = Number(archive.ideal[objectiveIndex] || 0);
  const nadir = Number(archive.nadir[objectiveIndex] || 0);
  const low = Math.min(ideal, nadir);
  const high = Math.max(ideal, nadir);
  if (high - low <= 1e-12) return 0.5;
  return Math.max(0, Math.min(1, (value - low) / (high - low)));
}

function drawPareto() {
  const chart = ensureOptimizeChart();
  const result = state.optimize.result;
  if (!result || !result.archive) return;
  const archive = result.archive;
  const solutions = archive.solutions || [];
  const xIndex = Number($("pareto-x").value || 0);
  const yIndex = Number($("pareto-y").value || 1);
  const zIndex = Number($("pareto-z").value || 2);
  const colourIndex = Number($("pareto-colour").value || 0);
  const sizeIndex = Number($("pareto-size").value || -1);
  const sliceIndex = Number($("pareto-slice-objective").value || 0);
  const threshold = Number($("pareto-slice").value) / 100;
  const filtered = solutions
    .map((solution) => ({
      solution,
      x: paretoNorm(archive, xIndex, Number(solution.objectives[xIndex])),
      y: paretoNorm(archive, yIndex, Number(solution.objectives[yIndex])),
      z: paretoNorm(archive, zIndex, Number(solution.objectives[zIndex])),
      colour: paretoNorm(archive, colourIndex, Number(solution.objectives[colourIndex])),
      size: sizeIndex >= 0 ? paretoNorm(archive, sizeIndex, Number(solution.objectives[sizeIndex])) : 0.5,
      slice: paretoNorm(archive, sliceIndex, Number(solution.objectives[sliceIndex])),
    }))
    .filter((point) => threshold <= 0 || point.slice >= threshold);
  state.optimize.filtered = filtered.map((point) => point.solution);
  clearParetoMesh();
  if (!filtered.length) {
    $("pareto-info").innerHTML = '<p class="hint">The slice is empty. Lower the slice threshold.</p>';
    chart.renderer.render(chart.scene, chart.camera);
    return;
  }
  const geometry = new THREE.SphereGeometry(0.045, 10, 8);
  const material = new THREE.MeshStandardMaterial({ roughness: 0.42, metalness: 0.08 });
  const mesh = new THREE.InstancedMesh(geometry, material, filtered.length);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const scale = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const color = new THREE.Color();
  filtered.forEach((point, index) => {
    position.set((point.x - 0.5) * 3.2, (point.y - 0.5) * 3.2, (point.z - 0.5) * 3.2);
    const size = 0.55 + point.size * 1.25;
    scale.set(size, size, size);
    matrix.compose(position, quaternion, scale);
    mesh.setMatrixAt(index, matrix);
    color.setHSL(0.58 - point.colour * 0.46, 0.68, 0.48);
    mesh.setColorAt(index, color);
  });
  mesh.instanceMatrix.needsUpdate = true;
  mesh.userData.solutions = filtered.map((point) => point.solution);
  chart.scene.add(mesh);
  chart.mesh = mesh;
  state.optimize.mesh = mesh;
  const labels = archive.objectives.map((objective) => objective.label || objective.name);
  $("pareto-legend").innerHTML =
    `<span><i class="change-swatch" style="background:hsl(210 68% 48%)"></i>low ${escapeHtml(labels[colourIndex] || "")}</span>` +
    `<span><i class="change-swatch" style="background:hsl(73 68% 48%)"></i>high ${escapeHtml(labels[colourIndex] || "")}</span>` +
    `<span>${filtered.length} of ${solutions.length} solutions</span>`;
  $("pareto-info").innerHTML = `<p class="muted">${filtered.length} visible solutions. Click a sphere to inspect it.</p>`;
  chart.renderer.render(chart.scene, chart.camera);
}

function clearParetoMesh() {
  const chart = state.optimize.chart;
  if (chart && chart.mesh) {
    chart.scene.remove(chart.mesh);
    chart.mesh.geometry.dispose();
    chart.mesh.material.dispose();
    chart.mesh = null;
  }
  state.optimize.mesh = null;
}

function paretoScreenPositions() {
  const chart = state.optimize.chart;
  const mesh = state.optimize.mesh;
  if (!chart || !mesh) return [];
  const matrix = new THREE.Matrix4();
  const point = new THREE.Vector3();
  const result = [];
  for (let index = 0; index < mesh.count; index += 1) {
    mesh.getMatrixAt(index, matrix);
    point.setFromMatrixPosition(matrix);
    point.project(chart.camera);
    result.push({
      x: (point.x * 0.5 + 0.5) * chart.canvas.clientWidth,
      y: (-point.y * 0.5 + 0.5) * chart.canvas.clientHeight,
    });
  }
  return result;
}

function renderParetoInfo(solution) {
  const result = state.optimize.result;
  if (!result || !result.archive) return;
  const archive = result.archive;
  const labels = archive.objectives.map((objective) => objective.label || objective.name);
  const rows = labels
    .map((label, index) => `<div class="mini-card"><span>${escapeHtml(label)}</span><strong>${formatNumber(Number(solution.objectives[index] || 0), 2)}</strong></div>`)
    .join("");
  $("pareto-info").innerHTML = `
    <div class="mini-grid">${rows}</div>
    <p class="hint">Planted sites: ${formatNumber((solution.planted || []).length)} · robustness ${formatNumber(Number(solution.robustness || 0), 2)} · id ${escapeHtml(solution.solution_id)}</p>`;
  state.optimize.selected = solution;
  $("pareto-load").disabled = false;
}

async function loadParetoScenario() {
  const selected = state.optimize.selected;
  const jobId = state.optimize.jobId;
  if (!selected || !jobId) return;
  try {
    const scenario = await api(`api/optimize/${encodeURIComponent(jobId)}/scenario`, {
      method: "POST",
      body: JSON.stringify({ solution_id: selected.solution_id }),
    });
    await refreshScenarioOptions();
    await loadScenario(scenario.scenario_id);
    switchView("map");
    toast("Pareto solution loaded as a scenario");
  } catch (error) {
    toast(`Could not load the solution: ${error.message}`, true);
  }
}

function resetParetoView() {
  const chart = state.optimize.chart;
  if (!chart) return;
  chart.camera.position.set(2.8, 2.2, 2.9);
  chart.controls.target.set(0, 0, 0);
  chart.controls.update();
}

async function populateChangeProducts() {
  if (state.changeProductsLoaded) return;
  state.changeProductsLoaded = true;
  try {
    const payload = await api("api/changes");
    const products = payload.products || [];
    const select = $("change-product");
    select.innerHTML = products
      .map(
        (product) =>
          `<option value="${escapeHtml(product.id)}">${escapeHtml(product.label)}</option>`
      )
      .join("");
    if (products.some((product) => product.id === state.changeProduct)) {
      select.value = state.changeProduct;
    } else if (products.length) {
      state.changeProduct = products[0].id;
      select.value = state.changeProduct;
    }
  } catch (error) {
    // Keep the default product when the index is unavailable.
  }
}

function switchChangeProduct(product) {
  if (!product || product === state.changeProduct) return;
  if (state.changeMap) {
    state.changeMap.remove();
    state.changeMap = null;
  }
  state.changeData = null;
  state.changeProduct = product;
  $("change-status").textContent = "loading";
  ensureChangeView();
}

async function ensureChangeView() {
  if (state.changeMap) return;
  try {
    await populateChangeProducts();
    const data = await api(`api/change?product=${encodeURIComponent(state.changeProduct)}`);
    state.changeData = data;
    renderChangeStats(data);
    renderChangeLegend(data.legend || []);
    const [west, south, east, north] = data.valid_bounds_wgs84 || data.bounds_wgs84;
    const coordinates = data.image_corners_wgs84 || data.corners_wgs84 || [
      [west, north],
      [east, north],
      [east, south],
      [west, south],
    ];
    const map = new maplibregl.Map({
      container: "map-change",
      style: {
        version: 8,
        sources: {
          canopy: {
            type: "image",
            url: "api/canopy.png?width=1400",
            coordinates: state.scene.corners_wgs84 || coordinates,
          },
          change: {
            type: "image",
            url: `api/change.png?product=${encodeURIComponent(state.changeProduct)}&v=${encodeURIComponent(data.image_version || Date.now())}`,
            coordinates,
          },
          buildings: { type: "geojson", data: buildingFeatures() },
          boundary: { type: "geojson", data: boundaryFeatures() },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#e6eae2" } },
          {
            id: "canopy",
            type: "raster",
            source: "canopy",
            paint: { "raster-opacity": 0.28, "raster-resampling": "linear" },
          },
          {
            id: "change",
            type: "raster",
            source: "change",
            paint: { "raster-opacity": 0.88, "raster-resampling": "nearest" },
          },
          {
            id: "buildings-outline",
            type: "line",
            source: "buildings",
            paint: { "line-color": "#8b948a", "line-width": 0.65, "line-opacity": 0.7 },
          },
          {
            id: "boundary",
            type: "line",
            source: "boundary",
            paint: { "line-color": "#2f6b4f", "line-width": 1.3, "line-dasharray": [2, 2] },
          },
        ],
      },
      center: [(west + east) / 2, (south + north) / 2],
      zoom: 14,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl(), "bottom-right");
    map.on("load", () => {
      map.fitBounds(
        [
          [west, south],
          [east, north],
        ],
        { padding: 36, duration: 0 }
      );
    });
    state.changeMap = map;
    $("change-status").textContent = "observed";
  } catch (error) {
    $("change-status").textContent = "none";
    $("change-labels").textContent = "No observed-change product for this dataset.";
    $("change-stats").innerHTML =
      '<div class="change-empty">Build one with <code>fresh-urban-forest build-change --earlier … --later … --out-dir …</code>.</div>';
    $("change-legend").innerHTML = "";
    $("change-note").textContent =
      "Observed change compares two real canopy-height surfaces; it is not a scenario projection.";
  }
}

function renderChangeStats(data) {
  $("change-labels").textContent = `${data.earlier_label} → ${data.later_label}`;
  const metrics = data.metrics || {};
  const net = Number(metrics.net_m2 || 0);
  const gain = Number(metrics.gain_m2 || 0);
  const loss = Number(metrics.loss_m2 || 0);
  const stable = Number(metrics.stable_m2 || 0);
  const height = Number(metrics.mean_height_change_m || 0);
  const overlap = Number(data.valid_overlap_m2 || 0);
  $("change-stats").innerHTML = `
    <div class="change-stat ${net < 0 ? "loss" : "gain"}"><span>Net canopy</span><strong>${net >= 0 ? "+" : ""}${formatCompact(net / 10000, " ha")}</strong></div>
    <div class="change-stat gain"><span>Gain</span><strong>${formatCompact(gain / 10000, " ha")}</strong></div>
    <div class="change-stat loss"><span>Loss</span><strong>${formatCompact(loss / 10000, " ha")}</strong></div>
    <div class="change-stat"><span>Stable</span><strong>${formatCompact(stable / 10000, " ha")}</strong></div>
    <div class="change-stat"><span>Height change</span><strong>${height >= 0 ? "+" : ""}${height.toFixed(2)} m</strong></div>
    <div class="change-stat"><span>Overlap</span><strong>${formatCompact(overlap / 10000, " ha")}</strong></div>`;
}

function renderChangeLegend(legend) {
  $("change-legend").innerHTML = legend
    .map(
      (item) =>
        `<span><i class="change-swatch" style="background:${item.colour}"></i>${escapeHtml(item.label)}</span>`
    )
    .join("");
}

function setMode(mode) {
  state.mode = state.mode === mode ? null : mode;
  const active = Boolean(state.mode);
  $("mode-hint").hidden = !active;
  $("mode-hint").textContent =
    state.mode === "move"
      ? "Click a new place on the map or terrain to move the selected tree."
      : state.mode === "zone"
        ? "Click a point on the map or terrain to centre a planting zone."
        : "Click an open place on the map or terrain to plant.";
  $("plant-tree").classList.toggle("primary", state.mode !== "plant");
  if (state.map) state.map.getCanvas().style.cursor = active ? "crosshair" : "";
}

function placeAt(lon, lat) {
  if (state.mode === "plant") {
    const species = $("plant-species").value || "Unknown";
    const edit = {
      kind: "plant",
      tree_id: `plant-${Date.now()}`,
      lon,
      lat,
      species,
      common_name: species,
      dbh_cm: 6,
      height_m: null,
      crown_width_m: null,
      note: "Planting placed in the prototype",
    };
    addEdit(edit, { optimisticTree: true });
  } else if (state.mode === "zone") {
    recommendPlanting([lon, lat]);
  } else if (state.mode === "move" && state.selectedId) {
    addEdit({
      kind: "move",
      tree_id: state.selectedId,
      lon,
      lat,
      note: "Moved in scenario",
    });
    const tree = state.treeById.get(state.selectedId);
    if (tree) {
      tree.lon = lon;
      tree.lat = lat;
      const [originLon, originLat] = state.scene.origin_lonlat;
      const [mx, my] = state.scene.meters_per_degree;
      tree.x = (lon - originLon) * mx;
      tree.y = (lat - originLat) * my;
      rebuildThreeTrees([...state.treeById.values()]);
    }
  }
  setMode(null);
}

function addEdit(edit, options = {}) {
  state.edits.push(edit);
  renderEditList();
  if (options.optimisticTree && edit.lon && edit.lat) {
    const [originLon, originLat] = state.scene.origin_lonlat;
    const [mx, my] = state.scene.meters_per_degree;
    const tree = {
      id: edit.tree_id,
      lon: edit.lon,
      lat: edit.lat,
      x: (edit.lon - originLon) * mx,
      y: (edit.lat - originLat) * my,
      z: 0,
      height: 3,
      crown_width: 1.5,
      dbh_cm: 6,
      crown_ratio: 0.55,
      species: edit.species,
      common_name: edit.common_name,
      group: /cedar|pine|fir|spruce|hemlock|yew/i.test(edit.species) ? "conifer" : "deciduous",
      native: false,
      status: "planted",
      source: "scenario",
      color: "#68a357",
      carbon_kg: 1,
    };
    state.treeById.set(tree.id, tree);
    state.scene.trees.push(tree);
    rebuildThreeTrees(state.scene.trees);
    updateMapTrees();
    selectTree(tree.id);
  }
  toast("Edit queued. Preview the scenario to project it.");
}

function renderEditList() {
  const list = $("edit-list");
  if (!state.edits.length) {
    list.innerHTML = '<p class="muted">No edits yet. Remove, replace, move, or plant a tree.</p>';
    return;
  }
  list.innerHTML = state.edits
    .map(
      (edit, index) => `
        <div class="edit-item">
          <span><span class="edit-kind ${edit.kind}">${edit.kind}</span> ${escapeHtml(
            edit.species || edit.tree_id
          )}</span>
          <button class="button tiny ghost" data-remove-edit="${index}" type="button">undo</button>
        </div>`
    )
    .join("");
  list.querySelectorAll("[data-remove-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      state.edits.splice(Number(button.dataset.removeEdit), 1);
      renderEditList();
    });
  });
}

function togglePlay() {
  if (state.playTimer) {
    window.clearInterval(state.playTimer);
    state.playTimer = null;
    $("play-year").textContent = "Play years";
    return;
  }
  if (!state.result) {
    toast("Preview a scenario before playing the years.");
    return;
  }
  const max = Number($("preview-year").max) || state.result.years;
  let year = Number($("preview-year").value);
  if (year >= max) year = 0;
  $("play-year").textContent = "Pause";
  state.playTimer = window.setInterval(() => {
    year += 1;
    if (year > max) {
      window.clearInterval(state.playTimer);
      state.playTimer = null;
      $("play-year").textContent = "Play years";
      return;
    }
    $("preview-year").value = String(year);
    $("preview-year-value").textContent = `${year} year${year === 1 ? "" : "s"}`;
    loadSceneAtYear(year);
  }, 700);
}

function updateExportButtons() {
  const enabled = Boolean(state.scenarioId);
  $("export-geojson").disabled = !enabled;
  $("export-csv").disabled = !enabled;
}

async function loadSceneAtYear(year) {
  if (!state.scenarioId) return;
  try {
    const scene = await api(
      `api/scene?scenario_id=${encodeURIComponent(state.scenarioId)}&year=${year}`
    );
    state.scene = scene;
    state.treeById = new Map(scene.trees.map((tree) => [tree.id, tree]));
    updateMapTrees();
    rebuildThreeTrees(scene.trees);
    const item = state.result?.timeline?.find((entry) => Number(entry.year) === year);
    if (item) {
      renderKPIs(item);
      renderComposition(item);
      renderSize(item);
    }
    if (state.result) {
      $("scenario-verdict").textContent = `${state.result.name} · year ${year} · score ${state.result.score}`;
    }
  } catch (error) {
    toast(error.message, true);
  }
}

function clearEdits() {
  state.edits = [];
  state.sentEditCount = 0;
  state.scenarioId = "";
  state.revision = 0;
  state.result = null;
  $("scenario-select").value = "";
  renderEditList();
  $("scenario-revision").textContent = "baseline";
  updateExportButtons();
  showBaseline();
}

function newScenario() {
  state.edits = [];
  state.sentEditCount = 0;
  state.scenarioId = "";
  state.revision = 0;
  state.result = null;
  $("scenario-name").value = "New campus scenario";
  $("scenario-select").value = "";
  $("scenario-revision").textContent = "draft";
  renderEditList();
  updateExportButtons();
  showBaseline();
}

async function ensureScenario() {
  if (!state.scenarioId) {
    const scenario = await api("/api/scenarios", {
      method: "POST",
      body: JSON.stringify({
        name: $("scenario-name").value || "Campus scenario",
        years: state.years,
        edits: state.edits,
      }),
    });
    state.scenarioId = scenario.scenario_id;
    state.revision = scenario.revision;
    state.sentEditCount = state.edits.length;
    await refreshScenarioOptions();
  } else if (state.edits.length > state.sentEditCount) {
    const newEdits = state.edits.slice(state.sentEditCount);
    const scenario = await api(`/api/scenarios/${state.scenarioId}`, {
      method: "PATCH",
      body: JSON.stringify({ edits: newEdits, revision: state.revision }),
    });
    state.revision = scenario.revision;
    state.sentEditCount = state.edits.length;
    await refreshScenarioOptions();
  }
  $("scenario-revision").textContent = `revision ${state.revision}`;
}

async function previewScenario() {
  try {
    setStatus("projecting");
    await ensureScenario();
    const result = await api(`/api/scenarios/${state.scenarioId}/project`, { method: "POST" });
    state.result = result;
    state.previewYear = result.years;
    $("preview-year").max = String(result.years);
    $("preview-year").value = String(result.years);
    $("preview-year-value").textContent = `${result.years} year${result.years === 1 ? "" : "s"}`;
    const scene = await api(
      `api/scene?scenario_id=${encodeURIComponent(state.scenarioId)}&year=${result.years}`
    );
    state.scene = scene;
    state.treeById = new Map(scene.trees.map((tree) => [tree.id, tree]));
    updateMapTrees();
    rebuildThreeTrees(scene.trees);
    renderKPIs(result.final);
    renderTimeline(result.timeline);
    renderComposition({ species_composition: result.final.species_composition || [] });
    renderSize(result.final);
    const baseline = result.baseline;
    const final = result.final;
    const coverDelta = final.canopy_cover_pct - baseline.canopy_cover_pct;
    const volumeDelta = final.canopy_volume_m3 - baseline.canopy_volume_m3;
    const carbonDelta = (final.total_carbon_kg - baseline.total_carbon_kg) / 1000;
    const nativeDelta = (final.native_fraction - baseline.native_fraction) * 100;
    $("scenario-verdict").textContent = `${result.name} · ${result.years} years · score ${result.score}`;
    $("delta-strip").innerHTML = `
      <span class="delta ${coverDelta < 0 ? "negative" : ""}"><b>${coverDelta >= 0 ? "+" : ""}${coverDelta.toFixed(1)}%</b> cover</span>
      <span class="delta ${volumeDelta < 0 ? "negative" : ""}"><b>${volumeDelta >= 0 ? "+" : ""}${formatCompact(volumeDelta)}</b> m³</span>
      <span class="delta ${carbonDelta < 0 ? "negative" : ""}"><b>${carbonDelta >= 0 ? "+" : ""}${formatCompact(carbonDelta)}</b> t carbon</span>
      <span class="delta ${nativeDelta < 0 ? "negative" : ""}"><b>${nativeDelta >= 0 ? "+" : ""}${nativeDelta.toFixed(0)}%</b> native</span>`;
    updateExportButtons();
    await renderComparison();
    setStatus("live");
    toast(`Projected ${result.years} years in ${result.timeline.length - 1} annual steps.`);
  } catch (error) {
    setStatus("error", true);
    toast(error.message, true);
  }
}

function showBaseline() {
  state.result = null;
  state.scene = state.scene;
  api("/api/scene").then((scene) => {
    state.scene = scene;
    state.treeById = new Map(scene.trees.map((tree) => [tree.id, tree]));
    updateMapTrees();
    rebuildThreeTrees(scene.trees);
    renderKPIs(state.dataset.metrics);
    renderBaselineTimeline(state.dataset.metrics);
    renderComposition(state.dataset.metrics);
    renderSize(state.dataset.metrics);
  });
  $("scenario-revision").textContent = "baseline";
}

function updateMapTrees() {
  if (state.map && state.map.getSource("trees") && state.scene) {
    state.map.getSource("trees").setData(treesToFeatureCollection(state.scene.trees));
    updateMapSelection();
  }
}

async function loadScenario(scenarioId) {
  try {
    const scenario = await api(`/api/scenarios/${scenarioId}`);
    state.scenarioId = scenario.scenario_id;
    state.revision = scenario.revision;
    state.edits = scenario.edits || [];
    state.sentEditCount = state.edits.length;
    state.years = scenario.years;
    $("scenario-name").value = scenario.name;
    $("scenario-select").value = scenario.scenario_id;
    $("scenario-years").value = String(scenario.years);
    $("scenario-years-value").textContent = `${scenario.years} years`;
    $("scenario-revision").textContent = `revision ${scenario.revision}`;
    renderEditList();
    await previewScenario();
  } catch (error) {
    toast(error.message, true);
  }
}

async function refreshScenarioOptions() {
  const payload = await api("/api/scenarios");
  state.scenarios = payload.scenarios || [];
  renderScenarioOptions();
}

function renderScenarioOptions() {
  const select = $("scenario-select");
  const current = state.scenarioId;
  select.innerHTML = '<option value="">Baseline</option>';
  for (const scenario of state.scenarios) {
    const option = document.createElement("option");
    option.value = scenario.scenario_id;
    option.textContent = `${scenario.name} (${scenario.years}y)${scenario.score != null ? ` · ${scenario.score}` : ""}`;
    select.appendChild(option);
  }
  select.value = current;
}

async function recommendPlanting(center = null) {
  try {
    const count = Number($("plant-count").value || 40);
    const budget = Number($("plant-budget").value || 0);
    const radius = Number($("plant-radius").value || 250);
    const payload = await api("/api/dss/recommend", {
      method: "POST",
      body: JSON.stringify({
        count,
        species: $("plant-species").value,
        common_name: $("plant-species").value,
        budget_cad: budget || null,
        center_lon: center ? center[0] : null,
        center_lat: center ? center[1] : null,
        radius_m: center ? radius : null,
      }),
    });
    state.recommendations = payload.edits || [];
    const list = $("recommend-list");
    list.innerHTML = (payload.candidates || [])
      .slice(0, 8)
      .map(
        (candidate, index) => `
          <div class="edit-item">
            <span><span class="edit-kind plant">${index + 1}</span> ${candidate.reasons[0]}</span>
            <code>${candidate.score.toFixed(2)}</code>
          </div>`
      )
      .join("");
    $("apply-recommend").disabled = !state.recommendations.length;
    renderRecommendationCandidates(payload.candidates || []);
    setMode(null);
    toast(
      center
        ? `${payload.candidates.length} sites ranked within ${radius} m. ${payload.edits.length} fit the budget.`
        : `${payload.candidates.length} sites ranked. ${payload.edits.length} fit the budget.`
    );
  } catch (error) {
    toast(error.message, true);
  }
}

function renderRecommendationCandidates(candidates) {
  if (!state.map) return;
  const features = candidates.map((candidate, index) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [candidate.lon, candidate.lat] },
    properties: { rank: index + 1, score: candidate.score },
  }));
  const collection = { type: "FeatureCollection", features };
  if (state.map.getSource("recommendations")) {
    state.map.getSource("recommendations").setData(collection);
  } else {
    state.map.addSource("recommendations", { type: "geojson", data: collection });
    state.map.addLayer({
      id: "recommendations",
      type: "circle",
      source: "recommendations",
      paint: {
        "circle-color": "#c98933",
        "circle-radius": 7,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2,
      },
    });
  }
}

function applyRecommendations() {
  if (!state.recommendations.length) return;
  state.edits.push(...state.recommendations);
  state.recommendations = [];
  $("recommend-list").innerHTML = "";
  $("apply-recommend").disabled = true;
  renderEditList();
  toast("Recommendations added to the scenario.");
}

function resetCamera() {
  if (!state.three) return;
  state.three.camera.position.set(240, 170, 280);
  state.three.controls.target.set(0, 14, 0);
  state.three.controls.update();
}

async function renderComparison() {
  const container = $("comparison-list");
  try {
    const payload = await api("api/scenario-comparison");
    const rows = payload.scenarios || [];
    if (!rows.length) {
      container.innerHTML = '<p class="muted">No scenarios yet.</p>';
      return;
    }
    const best = rows[0];
    container.innerHTML = rows
      .map(
        (row) => `
        <div class="comparison-card ${row.scenario_id === best.scenario_id ? "best" : ""}">
          <div>
            <strong>${escapeHtml(row.name)}</strong><br>
            <span class="muted">${row.years} years · ${row.edits} edits · ${formatCompact(row.final_cover_pct, "%")} cover · ${formatCompact(row.final_volume_m3)} m³</span>
          </div>
          <div><strong>${Number(row.score).toFixed(1)}</strong><br><span class="muted">score</span></div>
        </div>`
      )
      .join("");
  } catch (error) {
    container.innerHTML = '<p class="muted">Comparison unavailable.</p>';
  }
}

function updateHud() {
  const hint = $("map-hint");
  if (!hint) return;
  hint.textContent = "Click a tree to inspect it, or use Plant mode.";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

init();
