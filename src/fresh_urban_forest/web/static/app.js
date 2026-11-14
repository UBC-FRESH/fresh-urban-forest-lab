import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const PARETO_VIEW_STORAGE_KEY = "fresh.pareto.views.v1";
const SITE_SCENARIO_STORAGE_KEY = "fresh.site-scenarios.v1";
const SITE_SCENARIO_LIBRARY_VERSION = 1;
const SITE_SCENARIO_LIMIT = 20;
const SITE_SCENARIO_IMPORT_LIMIT = 250_000;
const PARETO_VIEW_VERSION = 1;
const PARETO_VIEW_LIMIT = 50;
const PARETO_VIEW_IMPORT_LIMIT = 250_000;

const state = {
  dataset: null,
  scene: null,
  scene3d: null,
  roads: null,
  mapTrees: null,
  mapBuildings: null,
  offInventory: null,
  offInventoryValue: null,
  offInventory3D: null,
  offInventory3DLoading: false,
  classifier: null,
  imageryClassifier: null,
  imageryFusion: null,
  birds: null,
  birdsLoading: false,
  treeById: new Map(),
  scenarios: [],
  scenarioId: "",
  edits: [],
  sentEditCount: 0,
  revision: 0,
  years: 25,
  mode: null,
  selectedId: "",
  selectedCandidateId: "",
  recommendations: [],
  map: null,
  selectedSourceReady: false,
  three: null,
  result: null,
  assistant: { enabled: false, available: false, busy: false, session: null },
  changeMap: null,
  changeData: null,
  cityMetrics: null,
  heatPriority: null,
  plantingOpportunity: null,
  heatEquity: null,
  canopyChange: null,
  canopyAction: null,
  canopyActionVersion: "original",
  canopyTurnover: null,
  canopyTurnoverVersion: "original",
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
  siteScenario: {
    map: null,
    candidates: new Map(),
    selected: new Set(),
    evaluation: null,
    scenario: null,
    loading: false,
    busy: false,
    candidatesSchema: "",
    savedName: null,
  },
  optimize: {
    jobId: null,
    result: null,
    selected: null,
    reference: null,
    chart: null,
    mesh: null,
    pollTimer: null,
    filtered: [],
    savedRuns: [],
    pinned: [],
    brushes: [],
    parallelAxes: [],
    parallelDrag: null,
    parallelPointerId: null,
    presetName: null,
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

function candidateSpeciesScreening() {
  // Only the Vancouver instance has an accepted candidate-species screening model.
  // Surrey, Burnaby, and Coquitlam have no candidate-species validation, so they use
  // confidence-only styling and do not show species-group counts.
  return state.dataset?.dataset_id === "vancouver-city-2022";
}

function offInventoryFeatures() {
  const candidates = state.offInventory?.candidates || [];
  return {
    type: "FeatureCollection",
    features: candidates.map((candidate) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [candidate.lon, candidate.lat] },
      properties: {
        candidate_id: candidate.candidate_id,
        confidence: candidate.confidence,
        height_m: candidate.height_m,
        land_class: candidate.land_class,
      },
    })),
  };
}

function renderOffInventory() {
  const container = $("off-inventory-summary");
  if (!container) return;
  const data = state.offInventory;
  if (!data) {
    $("off-inventory-status").textContent = "none";
    container.innerHTML = '<p class="muted">No off-inventory layer in this dataset.</p>';
    return;
  }
  const high = Number(
    data.high_confidence_count ??
      (data.candidates || []).filter((candidate) => Number(candidate.confidence) >= 0.6).length,
  );
  const areaHa = Number(data.candidate_area_m2 || 0) / 10000;
  const speciesScreening = candidateSpeciesScreening();
  container.dataset.candidateSpecies = speciesScreening ? "screening" : "unvalidated";
  const value = state.offInventoryValue;
  const volumeDelta = value ? Number(value.augmented_canopy_volume_m3 || 0) - Number(value.official_canopy_volume_m3 || 0) : 0;
  const carbonDelta = value ? Number(value.augmented_carbon_kg || 0) - Number(value.official_carbon_kg || 0) : 0;
  const voi = value
    ? `<div class="off-inventory-voi"><span>Plan change</span><strong>${(1 - Number(value.plan_jaccard || 1)).toFixed(2)}</strong><small>${formatNumber(value.changed_sites)} sites differ · +${formatCompact(volumeDelta, " m³")} canopy · +${formatCompact(carbonDelta / 1000, " t")} carbon</small></div>`
    : "";
  container.innerHTML = `
    <div class="kpi-grid">
      <article class="kpi"><span>Candidates</span><strong>${formatNumber(data.candidate_count)}</strong><small>unmatched crowns</small></article>
      <article class="kpi"><span>High confidence</span><strong>${formatNumber(high)}</strong><small>score >= 0.6</small></article>
      <article class="kpi"><span>Crown area</span><strong>${formatNumber(areaHa, 1)} ha</strong><small>summed, not unique</small></article>
      <article class="kpi"><span>Detected</span><strong>${formatNumber(data.detected_count)}</strong><small>${formatNumber(data.matched_count)} matched</small></article>
    </div>
    ${voi}
    ${
      data.imagery
        ? `<p class="hint">Image scoring: ${formatNumber(data.imagery.scored_count)} candidates · ${escapeHtml(data.imagery.source)} · ${
            speciesScreening
              ? `mapped groups ${formatNumber(data.imagery.groups.conifer)} conifer / ${formatNumber(data.imagery.groups.deciduous)} deciduous.`
              : "species groups are not validated for this dataset; candidate colors show confidence only."
          } ${escapeHtml(data.imagery.caveat || "")}</p>`
        : ""
    }`;
  $("off-inventory-status").textContent = data.evidence?.tier || "pilot";
  renderClassifierQA();
}

function renderClassifierQA() {
  const container = $("classifier-qa");
  if (!container) return;
  const report = state.classifier;
  const imagery = state.imageryClassifier;
  if (!report && !imagery) {
    container.innerHTML = "";
    return;
  }
  const evaluation = report?.evaluation || {};
  const matrix = Array.isArray(evaluation.matrix) ? evaluation.matrix : [];
  const conifer = evaluation.conifer || {};
  const deciduous = evaluation.deciduous || {};
  const labels = report?.known_good_labels || {};
  const weak = report?.weak_label_agreement || {};
  const cityRows = Object.entries(report?.by_city || {})
    .map(
      ([city, value]) =>
        `<tr><td>${escapeHtml(city)}</td><td>${formatNumber(value.n)}</td><td>${formatNumber(Number(value.accuracy) * 100, 1)}%</td></tr>`,
    )
    .join("");
  const weakRows = Object.entries(weak)
    .map(
      ([slug, value]) =>
        `<tr><td>${escapeHtml(slug.replace(/_[0-9]{4}$/, ""))}</td><td>${formatNumber(value.n)}</td><td>${formatNumber(Number(value.accuracy) * 100, 1)}%</td></tr>`,
    )
    .join("");
  const ci = Array.isArray(evaluation.accuracy_ci95)
    ? evaluation.accuracy_ci95.map((value) => `${formatNumber(Number(value) * 100, 1)}%`).join("–")
    : "n/a";
  const structural = `
    <details class="qa-details" ${imagery ? "" : "open"}>
      <summary>Structural baseline · P35</summary>
      <p class="hint">Inventory-derived height/crown features. This is the weaker baseline and is not the image/fusion model.</p>
      <table class="qa-matrix">
        <thead><tr><th></th><th>pred conifer</th><th>pred deciduous</th></tr></thead>
        <tbody>
          <tr><th>conifer</th><td>${formatNumber(matrix[0]?.[0] || 0)}</td><td>${formatNumber(matrix[0]?.[1] || 0)}</td></tr>
          <tr><th>deciduous</th><td>${formatNumber(matrix[1]?.[0] || 0)}</td><td>${formatNumber(matrix[1]?.[1] || 0)}</td></tr>
        </tbody>
      </table>
      <div class="qa-stats">
        <span><b>${formatNumber(Number(evaluation.accuracy) * 100, 1)}%</b><small>accuracy · 95% ${ci}</small></span>
        <span><b>${formatNumber(Number(conifer.precision) * 100, 1)}%</b><small>conifer precision</small></span>
        <span><b>${formatNumber(Number(conifer.recall) * 100, 1)}%</b><small>conifer recall</small></span>
        <span><b>${formatNumber(Number(deciduous.precision) * 100, 1)}%</b><small>deciduous precision</small></span>
      </div>
      <table class="qa-table">
        <thead><tr><th>held-out city</th><th>n</th><th>acc.</th></tr></thead>
        <tbody>${cityRows || '<tr><td colspan="3" class="muted">No city table.</td></tr>'}</tbody>
      </table>
      <p class="hint">Known-good: ${escapeHtml((labels.available_cities || []).join(", ") || "none")}. Unavailable: ${escapeHtml((labels.unavailable_cities || []).join(", ") || "none")}. ${formatNumber(report?.training?.spatial_block_m || 0)} m blocks; test n=${formatNumber(report?.training?.test_rows || 0)}.</p>
      <details class="qa-details">
        <summary>Weak-label diagnostic (not accuracy)</summary>
        <table class="qa-table">
          <thead><tr><th>city</th><th>n</th><th>agreement</th></tr></thead>
          <tbody>${weakRows || '<tr><td colspan="3" class="muted">No weak-label table.</td></tr>'}</tbody>
        </table>
        <p class="hint">Metro LCC agreement is weak-label context, not known-good species truth.</p>
      </details>
    </details>`;
  container.innerHTML = imagery ? imageryPrimaryHtml() : structural;
}

function imageryPrimaryHtml() {
  const report = state.imageryClassifier;
  if (!report) return "";
  const imageEvaluation = report.evaluation || {};
  const fusion = state.imageryFusion?.fused_model?.evaluation || null;
  const evaluation = fusion || imageEvaluation;
  const matrix = Array.isArray(evaluation.matrix) ? evaluation.matrix : [];
  const conifer = evaluation.conifer || {};
  const training = report.training || {};
  const title = fusion ? "Image + LiDAR fusion · Vancouver 2022" : "Image CNN · Vancouver 2022";
  return `
    <details class="qa-details" open>
      <summary>${title}</summary>
      <p class="hint">96 px RGB orthophoto chips; ${formatNumber(training.test_rows || 0)} spatial test chips. This is the primary model.</p>
      <table class="qa-matrix">
        <thead><tr><th></th><th>pred conifer</th><th>pred deciduous</th></tr></thead>
        <tbody>
          <tr><th>conifer</th><td>${formatNumber(matrix[0]?.[0] || 0)}</td><td>${formatNumber(matrix[0]?.[1] || 0)}</td></tr>
          <tr><th>deciduous</th><td>${formatNumber(matrix[1]?.[0] || 0)}</td><td>${formatNumber(matrix[1]?.[1] || 0)}</td></tr>
        </tbody>
      </table>
      <div class="qa-stats">
        <span><b>${formatNumber(Number(evaluation.accuracy) * 100, 1)}%</b><small>${fusion ? "fused" : "image"} accuracy</small></span>
        <span><b>${formatNumber(Number(conifer.precision) * 100, 1)}%</b><small>conifer precision</small></span>
        <span><b>${formatNumber(Number(conifer.recall) * 100, 1)}%</b><small>conifer recall</small></span>
        <span><b>${formatNumber(Number(imageEvaluation.brier_score) * 100, 1)}</b><small>image Brier ×100</small></span>
      </div>
      <p class="hint">${fusion ? "Fusion uses independent CHM crown-shape features plus image probability." : "Image-only result; no fusion report loaded."}</p>
    </details>`;
}

function imageryClassifierHtml() {
  return imageryPrimaryHtml();
}

function buildingFeatures() {
  if (state.mapBuildings && Array.isArray(state.mapBuildings.features)) {
    return state.mapBuildings;
  }
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

function loadFullMapLayers() {
  if (!state.dataset?.has_map_trees && !state.dataset?.has_map_buildings) return;
  const apply = () => {
    if (state.dataset.has_map_trees) {
      const trees = state.map?.getSource("trees");
      if (trees) trees.setData("api/map-trees");
    }
    if (state.dataset.has_map_buildings) {
      const buildings = state.map?.getSource("buildings");
      if (buildings) buildings.setData("api/map-buildings");
    }
  };
  if (!state.map) return;
  if (state.map.isStyleLoaded()) apply();
  else state.map.once("load", apply);
}

function renderCityMetrics() {
  const data = state.cityMetrics;
  if (!data) return;
  const tab = document.querySelector('.tab[data-view="city"]');
  if (tab) tab.hidden = false;
  const city = data.city || {};
  const local = Array.isArray(data.local_areas) ? data.local_areas : [];
  const metrics = state.dataset?.metrics || {};
  const visualTrees = state.scene?.trees?.length || 0;
  const cards = [
    ["Canopy cover", `${formatNumber(city.canopy_cover_pct, 1)}%`, "of city area"],
    ["Canopy volume", `${formatCompact(city.canopy_volume_m3)} m³`, city.canopy_source_label || "LiDAR height field"],
    ["Carbon storage", `${formatCompact(Number(city.carbon_kg) / 1000)} t`, "above ground"],
    ["Annual sequestration", `${formatCompact(Number(city.annual_sequestration_kg) / 1000)} t/yr`, "one-year model"],
    ["Rainfall interception", `${formatCompact(city.rainfall_interception_m3_low)}–${formatCompact(city.rainfall_interception_m3_high)} m³`, "10–20% screening"],
    [city.tree_record_label || "Tree records", formatNumber(city.tree_count), "compiled records"],
    ["Species", formatNumber(metrics.species_count), "distinct labels"],
    ["Native share", `${formatNumber(Number(city.native_fraction) * 100, 1)}%`, "of public trees"],
  ];
  if (data.shade?.metrics) {
    cards.push([
      "Tree shade",
      `${formatNumber(Number(data.shade.metrics.tree_shade_fraction) * 100, 1)}%`,
      "representative day",
    ]);
  }
  $("city-kpis").innerHTML = cards
    .map(
      ([label, value, note]) =>
        `<article class="kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`,
    )
    .join("");
  const maxCover = Math.max(...local.map((area) => Number(area.canopy_cover_pct) || 0), 1);
  const rows = [...local]
    .sort((a, b) => Number(b.canopy_cover_pct) - Number(a.canopy_cover_pct))
    .map((area) => {
      const width = Math.max(2, (Number(area.canopy_cover_pct) / maxCover) * 100);
      return `<div class="city-row">
        <span class="name">${escapeHtml(area.name)}</span>
        <span class="num">${formatNumber(area.canopy_cover_pct, 1)}%</span>
        <span class="bar"><span style="width:${width.toFixed(1)}%"></span></span>
        <span class="num hide-small">${formatCompact(Number(area.carbon_kg) / 1000)} t</span>
        <span class="num">${formatNumber(area.tree_count)}</span>
      </div>`;
    })
    .join("");
  const head = `<div class="city-row city-head"><span>Local area</span><span class="num">Cover</span><span></span><span class="num hide-small">Carbon</span><span class="num">Trees</span></div>`;
  $("city-local-areas").innerHTML = rows ? head + rows : '<p class="muted">No local-area metrics.</p>';
  const methods = Object.entries(data.methods || {})
    .map(([key, method]) => {
      const tier = method?.tier || "method";
      return `<div class="city-method"><strong>${escapeHtml(key.replaceAll("_", " "))}</strong><span>${escapeHtml(method?.method || "")} · ${escapeHtml(tier)}</span></div>`;
    })
    .join("");
  const caveats = (data.caveats || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const validation = data.validation
    ? `<div class="city-method"><strong>published canopy-cover check</strong><span>City estimate ${formatNumber(data.validation.published_canopy_cover_pct, 1)}% vs this pilot ${formatNumber(city.canopy_cover_pct, 1)}% · sanity check, not calibration</span></div>`
    : "";
  const shade = data.shade
    ? `<div class="city-method"><strong>tree shade</strong><span>${escapeHtml(data.shade.method || "")} · ${escapeHtml(data.shade.tier || "screening")}</span></div>`
    : "";
  $("city-methods").innerHTML = `${methods}${shade}${validation}<ul class="city-caveats">${caveats}</ul>`;
  $("city-source").textContent = `${formatNumber(city.tree_count)} public trees · ${local.length} local areas · 2022 LiDAR · ${formatNumber(visualTrees)} visual trees`;
}

async function loadCanopyActionVersion(version) {
  state.canopyActionVersion = version;
  try {
    const [payload, geojson] = await Promise.all([
      api(`api/canopy-action?version=${encodeURIComponent(version)}`),
      api(`api/canopy-action.geojson?version=${encodeURIComponent(version)}`),
    ]);
    state.canopyAction = payload;
    renderCanopyAction();
    if (state.map?.getSource("canopyAction")) state.map.getSource("canopyAction").setData(geojson);
  } catch (_error) {
    state.canopyAction = null;
    renderCanopyAction();
  }
}

async function loadCanopyTurnoverVersion(version) {
  state.canopyTurnoverVersion = version;
  try {
    const [payload, geojson] = await Promise.all([
      api(`api/canopy-turnover?version=${encodeURIComponent(version)}`),
      api(`api/canopy-turnover.geojson?version=${encodeURIComponent(version)}`),
    ]);
    state.canopyTurnover = payload;
    renderCanopyTurnover();
    if (state.map?.getSource("canopyTurnover")) state.map.getSource("canopyTurnover").setData(geojson);
  } catch (_error) {
    state.canopyTurnover = null;
    renderCanopyTurnover();
  }
}

function renderCanopyTurnover() {
  const data = state.canopyTurnover;
  const status = $("canopy-turnover-status");
  if (!data) {
    status.textContent = "none";
    $("canopy-turnover-summary").innerHTML =
      '<p class="muted">No turnover product in this dataset.</p>';
    return;
  }
  const cells = data.cells || [];
  const counts = {};
  let gainPatches = 0;
  let lossPatches = 0;
  let turnover = 0;
  let largest = 0;
  for (const cell of cells) {
    const tier = cell.turnover_tier || "none";
    counts[tier] = (counts[tier] || 0) + 1;
    gainPatches += Number(cell.gain_patch_count || 0);
    lossPatches += Number(cell.loss_patch_count || 0);
    turnover += Number(cell.turnover_area_m2 || 0);
    largest = Math.max(largest, Number(cell.largest_gain_patch_m2 || 0), Number(cell.largest_loss_patch_m2 || 0));
  }
  $("canopy-turnover-summary").innerHTML = `
    <div class="city-kpis" style="grid-template-columns:repeat(2,minmax(0,1fr));margin:0 0 10px">
      <div class="kpi"><span>high turnover cells</span><strong>${formatNumber(counts.high || 0)}</strong><small>of ${formatNumber(cells.length)} cells</small></div>
      <div class="kpi"><span>turnover area</span><strong>${formatCompact(turnover / 10000, " ha")}</strong><small>${formatNumber(gainPatches)} gain · ${formatNumber(lossPatches)} loss patches</small></div>
    </div>
    <div class="city-method"><strong>largest patch</strong><span>${formatCompact(largest / 10000, " ha")} · 2 m patches ≥50 m²</span></div>
    <p class="muted" style="font-size:.68rem;margin-top:8px">Turnover screen, not net gain/loss or tree survival.</p>
  `;
  status.textContent = state.canopyTurnoverVersion === "control" ? "full-control" : "original";
}

function renderCanopyAction() {
  const data = state.canopyAction;
  const status = $("canopy-action-status");
  if (!data) {
    status.textContent = "none";
    $("canopy-action-summary").innerHTML =
      '<p class="muted">No integrated action screen in this dataset.</p>';
    return;
  }
  const cells = data.cells || [];
  const counts = {};
  for (const cell of cells) {
    const key = cell.action_class || "none";
    counts[key] = (counts[key] || 0) + 1;
  }
  const rows = [
    ["plant_cool", "plant + cool"],
    ["structural_shade", "structural shade"],
    ["expand_canopy", "expand canopy"],
    ["protect_loss", "protect loss"],
    ["monitor", "monitor"],
  ]
    .map(
      ([key, label]) =>
        `<div class="city-row"><span class="name">${label}</span><span class="num">${formatNumber(counts[key] || 0)}</span><span class="num">${formatNumber((100 * (counts[key] || 0)) / Math.max(cells.length, 1), 1)}%</span></div>`,
    )
    .join("");
  const observed = cells.filter((cell) => cell.change_observed).length;
  $("canopy-action-summary").innerHTML = `
    <div class="city-kpis" style="grid-template-columns:repeat(2,minmax(0,1fr));margin:0 0 10px">
      <div class="kpi"><span>action cells</span><strong>${formatNumber(cells.length)}</strong><small>joined P38–P40</small></div>
      <div class="kpi"><span>change observed</span><strong>${formatNumber(observed)}</strong><small>P43 citywide change</small></div>
    </div>
    <div class="city-table">${rows}</div>
    <p class="muted" style="font-size:.68rem;margin-top:8px">Screening rule, not a planting plan or causal forecast.</p>
  `;
  status.textContent = state.canopyActionVersion === "control" ? "full-control" : "original";
}

function renderCanopyChange() {
  const data = state.canopyChange;
  const status = $("canopy-change-status");
  if (!data) {
    status.textContent = "none";
    $("canopy-change-summary").innerHTML =
      '<p class="muted">No observed-change product in this dataset.</p>';
    return;
  }
  const cells = data.cells || [];
  const counts = {};
  let gain = 0;
  let loss = 0;
  let net = 0;
  let stable = 0;
  for (const cell of cells) {
    const key = cell.change_class || "none";
    counts[key] = (counts[key] || 0) + 1;
    gain += Number(cell.gain_m2 || 0);
    loss += Number(cell.loss_m2 || 0);
    net += Number(cell.net_m2 || 0);
    stable += Number(cell.stable_m2 || 0);
  }
  const netSign = net >= 0 ? "+" : "";
  $("canopy-change-summary").innerHTML = `
    <div class="city-kpis" style="grid-template-columns:repeat(2,minmax(0,1fr));margin:0 0 10px">
      <div class="kpi"><span>net canopy</span><strong>${netSign}${formatCompact(net / 10000, " ha")}</strong><small>${formatNumber(cells.length)} cells</small></div>
      <div class="kpi"><span>gain / loss</span><strong>${formatCompact(gain / 10000, " ha")}</strong><small>${formatCompact(loss / 10000, " ha")} loss</small></div>
    </div>
    <div class="city-method"><strong>stable canopy</strong><span>${formatCompact(stable / 10000, " ha")} unchanged at the 2 m threshold</span></div>
    <div class="city-method"><strong>method</strong><span>${escapeHtml(data.metadata?.earlier_label || "2018")} → ${escapeHtml(data.metadata?.later_label || "2022")} · thresholded LiDAR change</span></div>
    <p class="muted" style="font-size:.68rem;margin-top:8px">Citywide 2 m surface comparison · not tree survival or causal attribution</p>
  `;
  status.textContent = "screening";
}

function renderHeatEquity() {
  const data = state.heatEquity;
  const status = $("heat-equity-status");
  if (!data) {
    status.textContent = "none";
    $("heat-equity-summary").innerHTML =
      '<p class="muted">No Landsat heat-equity product in this dataset.</p>';
    return;
  }
  const cells = data.cells || [];
  const counts = {};
  let lstSum = 0;
  let lstCount = 0;
  let hottest = null;
  let high = 0;
  for (const cell of cells) {
    const tier = cell.heat_equity_tier || "none";
    counts[tier] = (counts[tier] || 0) + 1;
    if (tier === "high") high += 1;
    if (Number.isFinite(Number(cell.lst_mean_c))) {
      lstSum += Number(cell.lst_mean_c);
      lstCount += 1;
      if (!hottest || Number(cell.lst_mean_c) > Number(hottest.lst_mean_c)) hottest = cell;
    }
  }
  const mean = lstCount ? lstSum / lstCount : 0;
  const hottestText = hottest
    ? `${formatNumber(hottest.lst_mean_c, 1)} °C at ${escapeHtml(hottest.cell_id)}`
    : "no valid LST";
  $("heat-equity-summary").innerHTML = `
    <div class="city-kpis" style="grid-template-columns:repeat(2,minmax(0,1fr));margin:0 0 10px">
      <div class="kpi"><span>mean surface temperature</span><strong>${formatNumber(mean, 1)} °C</strong><small>Landsat summer composite</small></div>
      <div class="kpi"><span>high heat-equity cells</span><strong>${formatNumber(high)}</strong><small>of ${formatNumber(cells.length)} cells</small></div>
    </div>
    <div class="city-method"><strong>hottest cell</strong><span>${hottestText} · LST, not air temperature</span></div>
    <div class="city-method"><strong>index</strong><span>1/5 Landsat LST + 4/5 P38 Census equity · relative screen</span></div>
    <p class="muted" style="font-size:.68rem;margin-top:8px">${formatNumber(data.metadata?.scene_dates?.length || 0)} Landsat scenes · ${escapeHtml(data.metadata?.lst_resolution_m || 30)} m LST</p>
  `;
  status.textContent = "screening";
}

function renderPlantingOpportunity() {
  const data = state.plantingOpportunity;
  const status = $("planting-opportunity-status");
  if (!data) {
    status.textContent = "none";
    $("planting-opportunity-summary").innerHTML =
      '<p class="muted">No canopy-gap product in this dataset.</p>';
    return;
  }
  const cells = data.cells || [];
  const counts = {};
  let gap = 0;
  let street = 0;
  let sites = 0;
  let streetSites = 0;
  let capacity = 0;
  for (const cell of cells) {
    counts[cell.opportunity_tier] = (counts[cell.opportunity_tier] || 0) + 1;
    gap += Number(cell.gap_m2 || 0);
    street += Number(cell.street_gap_m2 || 0);
    sites += Number(cell.gap_sites || 0);
    streetSites += Number(cell.street_gap_sites || 0);
    capacity += Number(cell.capacity_small_upper || 0);
  }
  $("planting-opportunity-summary").innerHTML = `
    <div class="city-kpis" style="grid-template-columns:repeat(2,minmax(0,1fr));margin:0 0 10px">
      <div class="kpi"><span>canopy-gap area</span><strong>${formatCompact(gap / 10000, " ha")}</strong><small>${formatCompact(street / 10000, " ha")} street-adjacent</small></div>
      <div class="kpi"><span>contiguous sites</span><strong>${formatNumber(sites)}</strong><small>${formatNumber(streetSites)} street-adjacent</small></div>
    </div>
    <div class="city-method"><strong>gross small-crown slots</strong><span>${formatCompact(capacity)} upper bound if every square metre were available · not a tree count</span></div>
    <div class="city-method"><strong>high tier cells</strong><span>${formatNumber(counts.high || 0)} of ${formatNumber(cells.length)} cells</span></div>
    <p class="muted" style="font-size:.68rem;margin-top:8px">P38 shade deficit and Census equity are used in the relative score.</p>
  `;
  status.textContent = "screening";
}

function renderHeatPriority() {
  const data = state.heatPriority;
  const status = $("heat-priority-status");
  if (!data) {
    status.textContent = "none";
    $("heat-priority-summary").innerHTML =
      '<p class="muted">No shade-equity product in this dataset.</p>';
    return;
  }
  const cells = data.cells || [];
  const counts = {};
  let winWin = 0;
  let shadeSum = 0;
  let equitySum = 0;
  let scored = 0;
  for (const cell of cells) {
    const key = cell.priority_class || "NA";
    counts[key] = (counts[key] || 0) + 1;
    if (key === "1A" || key === "1B") winWin += 1;
    if (Number.isFinite(Number(cell.shade_fraction))) {
      shadeSum += Number(cell.shade_fraction);
      equitySum += Number(cell.equity_score || 0);
      scored += 1;
    }
  }
  const reportedShade = Number(data.metadata?.shade?.metrics?.combined_shade_fraction);
  const shade = Number.isFinite(reportedShade) ? reportedShade : scored ? shadeSum / scored : 0;
  const equity = scored ? equitySum / scored : 0;
  const classRows = Object.entries(counts)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(
      ([key, count]) =>
        `<div class="city-row"><span class="name">class ${escapeHtml(key)}</span><span class="num">${formatNumber(count)}</span><span class="num">${formatNumber((100 * count) / Math.max(cells.length, 1), 1)}%</span></div>`,
    )
    .join("");
  const methods = data.metadata?.methods || {};
  const shadeMethod = methods.shade?.method || "raster-dsm-solar-shadow";
  const priorityMethod = methods.priority?.method || "median-split-screen";
  $("heat-priority-summary").innerHTML = `
    <div class="city-kpis" style="grid-template-columns:repeat(2,minmax(0,1fr));margin:0 0 10px">
      <div class="kpi"><span>mean shade</span><strong>${formatNumber(shade * 100, 1)}%</strong><small>${formatNumber(cells.length)} cells</small></div>
      <div class="kpi"><span>win-win cells</span><strong>${formatNumber(winWin)}</strong><small>high deficit + high equity</small></div>
    </div>
    <div class="city-table">${classRows}</div>
    <div class="city-method"><strong>shade</strong><span>${escapeHtml(shadeMethod)} · screening</span></div>
    <div class="city-method"><strong>priority</strong><span>${escapeHtml(priorityMethod)} · relative within city</span></div>
    <p class="muted" style="font-size:.68rem;margin-top:8px">Mean equity score ${formatNumber(equity, 2)} · 2021 Census DA screen</p>
  `;
  status.textContent = "screening";
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
    updateSiteTabVisibility(Boolean(dataset.has_site_candidates));
    updateLayerToggleAvailability(dataset);
    if (dataset.has_roads) {
      try {
        state.roads = await api("api/roads");
      } catch (_error) {
        state.roads = null;
      }
    }
    if (dataset.has_full_scene) {
      try {
        state.scene3d = await api("api/full-scene");
      } catch (_error) {
        state.scene3d = null;
      }
    }
    state.scenarios = scenarios.scenarios || [];
    state.treeById = new Map(scene.trees.map((tree) => [tree.id, tree]));
    if (dataset.has_off_inventory) {
      try {
        state.offInventory = await api("api/off-inventory");
        renderOffInventory();
        if (dataset.has_off_inventory_value) {
          try {
            state.offInventoryValue = await api("api/off-inventory/value");
            renderOffInventory();
          } catch (_error) {
            // The value-of-information file is optional.
          }
        }
      } catch (_error) {
        state.offInventory = null;
        renderOffInventory();
      }
    } else {
      state.offInventory = null;
      renderOffInventory();
    }
    if (dataset.has_classifier) {
      try {
        state.classifier = await api("api/classifier");
        renderClassifierQA();
      } catch (_error) {
        state.classifier = null;
      }
    }
    if (dataset.has_imagery_classifier) {
      try {
        state.imageryClassifier = await api("api/imagery-classifier");
        renderClassifierQA();
      } catch (_error) {
        state.imageryClassifier = null;
      }
    }
    if (dataset.has_imagery_fusion) {
      try {
        state.imageryFusion = await api("api/imagery-fusion");
        renderClassifierQA();
      } catch (_error) {
        state.imageryFusion = null;
      }
    }
    if (dataset.has_city_metrics) {
      try {
        state.cityMetrics = await api("api/city-metrics");
        renderCityMetrics();
      } catch (_error) {
        state.cityMetrics = null;
      }
    }
    if (dataset.has_heat_priority) {
      try {
        state.heatPriority = await api("api/heat-priority");
        renderHeatPriority();
      } catch (_error) {
        state.heatPriority = null;
        renderHeatPriority();
      }
    }
    if (dataset.has_planting_opportunity) {
      try {
        state.plantingOpportunity = await api("api/planting-opportunity");
        renderPlantingOpportunity();
      } catch (_error) {
        state.plantingOpportunity = null;
        renderPlantingOpportunity();
      }
    }
    if (dataset.has_heat_equity) {
      try {
        state.heatEquity = await api("api/heat-equity");
        renderHeatEquity();
      } catch (_error) {
        state.heatEquity = null;
        renderHeatEquity();
      }
    }
    if (dataset.has_canopy_change) {
      try {
        state.canopyChange = await api("api/canopy-change");
        renderCanopyChange();
      } catch (_error) {
        state.canopyChange = null;
        renderCanopyChange();
      }
    }
    if (dataset.has_canopy_action) {
      state.canopyActionVersion = dataset.has_canopy_action_control ? "control" : "original";
      $("canopy-action-version").value = state.canopyActionVersion;
      $("canopy-action-version").querySelector('option[value="control"]').disabled =
        !dataset.has_canopy_action_control;
      await loadCanopyActionVersion(state.canopyActionVersion);
    }
    if (dataset.has_canopy_turnover) {
      state.canopyTurnoverVersion = dataset.has_canopy_turnover_control ? "control" : "original";
      $("canopy-turnover-version").value = state.canopyTurnoverVersion;
      $("canopy-turnover-version").querySelector('option[value="control"]').disabled =
        !dataset.has_canopy_turnover_control;
      await loadCanopyTurnoverVersion(state.canopyTurnoverVersion);
    }
    $("dataset-name").textContent = `${dataset.name} · ${dataset.tree_count.toLocaleString("en-CA")} tree records · ${dataset.sources.length} sources`;
    setStatus("live");
    renderKPIs(dataset.metrics);
    await loadCompleteness();
    renderComposition(dataset.metrics);
    renderSize(dataset.metrics);
    renderScenarioOptions();
    renderBaselineTimeline(dataset.metrics);
    initMap();
    loadFullMapLayers();
    bindControls();
    initLightControls();
    initOptimizeControls();
    initSiteControls();
    updateSunForTime();
    updateHud();
    window.__freshLab = {
      selectTree,
      switchView,
      loadLight,
      selectPareto: selectParetoByIndex,
      paretoScreenPositions,
      selectedSummary: () => ({
        id: state.optimize.selected?.solution_id || "",
        planted: state.optimize.selected?.planted?.length || 0,
        archive_first_planted: state.optimize.result?.archive?.solutions?.[0]?.planted?.length || 0,
      }),
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

function updateLayerToggleAvailability(dataset) {
  const layers = {
    "toggle-off-inventory": "has_off_inventory",
    "toggle-heat-priority": "has_heat_priority",
    "toggle-planting-opportunity": "has_planting_opportunity",
    "toggle-heat-equity": "has_heat_equity",
    "toggle-canopy-change": "has_canopy_change",
    "toggle-canopy-action": "has_canopy_action",
    "toggle-canopy-turnover": "has_canopy_turnover",
  };
  for (const [id, flag] of Object.entries(layers)) {
    const input = $(id);
    if (!input) continue;
    const available = Boolean(dataset[flag]);
    input.disabled = !available;
    const label = input.closest("label");
    if (label) label.hidden = !available;
  }
}

function initMap() {
  const [west, south, east, north] = state.scene.bounds_wgs84;
  const coordinates = state.scene.corners_wgs84 || [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ];
  const showCandidateSpecies = candidateSpeciesScreening();
  const map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        hillshade: { type: "image", url: "api/hillshade.png?width=1400", coordinates },
        canopy: { type: "image", url: "api/canopy.png?width=1400", coordinates },
        buildings: { type: "geojson", data: buildingFeatures() },
        heatPriority: {
          type: "geojson",
          data: state.dataset?.has_heat_priority
            ? "api/heat-priority.geojson"
            : { type: "FeatureCollection", features: [] },
        },
        plantingOpportunity: {
          type: "geojson",
          data: state.dataset?.has_planting_opportunity
            ? "api/planting-opportunity.geojson"
            : { type: "FeatureCollection", features: [] },
        },
        heatEquity: {
          type: "geojson",
          data: state.dataset?.has_heat_equity
            ? "api/heat-equity.geojson"
            : { type: "FeatureCollection", features: [] },
        },
        canopyChange: {
          type: "geojson",
          data: state.dataset?.has_canopy_change
            ? "api/canopy-change.geojson"
            : { type: "FeatureCollection", features: [] },
        },
        canopyAction: {
          type: "geojson",
          data: state.dataset?.has_canopy_action_control
            ? "api/canopy-action.geojson?version=control"
            : state.dataset?.has_canopy_action
              ? "api/canopy-action.geojson"
              : { type: "FeatureCollection", features: [] },
        },
        canopyTurnover: {
          type: "geojson",
          data: state.dataset?.has_canopy_turnover_control
            ? "api/canopy-turnover.geojson?version=control"
            : state.dataset?.has_canopy_turnover
              ? "api/canopy-turnover.geojson"
              : { type: "FeatureCollection", features: [] },
        },
        offInventory: {
          type: "geojson",
          data: state.dataset?.has_off_inventory
            ? "api/off-inventory.geojson"
            : offInventoryFeatures(),
        },
        boundary: { type: "geojson", data: boundaryFeatures() },
        roads: { type: "geojson", data: state.roads || { type: "FeatureCollection", features: [] } },
        trees: {
          type: "geojson",
          data: state.mapTrees || treesToFeatureCollection(state.scene.trees),
        },
        selected: { type: "geojson", data: selectedFeatures() },
      },
      layers: [
        { id: "background", type: "background", paint: { "background-color": "#e6eae2" } },
        {
          id: "hillshade",
          type: "raster",
          source: "hillshade",
          paint: { "raster-opacity": 0.38, "raster-resampling": "linear" },
        },
        {
          id: "canopy",
          type: "raster",
          source: "canopy",
          paint: { "raster-opacity": 0.58, "raster-resampling": "linear" },
        },
        {
          id: "roads-casing",
          type: "line",
          source: "roads",
          paint: {
            "line-color": "#ffffff",
            "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.8, 16, 2.8],
            "line-opacity": 0.55,
          },
        },
        {
          id: "roads",
          type: "line",
          source: "roads",
          paint: {
            "line-color": "#7b8479",
            "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.4, 16, 1.4],
            "line-opacity": 0.7,
          },
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
          id: "heat-priority",
          type: "fill",
          source: "heatPriority",
          layout: { visibility: "none" },
          paint: {
            "fill-color": [
              "match",
              ["get", "priority_class"],
              "1A", "#b22222",
              "1B", "#dc642d",
              "2A", "#d65db1",
              "2B", "#e8aaca",
              "3A", "#2f5597",
              "3B", "#5d91cc",
              "4A", "#626262",
              "4B", "#aaaaaa",
              "#000000",
            ],
            "fill-opacity": 0.52,
            "fill-outline-color": "rgba(255,255,255,0.45)",
          },
        },
        {
          id: "planting-opportunity",
          type: "fill",
          source: "plantingOpportunity",
          layout: { visibility: "none" },
          paint: {
            "fill-color": [
              "match",
              ["get", "opportunity_tier"],
              "high", "#ca4c18",
              "medium", "#f4a538",
              "low", "#9bbe78",
              "#000000",
            ],
            "fill-opacity": 0.48,
            "fill-outline-color": "rgba(255,255,255,0.35)",
          },
        },
        {
          id: "heat-equity",
          type: "fill",
          source: "heatEquity",
          layout: { visibility: "none" },
          paint: {
            "fill-color": [
              "match",
              ["get", "heat_equity_tier"],
              "high", "#b2182b",
              "medium", "#ef8a34",
              "low", "#4575b4",
              "#000000",
            ],
            "fill-opacity": 0.5,
            "fill-outline-color": "rgba(255,255,255,0.35)",
          },
        },
        {
          id: "canopy-change",
          type: "fill",
          source: "canopyChange",
          layout: { visibility: "none" },
          paint: {
            "fill-color": [
              "match",
              ["get", "change_class"],
              "gain", "#4d9221",
              "loss", "#c51b7d",
              "stable", "#5a5a5a",
              "no canopy", "#b4b4b4",
              "#000000",
            ],
            "fill-opacity": 0.5,
            "fill-outline-color": "rgba(255,255,255,0.35)",
          },
        },
        {
          id: "canopy-action",
          type: "fill",
          source: "canopyAction",
          layout: { visibility: "none" },
          paint: {
            "fill-color": [
              "match",
              ["get", "action_class"],
              "plant_cool", "#377e22",
              "structural_shade", "#3182bd",
              "expand_canopy", "#e6911e",
              "protect_loss", "#c51b7d",
              "monitor", "#8c8c8c",
              "#000000",
            ],
            "fill-opacity": 0.5,
            "fill-outline-color": "rgba(255,255,255,0.35)",
          },
        },
        {
          id: "canopy-turnover",
          type: "fill",
          source: "canopyTurnover",
          layout: { visibility: "none" },
          paint: {
            "fill-color": [
              "match",
              ["get", "turnover_tier"],
              "high", "#c51b7d",
              "medium", "#ef8a34",
              "low", "#9bbe78",
              "#000000",
            ],
            "fill-opacity": 0.5,
            "fill-outline-color": "rgba(255,255,255,0.35)",
          },
        },
        {
          id: "off-inventory",
          type: "circle",
          source: "offInventory",
          layout: { visibility: "none" },
          paint: {
            "circle-color": showCandidateSpecies
              ? [
                  "case",
                  ["==", ["coalesce", ["get", "imagery_group"], ["get", "predicted_group"]], "conifer"],
                  "#14563a",
                  ["==", ["coalesce", ["get", "imagery_group"], ["get", "predicted_group"]], "deciduous"],
                  "#91a948",
                  "#d98a2b",
                ]
              : "#d98a2b",
            "circle-radius": ["interpolate", ["linear"], ["get", "height_m"], 3, 2, 30, 5, 70, 8],
            "circle-opacity": ["interpolate", ["linear"], ["get", "confidence"], 0.3, 0.35, 0.9, 0.9],
            "circle-stroke-color": "#7b4a12",
            "circle-stroke-width": 0.6,
          },
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
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 13, 0.55, 15, 1.2, 17, 2.8, 19, 6],
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 13, 0, 16, 0.25, 19, 0.8],
            "circle-opacity": ["interpolate", ["linear"], ["zoom"], 13, 0.34, 16, 0.74, 19, 0.95],
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
  map.on("click", (event) => {
    const point = event.point;
    const treeHits = map.queryRenderedFeatures(
      [
        [point.x - 6, point.y - 6],
        [point.x + 6, point.y + 6],
      ],
      { layers: ["trees"] },
    );
    if (treeHits.length) {
      const feature = treeHits[0];
      selectTree(feature.properties.tree_id, feature.properties);
      return;
    }
    const candidateHits = map.queryRenderedFeatures(event.point, {
      layers: ["off-inventory"],
    });
    if (candidateHits.length) {
      const properties = candidateHits[0].properties || {};
      selectCandidate(properties.candidate_id, properties);
      return;
    }
    if (state.mode === "zone") {
      placeAt(event.lngLat.lng, event.lngLat.lat);
      return;
    }
    if (state.mode === "plant" || state.mode === "move") {
      placeAt(event.lngLat.lng, event.lngLat.lat);
    }
  });
  map.on("mousemove", (event) => {
    const point = event.point;
    const hits = map.queryRenderedFeatures(
      [
        [point.x - 6, point.y - 6],
        [point.x + 6, point.y + 6],
      ],
      { layers: ["trees", "off-inventory"] },
    );
    map.getCanvas().style.cursor = hits.length ? "pointer" : "";
  });
  map.on("mouseleave", () => {
    map.getCanvas().style.cursor = "";
  });
  state.map = map;
  state.selectedSourceReady = true;
}

function walkHeightAt(x, z) {
  const source = threeScene();
  if (!source) return null;
  const terrain = source.terrain;
  const [left, bottom, right, top] = source.bounds;
  const origin = source.origin;
  const xAbs = x + origin.x;
  const yAbs = origin.y - z;
  const col = Math.round(((xAbs - left) / Math.max(right - left, 1e-9)) * (terrain.width - 1));
  const row = Math.round(((top - yAbs) / Math.max(top - bottom, 1e-9)) * (terrain.height - 1));
  if (col < 0 || row < 0 || col >= terrain.width || row >= terrain.height) return null;
  const value = terrain.elevation[row * terrain.width + col];
  return Number.isFinite(value) ? value - origin.z : null;
}

function setWalkMode(enabled) {
  const three = state.three;
  if (!three) return;
  const canvas = three.renderer.domElement;
  if (enabled) {
    three.walkMode = true;
    three.controls.enabled = false;
    three.walkKeys.clear();
    const source = threeScene();
    const origin = source.origin;
    const [left, bottom, right, top] = source.bounds;
    let x = three.controls.target.x;
    let z = three.controls.target.z;
    let height = walkHeightAt(x, z);
    if (height === null) {
      x = (left + right) / 2 - origin.x;
      z = origin.y - (bottom + top) / 2;
      height = walkHeightAt(x, z) ?? 0;
    }
    const direction = new THREE.Vector3();
    three.camera.getWorldDirection(direction);
    three.walkYaw = Math.atan2(-direction.x, -direction.z);
    three.walkPitch = 0;
    three.camera.position.set(x, height + three.walkEyeHeight, z);
    three.camera.rotation.order = "YXZ";
    three.camera.rotation.set(0, three.walkYaw, 0);
    three.walkClock.start();
    three.walkClock.getDelta();
    $("walk-hud").hidden = false;
    $("scene-walk").textContent = "Orbit";
    $("scene-walk-status").textContent = "click to look";
    canvas.requestPointerLock?.();
  } else {
    three.walkMode = false;
    three.walkKeys.clear();
    three.controls.enabled = true;
    if (document.pointerLockElement === canvas) document.exitPointerLock();
    const forward = new THREE.Vector3(-Math.sin(three.walkYaw), 0, -Math.cos(three.walkYaw));
    three.controls.target.set(
      three.camera.position.x + forward.x * Math.max(18, sceneSpan() * 0.02),
      Math.max(1, three.camera.position.y - three.walkEyeHeight),
      three.camera.position.z + forward.z * Math.max(18, sceneSpan() * 0.02),
    );
    three.controls.update();
    $("walk-hud").hidden = true;
    $("scene-walk").textContent = "Walk";
    $("scene-walk-status").textContent = "orbit";
  }
}

function updateWalk(delta) {
  const three = state.three;
  if (!three?.walkMode) return;
  const keys = three.walkKeys;
  const forward = Number(keys.has("w") || keys.has("arrowup")) - Number(keys.has("s") || keys.has("arrowdown"));
  const strafe = Number(keys.has("d") || keys.has("arrowright")) - Number(keys.has("a") || keys.has("arrowleft"));
  const source = threeScene();
  const origin = source.origin;
  const [left, bottom, right, top] = source.bounds;
  const speed = (keys.has("shift") ? three.walkSprint : three.walkSpeed) * Math.min(delta, 0.1);
  const directionX = -Math.sin(three.walkYaw);
  const directionZ = -Math.cos(three.walkYaw);
  const rightX = Math.cos(three.walkYaw);
  const rightZ = -Math.sin(three.walkYaw);
  const nextX = Math.max(
    left - origin.x,
    Math.min(right - origin.x, three.camera.position.x + (directionX * forward + rightX * strafe) * speed),
  );
  const nextZ = Math.max(
    origin.y - top,
    Math.min(origin.y - bottom, three.camera.position.z + (directionZ * forward + rightZ * strafe) * speed),
  );
  const height = walkHeightAt(nextX, nextZ);
  if (height !== null) {
    three.camera.position.set(nextX, height + three.walkEyeHeight, nextZ);
  }
  three.camera.rotation.order = "YXZ";
  three.camera.rotation.set(three.walkPitch, three.walkYaw, 0);
}

function ensureThree() {
  if (state.three) {
    state.three.renderer.setSize(state.three.container.clientWidth, state.three.container.clientHeight, false);
    return state.three;
  }
  const container = $("view-scene");
  const canvas = $("scene-canvas");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  const sourceScene = threeScene();
  const compactScene = Boolean(sourceScene?.compact);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, compactScene ? 1 : 2));
  renderer.setSize(container.clientWidth, container.clientHeight, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = !compactScene;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const span = sceneSpan();
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#dfe7dc");
  scene.fog = new THREE.Fog("#dfe7dc", span * 1.15, span * 4.2);

  const camera = new THREE.PerspectiveCamera(46, container.clientWidth / Math.max(container.clientHeight, 1), 0.5, span * 7);
  const cameraDistance = Math.max(300, span * 0.62);
  camera.position.set(cameraDistance * 0.55, cameraDistance * 0.52, cameraDistance * 0.85);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, Math.max(12, span * 0.01), 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = Math.PI / 2.04;
  controls.minDistance = 30;
  controls.maxDistance = span * 2.8;

  const ambient = new THREE.HemisphereLight(0xf7fbf4, 0x495243, 1.3);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(0xfff4dc, 1.8);
  sun.position.set(-span * 0.45, span * 0.72, span * 0.32);
  sun.castShadow = !compactScene;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.left = -span * 0.45;
  sun.shadow.camera.right = span * 0.45;
  sun.shadow.camera.top = span * 0.45;
  sun.shadow.camera.bottom = -span * 0.45;
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = span * 4;
  scene.add(sun);
  scene.add(sun.target);
  const sunSphere = new THREE.Mesh(
    new THREE.SphereGeometry(Math.max(9, span * 0.006), 18, 12),
    new THREE.MeshBasicMaterial({ color: 0xffe6a0 })
  );
  sunSphere.position.set(-span * 0.7, span * 0.9, span * 0.4);
  scene.add(sunSphere);

  const terrain = buildTerrainMesh();
  scene.add(terrain);
  const buildings = buildBuildingMeshes();
  buildings.forEach((mesh) => scene.add(mesh));
  const roads = buildRoadLines();
  if (roads) scene.add(roads);

  const three = {
    renderer,
    scene,
    camera,
    controls,
    container,
    terrain,
    compact: compactScene,
    buildingMeshes: buildings,
    roadLines: roads,
    crownMeshes: [],
    trunkMeshes: [],
    treeGroups: new Map(),
    selectedMarker: null,
    walkMode: false,
    walkKeys: new Set(),
    walkYaw: 0,
    walkPitch: 0,
    walkEyeHeight: 1.7,
    walkSpeed: 7,
    walkSprint: 14,
    walkClock: new THREE.Clock(),
    sunLight: sun,
    sunSphere,
  };
  state.three = three;
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  renderer.domElement.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    if (state.three?.walkMode) {
      if (document.pointerLockElement !== renderer.domElement) {
        renderer.domElement.requestPointerLock();
      }
      return;
    }
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    if (state.mode === "zone") {
      const terrainHits = raycaster.intersectObject(terrain, false);
      if (!terrainHits.length) return;
      const local = terrainHits[0].point;
      const source = threeScene();
      const origin = source.origin_lonlat;
      const metres = source.meters_per_degree;
      placeAt(origin[0] + local.x / metres[0], origin[1] - local.z / metres[1]);
      return;
    }
    const targets = [
      ...three.crownMeshes,
      ...three.trunkMeshes,
      ...(three.offInventoryMeshes || []),
      terrain,
    ];
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
    if (
      hit.object.userData.kind === "off-crown" ||
      hit.object.userData.kind === "off-trunk"
    ) {
      const candidate = hit.object.userData.candidates[hit.instanceId];
      if (candidate) {
        selectCandidate(candidate.candidate_id, candidate);
        return;
      }
    }
    if (state.mode === "plant" || state.mode === "move") {
      const local = hit.point;
      const source = threeScene();
      const origin = source.origin_lonlat;
      const metres = source.meters_per_degree;
      const lon = origin[0] + local.x / metres[0];
      const lat = origin[1] - local.z / metres[1];
      placeAt(lon, lat);
    }
  });
  renderer.domElement.addEventListener("pointerdown", () => {
    renderer.domElement.style.cursor = "default";
  });
  document.addEventListener("pointerlockchange", () => {
    if (!state.three?.walkMode) return;
    $("scene-walk-status").textContent =
      document.pointerLockElement === renderer.domElement ? "mouse captured" : "click to look";
  });
  document.addEventListener("mousemove", (event) => {
    if (!state.three?.walkMode || document.pointerLockElement !== renderer.domElement) return;
    state.three.walkYaw -= event.movementX * 0.0022;
    state.three.walkPitch = Math.max(
      -Math.PI / 2.05,
      Math.min(Math.PI / 2.05, state.three.walkPitch - event.movementY * 0.0022),
    );
  });
  window.addEventListener("keydown", (event) => {
    if (!state.three?.walkMode) return;
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
    const key = event.key.toLowerCase();
    if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright", "shift"].includes(key)) {
      event.preventDefault();
      state.three.walkKeys.add(key);
    }
  });
  window.addEventListener("keyup", (event) => {
    state.three?.walkKeys.delete(event.key.toLowerCase());
  });
  window.addEventListener("blur", () => state.three?.walkKeys.clear());
  window.addEventListener("resize", () => {
    if (!state.three) return;
    const width = state.three.container.clientWidth;
    const height = Math.max(state.three.container.clientHeight, 1);
    state.three.renderer.setSize(width, height, false);
    state.three.camera.aspect = width / height;
    state.three.camera.updateProjectionMatrix();
  });
  const source = threeScene();
  rebuildThreeTrees(source.compact ? source.tree_arrays : source.trees);
  applySun();
  animateThree();
  return three;
}

function buildTerrainMesh() {
  const sceneData = threeScene();
  const { width, height, elevation, canopy_height: canopy } = sceneData.terrain;
  const [left, bottom, right, top] = sceneData.bounds;
  const spanX = right - left;
  const spanZ = top - bottom;
  const originX = sceneData.origin.x;
  const originY = sceneData.origin.y;
  const originZ = sceneData.origin.z;
  const positions = [];
  const colors = [];
  const indices = [];
  const color = new THREE.Color();
  for (let row = 0; row < height; row += 1) {
    for (let col = 0; col < width; col += 1) {
      const index = row * width + col;
      const x = left + (col / Math.max(width - 1, 1)) * spanX - originX;
      const z = originY - (top - (row / Math.max(height - 1, 1)) * spanZ);
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
      indices.push(a, b, c, b, d, c);
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

function roadWidthMeters(highway) {
  const widths = {
    motorway: 10.0,
    motorway_link: 6.0,
    trunk: 9.0,
    trunk_link: 5.5,
    primary: 8.0,
    primary_link: 5.0,
    secondary: 6.5,
    secondary_link: 4.5,
    tertiary: 5.5,
    tertiary_link: 4.0,
    residential: 4.0,
    living_street: 4.0,
    unclassified: 3.5,
    service: 3.0,
    pedestrian: 3.0,
    cycleway: 2.0,
    footway: 1.5,
    path: 1.2,
    steps: 1.2,
  };
  return widths[String(highway || "unclassified")] || 3.5;
}

function buildRoadLines() {
  const source = threeScene();
  const features = state.roads?.features;
  if (!Array.isArray(features) || !source) return null;
  const [originLon, originLat] = source.origin_lonlat;
  const [mx, my] = source.meters_per_degree;
  const terrain = source.terrain;
  const [left, bottom, right, top] = terrain.bounds;
  const width = terrain.width;
  const height = terrain.height;
  const elevation = terrain.elevation;
  const originX = source.origin.x;
  const originY = source.origin.y;
  const originZ = source.origin.z;
  const positions = [];
  const indices = [];
  let vertex = 0;
  const point = (lon, lat) => {
    const x = (lon - originLon) * mx;
    const y = (lat - originLat) * my;
    const col = Math.round(((x + originX - left) / Math.max(right - left, 1e-9)) * (width - 1));
    const row = Math.round(((top - (y + originY)) / Math.max(top - bottom, 1e-9)) * (height - 1));
    if (col < 0 || row < 0 || col >= width || row >= height) return null;
    const z = elevation[row * width + col];
    return [x, Number.isFinite(z) ? z - originZ + 0.08 : 0.08, -y];
  };
  for (const feature of features) {
    const coordinates = feature.geometry?.coordinates;
    if (!Array.isArray(coordinates)) continue;
    const halfWidth = roadWidthMeters(feature.properties?.highway) / 2.0;
    for (let index = 0; index < coordinates.length - 1; index += 1) {
      const first = point(coordinates[index][0], coordinates[index][1]);
      const second = point(coordinates[index + 1][0], coordinates[index + 1][1]);
      if (!first || !second) continue;
      const dx = second[0] - first[0];
      const dz = second[2] - first[2];
      const length = Math.hypot(dx, dz);
      if (length < 0.1) continue;
      const px = (-dz / length) * halfWidth;
      const pz = (dx / length) * halfWidth;
      positions.push(
        first[0] - px, first[1], first[2] - pz,
        first[0] + px, first[1], first[2] + pz,
        second[0] - px, second[1], second[2] - pz,
        second[0] + px, second[1], second[2] + pz,
      );
      indices.push(vertex, vertex + 1, vertex + 2, vertex + 1, vertex + 3, vertex + 2);
      vertex += 4;
    }
  }
  if (!positions.length) return null;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.9,
    depthTest: true,
    depthWrite: false,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
    side: THREE.DoubleSide,
  });
  const roads = new THREE.Mesh(geometry, material);
  roads.name = "roads";
  roads.userData.kind = "roads";
  roads.renderOrder = 1;
  return roads;
}


async function ensureOffInventory3D() {
  if (!state.three || state.offInventory3DLoading) return;
  if (state.three.offInventoryGroup) {
    state.three.offInventoryGroup.visible = Boolean($("toggle-off-inventory")?.checked);
    return;
  }
  if (!state.dataset?.has_off_inventory_3d) {
    $("scene-candidate-status").textContent = "3D candidates unavailable";
    return;
  }
  state.offInventory3DLoading = true;
  $("scene-candidate-status").textContent = "loading candidates…";
  try {
    if (!state.offInventory3D) {
      state.offInventory3D = await api("api/off-inventory-3d");
    }
    const data = state.offInventory3D;
    const count = Number(data?.count || 0);
    $("scene-candidate-status").textContent = `building ${formatNumber(count)} candidate trees…`;
    if (!count || !state.three) {
      $("scene-candidate-status").textContent = "no high-confidence candidates";
      return;
    }
    const source = threeScene();
    const terrain = source.terrain;
    const [left, bottom, right, top] = source.bounds;
    const originX = source.origin.x;
    const originY = source.origin.y;
    const originZ = source.origin.z;
    const terrainBase = (x, z) => {
      const north = -z;
      const col = Math.round(((x + originX - left) / Math.max(right - left, 1e-9)) * (terrain.width - 1));
      const row = Math.round(((top - (north + originY)) / Math.max(top - bottom, 1e-9)) * (terrain.height - 1));
      if (col < 0 || row < 0 || col >= terrain.width || row >= terrain.height) return 0;
      const value = terrain.elevation[row * terrain.width + col];
      return Number.isFinite(value) ? value - originZ : 0;
    };
    const landNames = ["likely private parcel", "street/lane", "public park", "other parcel", "unknown"];
    const colorFor = (land) => (land === 0 ? "#f2a33b" : "#b8641d");
    const opacityBins = [0.36, 0.55, 0.74, 0.92];
    const buckets = Array.from({ length: 8 }, () => []);
    for (let index = 0; index < count; index += 1) {
      const confidence = Number(data.confidence[index] || 0);
      const radius = Number(data.crown_radius_m[index] || 0);
      if (confidence < 0.6 || radius > 25) continue;
      const bin = confidence < 0.7 ? 0 : confidence < 0.8 ? 1 : confidence < 0.9 ? 2 : 3;
      const land = Number(data.land_code[index]);
      const x = Number(data.x_m[index]) - originX;
      const z = -(Number(data.y_m[index]) - originY);
      const height = Math.max(Number(data.height_m[index] || 2), 1.5);
      const crownDepth = Math.max(height * 0.55, 1);
      const trunkHeight = Math.max(height - crownDepth, 0.8);
      const base = terrainBase(x, z);
      buckets[bin * 2 + (land === 0 ? 0 : 1)].push({
        x,
        z,
        base,
        height,
        crownWidth: Math.max(Number(data.crown_radius_m[index] || 0) * 2, 1),
        crownDepth,
        trunkHeight,
        candidate: {
          candidate_id: String(data.candidate_id[index]),
          height_m: Number(data.height_m[index]),
          crown_radius_m: Number(data.crown_radius_m[index]),
          crown_area_m2: Number(data.crown_area_m2[index]),
          dbh_cm: Number(data.dbh_cm[index]),
          crown_volume_m3: Number(data.crown_volume_m3[index]),
          carbon_kg: Number(data.carbon_kg[index]),
          confidence,
          point_count: Number(data.point_count[index]),
          land_class: landNames[land] || "unknown",
        },
      });
    }
    $("scene-candidate-status").textContent = "assembling candidate tree meshes…";
    const group = new THREE.Group();
    group.name = "off-inventory-3d";
    let builtCount = 0;
    const meshes = [];
    const crownGeometry = new THREE.SphereGeometry(0.5, 7, 6);
    const trunkGeometry = new THREE.CylinderGeometry(0.12, 0.2, 1, 5);
    const matrix = new THREE.Matrix4();
    const quaternion = new THREE.Quaternion();
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();
    for (let bucketIndex = 0; bucketIndex < buckets.length; bucketIndex += 1) {
      const items = buckets[bucketIndex];
      if (!items.length) continue;
      builtCount += items.length;
      const bin = Math.floor(bucketIndex / 2);
      const light = bucketIndex % 2 === 0;
      const opacity = opacityBins[bin];
      const color = light ? "#f2a33b" : "#b8641d";
      const crownMaterial = new THREE.MeshStandardMaterial({
        color,
        roughness: 0.9,
        metalness: 0,
        transparent: true,
        opacity,
        depthWrite: opacity > 0.8,
      });
      const trunkMaterial = new THREE.MeshStandardMaterial({
        color: light ? "#a9692d" : "#7d4a1d",
        roughness: 1,
        transparent: true,
        opacity,
        depthWrite: opacity > 0.8,
      });
      const crowns = new THREE.InstancedMesh(crownGeometry, crownMaterial, items.length);
      const trunks = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, items.length);
      crowns.castShadow = false;
      crowns.receiveShadow = false;
      trunks.castShadow = false;
      trunks.receiveShadow = false;
      items.forEach((item, instance) => {
        position.set(item.x, item.base + item.trunkHeight + item.crownDepth * 0.5, item.z);
        scale.set(item.crownWidth, item.crownDepth, item.crownWidth);
        matrix.compose(position, quaternion, scale);
        crowns.setMatrixAt(instance, matrix);
        position.set(item.x, item.base + item.trunkHeight * 0.5, item.z);
        scale.set(1, item.trunkHeight, 1);
        matrix.compose(position, quaternion, scale);
        trunks.setMatrixAt(instance, matrix);
      });
      crowns.instanceMatrix.needsUpdate = true;
      trunks.instanceMatrix.needsUpdate = true;
      crowns.userData = { kind: "off-crown", candidates: items.map((item) => item.candidate) };
      trunks.userData = { kind: "off-trunk", candidates: items.map((item) => item.candidate) };
      group.add(crowns, trunks);
      meshes.push(crowns, trunks);
    }
    state.three.scene.add(group);
    state.three.offInventoryGroup = group;
    state.three.offInventoryMeshes = meshes;
    group.visible = Boolean($("toggle-off-inventory")?.checked);
    $("scene-candidate-status").textContent = `${formatNumber(builtCount)} 3D candidates (score ≥ 0.6; radius ≤ 25 m; opacity = confidence)`;
  } catch (error) {
    $("scene-candidate-status").textContent = "candidates unavailable";
    toast(`Could not load 3D candidates: ${error.message}`, true);
  } finally {
    state.offInventory3DLoading = false;
  }
}

function buildBuildingMeshes() {
  const sceneData = threeScene();
  if (sceneData.compact && sceneData.building_boxes) {
    const boxes = sceneData.building_boxes;
    const count = Array.isArray(boxes.x) ? boxes.x.length : 0;
    if (!count) return [];
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshStandardMaterial({
      color: 0xc3c9bd,
      roughness: 0.82,
      metalness: 0.03,
    });
    const mesh = new THREE.InstancedMesh(geometry, material, count);
    const matrix = new THREE.Matrix4();
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    for (let index = 0; index < count; index += 1) {
      position.set(boxes.x[index], boxes.base[index] + boxes.h[index] / 2, -boxes.z[index]);
      scale.set(Math.max(boxes.w[index], 1), Math.max(boxes.h[index], 2), Math.max(boxes.d[index], 1));
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(index, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
    mesh.castShadow = !threeScene().compact;
    mesh.receiveShadow = !threeScene().compact;
    mesh.userData.kind = "building";
    mesh.name = "buildings";
    return [mesh];
  }
  const positions = [];
  const normals = [];
  for (const building of state.scene.buildings || []) {
    const ring = (building.rings_local || [])[0] || [];
    if (ring.length < 3) continue;
    const height = Math.max(Number(building.height_m) || 10, 2);
    const shape = new THREE.Shape();
    ring.forEach((point, index) => {
      const x = Number(point[0]);
      const y = Number(point[1]);
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
      geometry.translate(0, Number(building.base_z) || 0, 0);
    } catch (_error) {
      continue;
    }
    const flat = geometry.toNonIndexed();
    const position = flat.getAttribute("position");
    const normal = flat.getAttribute("normal");
    if (position) positions.push(...position.array);
    if (normal) normals.push(...normal.array);
    flat.dispose();
    geometry.dispose();
  }
  if (!positions.length) return [];
  const merged = new THREE.BufferGeometry();
  merged.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  if (normals.length === positions.length) {
    merged.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  }
  merged.computeBoundingSphere();
  const material = new THREE.MeshStandardMaterial({
    color: 0xc3c9bd,
    roughness: 0.82,
    metalness: 0.03,
    transparent: true,
    opacity: 0.82,
    depthWrite: true,
  });
  const mesh = new THREE.Mesh(merged, material);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.userData.kind = "building";
  mesh.name = "buildings";
  return [mesh];
}

function rebuildCompactTrees(trees) {
  const three = state.three;
  for (const mesh of [...three.crownMeshes, ...three.trunkMeshes]) {
    three.scene.remove(mesh);
    mesh.geometry.dispose();
    mesh.material.dispose();
  }
  three.crownMeshes = [];
  three.trunkMeshes = [];
  three.treeGroups = new Map();
  const groups = { 0: [], 1: [], 2: [] };
  for (let index = 0; index < trees.x.length; index += 1) {
    groups[trees.group[index]]?.push(index);
  }
  const names = { 0: "conifer", 1: "deciduous", 2: "unknown" };
  const colors = { 0: "#14563a", 1: "#91a948", 2: "#5f665f" };
  const matrix = new THREE.Matrix4();
  const quaternion = new THREE.Quaternion();
  const scale = new THREE.Vector3();
  const position = new THREE.Vector3();
  const color = new THREE.Color();
  for (const [groupKey, indices] of Object.entries(groups)) {
    if (!indices.length) continue;
    const groupName = names[groupKey] || "unknown";
    const crownGeometry =
      groupName === "conifer"
        ? new THREE.ConeGeometry(0.5, 1, 6, 1, false)
        : new THREE.SphereGeometry(0.5, 6, 5);
    const trunkGeometry = new THREE.CylinderGeometry(0.12, 0.2, 1, 4);
    const crownMaterial = new THREE.MeshStandardMaterial({ roughness: 0.9, metalness: 0.0 });
    const trunkMaterial = new THREE.MeshStandardMaterial({ color: 0x6d5a45, roughness: 1 });
    const crowns = new THREE.InstancedMesh(crownGeometry, crownMaterial, indices.length);
    const trunks = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, indices.length);
    crowns.castShadow = !three.compact;
    crowns.receiveShadow = !three.compact;
    trunks.castShadow = !three.compact;
    trunks.receiveShadow = !three.compact;
    indices.forEach((treeIndex, instance) => {
      const height = Math.max(trees.height[treeIndex] || 2, 1.5);
      const crownWidth = Math.max(trees.crown_width[treeIndex] || height * 0.35, 0.8);
      const crownDepth = Math.max(height * 0.55, 1.0);
      const trunkHeight = Math.max(height - crownDepth, 0.8);
      position.set(
        trees.x[treeIndex],
        trees.z[treeIndex] + trunkHeight + crownDepth * 0.5,
        -trees.y[treeIndex],
      );
      scale.set(crownWidth, crownDepth, crownWidth);
      matrix.compose(position, quaternion, scale);
      crowns.setMatrixAt(instance, matrix);
      color.set(colors[groupKey] || colors[2]);
      crowns.setColorAt(instance, color);
      position.set(
        trees.x[treeIndex],
        trees.z[treeIndex] + trunkHeight * 0.5,
        -trees.y[treeIndex],
      );
      scale.set(1, trunkHeight, 1);
      matrix.compose(position, quaternion, scale);
      trunks.setMatrixAt(instance, matrix);
    });
    crowns.instanceMatrix.needsUpdate = true;
    if (crowns.instanceColor) crowns.instanceColor.needsUpdate = true;
    trunks.instanceMatrix.needsUpdate = true;
    three.scene.add(crowns, trunks);
    three.crownMeshes.push(crowns);
    three.trunkMeshes.push(trunks);
    three.treeGroups.set(groupName, indices);
  }
  updateSelectedMarker();
}

function rebuildThreeTrees(trees) {
  if (!state.three) return;
  const three = state.three;
  if (!Array.isArray(trees) && trees && Array.isArray(trees.x)) {
    rebuildCompactTrees(trees);
    return;
  }
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
    crowns.castShadow = !three.compact;
    crowns.receiveShadow = !three.compact;
    trunks.castShadow = !three.compact;
    trunks.receiveShadow = !three.compact;
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
      position.set(tree.x, tree.z + trunkHeight + crownDepth * 0.5, -tree.y);
      scale.set(crownWidth, crownDepth, crownWidth);
      matrix.compose(position, quaternion, scale);
      crowns.setMatrixAt(index, matrix);
      color.set(tree.color || "#68a357");
      crowns.setColorAt(index, color);
      position.set(tree.x, tree.z + trunkHeight * 0.5, -tree.y);
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
  marker.position.set(tree.x, tree.z + 0.25, -tree.y);
  three.scene.add(marker);
  three.selectedMarker = marker;
}

function animateThree() {
  if (!state.three) return;
  const three = state.three;
  const delta = three.walkClock.getDelta();
  if (three.walkMode) updateWalk(delta);
  else three.controls.update();
  three.renderer.render(three.scene, three.camera);
  requestAnimationFrame(animateThree);
}

function selectCandidate(candidateId, candidateData = null) {
  const candidate = candidateData || null;
  if (!candidate) return;
  state.selectedCandidateId = candidateId;
  state.selectedId = "";
  updateMapSelection();
  updateSelectedMarker();
  const height = Number(candidate.height_m || 0);
  const radius = Number(candidate.crown_radius_m || 0);
  const dbh = Number(candidate.dbh_cm || 0);
  const volume = Number(candidate.crown_volume_m3 || 0);
  const carbon = Number(candidate.carbon_kg || 0);
  const confidence = Number(candidate.confidence || 0);
  const crownDiameter = radius * 2;
  const heightLow = candidate.height_low_m ?? height * 0.8;
  const heightHigh = candidate.height_high_m ?? height * 1.2;
  const dbhLow = candidate.dbh_low_cm ?? dbh * 0.65;
  const dbhHigh = candidate.dbh_high_cm ?? dbh * 1.35;
  const carbonLow = candidate.carbon_low_kg ?? carbon * 0.5;
  const carbonHigh = candidate.carbon_high_kg ?? carbon * 1.5;
  $("selected-label").textContent = `${candidateId} · off-inventory candidate`;
  $("tree-detail").innerHTML = `
    <dl>
      <dt>ID</dt><dd>${escapeHtml(candidateId)}</dd>
      <dt>Type</dt><dd>Off-inventory candidate</dd>
      <dt>Species</dt><dd>Not identified</dd>
      <dt>Height</dt><dd>${formatNumber(height, 1)} m (${formatNumber(heightLow, 1)}–${formatNumber(heightHigh, 1)} m)</dd>
      <dt>DBH</dt><dd>${formatNumber(dbh, 1)} cm (${formatNumber(dbhLow, 1)}–${formatNumber(dbhHigh, 1)} cm)</dd>
      <dt>Crown diameter</dt><dd>${formatNumber(crownDiameter, 1)} m</dd>
      <dt>Crown shape</dt><dd>Ellipsoid screening / watershed segment</dd>
      <dt>Crown volume</dt><dd>${formatCompact(volume)} m³</dd>
      <dt>Carbon</dt><dd>${formatNumber(carbon / 1000, 2)} t (${formatNumber(carbonLow / 1000, 2)}–${formatNumber(carbonHigh / 1000, 2)} t)</dd>
      <dt>Confidence</dt><dd>${formatNumber(confidence, 2)}</dd>
      <dt>Land proxy</dt><dd>${escapeHtml(candidate.land_class || "unknown")}</dd>
      <dt>Point support</dt><dd>${candidate.point_count == null ? "n/a" : formatNumber(candidate.point_count)}</dd>
      <dt>Nearest public tree</dt><dd>${candidate.nearest_inventory_m == null ? "n/a" : `${formatNumber(candidate.nearest_inventory_m, 1)} m`}</dd>
    </dl>
    <p class="muted">Screening candidate, not a confirmed tree or ownership record. Species and measurements are not field-verified.</p>`;
  $("remove-tree").disabled = true;
  $("replace-tree").disabled = true;
  $("move-tree").disabled = true;
}

function selectTree(treeId, treeData = null) {
  const tree = treeData || state.treeById.get(treeId);
  if (!tree) return;
  if (treeData) state.treeById.set(treeId, treeData);
  state.selectedId = treeId;
  state.selectedCandidateId = "";
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
  $("export-report").addEventListener("click", exportLabReport);
  $("preview").addEventListener("click", previewScenario);
  $("reset-edits").addEventListener("click", clearEdits);
  $("new-scenario").addEventListener("click", newScenario);
  $("scenario-select").addEventListener("change", async (event) => {
    if (event.target.value) {
      await loadScenario(event.target.value, { focusPareto: true });
    } else {
      showBaseline();
      switchView("map");
    }
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
  $("scene-downtown").addEventListener("click", focusDowntown);
  $("scene-walk").addEventListener("click", () => setWalkMode(!state.three?.walkMode));
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
  $("toggle-roads").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("roads")) {
      const visibility = event.target.checked ? "visible" : "none";
      state.map.setLayoutProperty("roads", "visibility", visibility);
      state.map.setLayoutProperty("roads-casing", "visibility", visibility);
    }
    if (state.three?.roadLines) {
      state.three.roadLines.visible = event.target.checked;
    }
  });
  $("toggle-buildings").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("buildings")) {
      const visibility = event.target.checked ? "visible" : "none";
      state.map.setLayoutProperty("buildings", "visibility", visibility);
      state.map.setLayoutProperty("buildings-outline", "visibility", visibility);
    }
  });
  $("toggle-off-inventory").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("off-inventory")) {
      state.map.setLayoutProperty("off-inventory", "visibility", event.target.checked ? "visible" : "none");
      applyOffInventoryFilter();
    }
    if (state.three?.offInventoryGroup) {
      state.three.offInventoryGroup.visible = event.target.checked;
    }
    if (event.target.checked) ensureOffInventory3D();
  });
  $("toggle-heat-priority").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("heat-priority")) {
      state.map.setLayoutProperty(
        "heat-priority",
        "visibility",
        event.target.checked ? "visible" : "none",
      );
    }
  });
  $("toggle-canopy-turnover").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("canopy-turnover")) {
      state.map.setLayoutProperty(
        "canopy-turnover",
        "visibility",
        event.target.checked ? "visible" : "none",
      );
    }
  });
  $("canopy-action-version").addEventListener("change", (event) => {
    loadCanopyActionVersion(event.target.value);
  });
  $("canopy-turnover-version").addEventListener("change", (event) => {
    loadCanopyTurnoverVersion(event.target.value);
  });
  $("toggle-canopy-action").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("canopy-action")) {
      state.map.setLayoutProperty(
        "canopy-action",
        "visibility",
        event.target.checked ? "visible" : "none",
      );
    }
  });
  $("toggle-canopy-change").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("canopy-change")) {
      state.map.setLayoutProperty(
        "canopy-change",
        "visibility",
        event.target.checked ? "visible" : "none",
      );
    }
  });
  $("toggle-heat-equity").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("heat-equity")) {
      state.map.setLayoutProperty(
        "heat-equity",
        "visibility",
        event.target.checked ? "visible" : "none",
      );
    }
  });
  $("toggle-planting-opportunity").addEventListener("change", (event) => {
    if (state.map && state.map.getLayer("planting-opportunity")) {
      state.map.setLayoutProperty(
        "planting-opportunity",
        "visibility",
        event.target.checked ? "visible" : "none",
      );
    }
  });
  $("off-inventory-confidence").addEventListener("change", applyOffInventoryFilter);
  $("off-inventory-land").addEventListener("change", applyOffInventoryFilter);
}

function applyOffInventoryFilter() {
  if (!state.map || !state.map.getLayer("off-inventory")) return;
  const minimum = Number($("off-inventory-confidence").value || 0);
  const land = $("off-inventory-land").value;
  const filter = [
    "all",
    [">=", ["get", "confidence"], minimum],
    ["<=", ["get", "crown_radius_m"], 25],
  ];
  if (land !== "all") filter.push(["==", ["get", "land_class"], land]);
  state.map.setFilter("off-inventory", filter);
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
  if (view !== "scene" && state.three?.walkMode) setWalkMode(false);
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
    if ($("toggle-off-inventory")?.checked) ensureOffInventory3D();
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
  if (view === "birds") {
    loadBirds();
  }
  if (view === "sites") {
    ensureSitesView();
    window.setTimeout(() => {
      if (state.siteScenario.map) state.siteScenario.map.resize();
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

function updateSiteTabVisibility(visible) {
  const tab = document.querySelector('[data-view="sites"]');
  if (!tab) return;
  tab.hidden = !visible;
  if (!visible && tab.classList.contains("active")) switchView("map");
}

function initSiteControls() {
  const inputIds = [
    "site-species",
    "site-height",
    "site-crown",
    "site-count",
    "site-cost",
    "site-water",
    "site-maintenance",
    "site-date",
    "site-time",
    "site-target-height",
  ];
  const assumptionIds = new Set([
    "site-species",
    "site-height",
    "site-crown",
    "site-count",
    "site-cost",
    "site-water",
    "site-maintenance",
  ]);
  for (const id of inputIds) {
    $(id).addEventListener("input", () => {
      if (assumptionIds.has(id)) $("site-preset").value = "custom";
      renderSiteSelection();
      invalidateSiteEvaluation();
    });
  }
  $("site-sensitivity").addEventListener("change", invalidateSiteEvaluation);
  $("site-preset").addEventListener("change", applySitePreset);
  $("site-save").addEventListener("click", saveSiteScenario);
  $("site-load").addEventListener("click", loadSiteScenario);
  $("site-delete").addEventListener("click", deleteSiteScenario);
  $("site-export").addEventListener("click", exportSiteScenarios);
  $("site-import").addEventListener("change", importSiteScenarios);
  $("site-saved-select").addEventListener("change", () => {
    $("site-saved-name").value = $("site-saved-select").value;
    updateSiteSavedButtons();
  });
  refreshSiteScenarioSelect();
  $("site-action-filter").addEventListener("change", applySiteFilter);
  $("site-select-six").addEventListener("click", selectSixSiteCandidates);
  $("site-clear").addEventListener("click", clearSiteSelection);
  $("site-evaluate").addEventListener("click", evaluateSiteScenario);
  $("site-open-3d").addEventListener("click", openSiteScenario3D);
  renderSiteSelection();
}

const SITE_ASSUMPTION_PRESETS = {
  small: { height_m: 6, crown_radius_m: 2.0, cost_cad: 650, water_l_per_year: 800 },
  medium: { height_m: 8, crown_radius_m: 3.0, cost_cad: 850, water_l_per_year: 1200 },
  large: { height_m: 12, crown_radius_m: 5.0, cost_cad: 1400, water_l_per_year: 2000 },
};

function applySitePreset() {
  const preset = SITE_ASSUMPTION_PRESETS[$("site-preset").value];
  if (!preset) return;
  $("site-height").value = String(preset.height_m);
  $("site-crown").value = String(preset.crown_radius_m);
  $("site-cost").value = String(preset.cost_cad);
  $("site-water").value = String(preset.water_l_per_year);
  renderSiteSelection();
  invalidateSiteEvaluation();
}

function siteEvaluationSummary() {
  const evaluation = state.siteScenario.evaluation;
  if (!evaluation) return null;
  return {
    method: String(evaluation.method || ""),
    baseline_shade_m2h: Number(evaluation.baseline_shade_m2h || 0),
    scenario_shade_m2h: Number(evaluation.scenario_shade_m2h || 0),
    delta_shade_m2h: Number(evaluation.delta_shade_m2h || 0),
    delta_shade_pct:
      evaluation.delta_shade_pct == null ? null : Number(evaluation.delta_shade_pct),
    baseline_shade_fraction: Number(evaluation.baseline_shade_fraction || 0),
    scenario_shade_fraction: Number(evaluation.scenario_shade_fraction || 0),
  };
}

function normalizeSiteScenarioEvaluation(raw) {
  if (!raw || typeof raw !== "object") return null;
  const values = [
    "baseline_shade_m2h",
    "scenario_shade_m2h",
    "delta_shade_m2h",
    "baseline_shade_fraction",
    "scenario_shade_fraction",
  ];
  for (const key of values) {
    if (!Number.isFinite(Number(raw[key]))) return null;
  }
  const percent = raw.delta_shade_pct;
  return {
    method: String(raw.method || ""),
    baseline_shade_m2h: Number(raw.baseline_shade_m2h),
    scenario_shade_m2h: Number(raw.scenario_shade_m2h),
    delta_shade_m2h: Number(raw.delta_shade_m2h),
    delta_shade_pct: percent == null ? null : Number(percent),
    baseline_shade_fraction: Number(raw.baseline_shade_fraction),
    scenario_shade_fraction: Number(raw.scenario_shade_fraction),
  };
}

function normalizeSiteScenarioRecord(raw) {
  if (!raw || typeof raw !== "object" || raw.version !== SITE_SCENARIO_LIBRARY_VERSION) {
    return null;
  }
  const name = String(raw.name || "").trim().slice(0, 80);
  const datasetId = String(raw.dataset_id || "").trim().slice(0, 120);
  const candidatesSchema = String(raw.candidates_schema || "").trim().slice(0, 120);
  if (!name || !datasetId || !candidatesSchema) return null;
  if (!Array.isArray(raw.selected) || raw.selected.length < 1 || raw.selected.length > 200) {
    return null;
  }
  const selected = [...new Set(raw.selected.map((value) => String(value).slice(0, 120)))];
  if (selected.length !== raw.selected.length) return null;
  const assumptions = raw.assumptions;
  const settings = raw.settings;
  if (!assumptions || typeof assumptions !== "object" || !settings || typeof settings !== "object") {
    return null;
  }
  const species = String(assumptions.species || "").trim().slice(0, 80);
  const maintenance = String(assumptions.maintenance || "").trim().slice(0, 120);
  const height = Number(assumptions.height_m);
  const crown = Number(assumptions.crown_radius_m);
  const count = Number(assumptions.count);
  const cost = Number(assumptions.cost_cad);
  const water = Number(assumptions.water_l_per_year);
  if (
    !species ||
    !maintenance ||
    !Number.isFinite(height) ||
    height < 0.5 ||
    height > 40 ||
    !Number.isFinite(crown) ||
    crown < 0.25 ||
    crown > 20 ||
    !Number.isInteger(count) ||
    count < 1 ||
    count > 50 ||
    !Number.isFinite(cost) ||
    cost < 0 ||
    cost > 1_000_000 ||
    !Number.isFinite(water) ||
    water < 0 ||
    water > 1_000_000
  ) {
    return null;
  }
  const targetHeight = Number(settings.target_height_m);
  if (!Number.isFinite(targetHeight) || targetHeight < 0.5 || targetHeight > 10) return null;
  const evaluation =
    raw.evaluation == null ? null : normalizeSiteScenarioEvaluation(raw.evaluation);
  if (raw.evaluation != null && evaluation == null) return null;
  return {
    version: SITE_SCENARIO_LIBRARY_VERSION,
    name,
    dataset_id: datasetId,
    candidates_schema: candidatesSchema,
    created_at: String(raw.created_at || new Date().toISOString()).slice(0, 40),
    selected,
    assumptions: {
      species,
      height_m: height,
      crown_radius_m: crown,
      count,
      cost_cad: cost,
      water_l_per_year: water,
      maintenance,
    },
    settings: {
      date: String(settings.date || "2026-06-21").slice(0, 20),
      time: String(settings.time || "12:00").slice(0, 10),
      target_height_m: targetHeight,
      sensitivity: Boolean(settings.sensitivity),
    },
    evaluation,
  };
}

function readSiteScenarioLibrary() {
  try {
    const raw = localStorage.getItem(SITE_SCENARIO_STORAGE_KEY);
    if (!raw) return [];
    const payload = JSON.parse(raw);
    if (!payload || payload.version !== SITE_SCENARIO_LIBRARY_VERSION) return [];
    if (!Array.isArray(payload.scenarios) || payload.scenarios.length > SITE_SCENARIO_LIMIT) {
      return [];
    }
    const records = [];
    for (const entry of payload.scenarios) {
      const record = normalizeSiteScenarioRecord(entry);
      if (!record) return [];
      const existing = records.findIndex((item) => item.name === record.name);
      if (existing >= 0) records[existing] = record;
      else records.push(record);
    }
    return records;
  } catch (_error) {
    return [];
  }
}

function writeSiteScenarioLibrary(records) {
  try {
    localStorage.setItem(
      SITE_SCENARIO_STORAGE_KEY,
      JSON.stringify({
        version: SITE_SCENARIO_LIBRARY_VERSION,
        scenarios: records.slice(0, SITE_SCENARIO_LIMIT),
      })
    );
    return true;
  } catch (error) {
    toast(`Could not save site scenarios: ${error.message}`, true);
    return false;
  }
}

function updateSiteSavedButtons() {
  const selected = $("site-saved-select").value;
  $("site-load").disabled = !selected;
  $("site-delete").disabled = !selected;
}

function refreshSiteScenarioSelect(selectedName = null) {
  const select = $("site-saved-select");
  if (!select) return;
  const records = readSiteScenarioLibrary();
  const current = selectedName || "";
  select.innerHTML =
    `<option value="">${records.length ? "— choose a saved scenario —" : "— no saved scenarios —"}</option>` +
    records
      .map((record) => `<option value="${escapeHtml(record.name)}">${escapeHtml(record.name)}</option>`)
      .join("");
  if (current && records.some((record) => record.name === current)) {
    select.value = current;
    $("site-saved-name").value = current;
  }
  updateSiteSavedButtons();
  $("site-saved-meta").textContent = `${records.length} saved scenario${records.length === 1 ? "" : "s"} in this browser.`;
  renderSiteComparison();
}

function currentSiteScenarioRecord(name) {
  const scenario = state.siteScenario;
  const count = Math.max(1, Math.round(Number($("site-count").value || 1)));
  return normalizeSiteScenarioRecord({
    version: SITE_SCENARIO_LIBRARY_VERSION,
    name,
    dataset_id: state.dataset?.dataset_id || "",
    candidates_schema: scenario.candidatesSchema,
    created_at: new Date().toISOString(),
    selected: [...scenario.selected],
    assumptions: {
      species: $("site-species").value,
      height_m: Number($("site-height").value || 8),
      crown_radius_m: Number($("site-crown").value || 3),
      count,
      cost_cad: Number($("site-cost").value || 0),
      water_l_per_year: Number($("site-water").value || 0),
      maintenance: $("site-maintenance").value,
    },
    settings: {
      date: $("site-date").value,
      time: $("site-time").value,
      target_height_m: Number($("site-target-height").value || 1.5),
      sensitivity: $("site-sensitivity").checked,
    },
    evaluation: siteEvaluationSummary(),
  });
}

function saveSiteScenario() {
  if (!state.siteScenario.selected.size) {
    toast("Select at least one candidate site first.", true);
    return;
  }
  const name = $("site-saved-name").value.trim();
  if (!name) {
    toast("Name the scenario before saving.", true);
    return;
  }
  const record = currentSiteScenarioRecord(name);
  if (!record) {
    toast("Could not validate the current scenario.", true);
    return;
  }
  const records = [
    record,
    ...readSiteScenarioLibrary().filter((item) => item.name !== record.name),
  ].slice(0, SITE_SCENARIO_LIMIT);
  if (!writeSiteScenarioLibrary(records)) return;
  state.siteScenario.savedName = record.name;
  refreshSiteScenarioSelect(record.name);
  toast(`Saved scenario “${record.name}”`);
}

function loadSiteScenario() {
  const name = $("site-saved-select").value;
  if (!name) {
    toast("Choose a saved scenario first.", true);
    return;
  }
  const record = readSiteScenarioLibrary().find((item) => item.name === name);
  if (!record) {
    toast("That saved scenario is no longer available.", true);
    refreshSiteScenarioSelect();
    return;
  }
  if (record.dataset_id !== (state.dataset?.dataset_id || "")) {
    toast("This scenario belongs to a different dataset.", true);
    return;
  }
  if (
    record.candidates_schema &&
    state.siteScenario.candidatesSchema &&
    record.candidates_schema !== state.siteScenario.candidatesSchema
  ) {
    toast("This scenario belongs to a different candidate schema.", true);
    return;
  }
  if (record.selected.some((siteId) => !state.siteScenario.candidates.has(siteId))) {
    toast("This scenario contains candidate sites that are not available.", true);
    return;
  }
  state.siteScenario.selected = new Set(record.selected);
  $("site-species").value = record.assumptions.species;
  $("site-height").value = String(record.assumptions.height_m);
  $("site-crown").value = String(record.assumptions.crown_radius_m);
  $("site-count").value = String(record.assumptions.count);
  $("site-cost").value = String(record.assumptions.cost_cad);
  $("site-water").value = String(record.assumptions.water_l_per_year);
  $("site-maintenance").value = record.assumptions.maintenance;
  $("site-date").value = record.settings.date;
  $("site-time").value = record.settings.time;
  $("site-target-height").value = String(record.settings.target_height_m);
  $("site-sensitivity").checked = record.settings.sensitivity;
  $("site-preset").value = "custom";
  state.siteScenario.savedName = record.name;
  state.siteScenario.evaluation = record.evaluation ? { ...record.evaluation, per_site: [] } : null;
  updateSiteSelectedSource();
  renderSiteSelection();
  refreshSiteScenarioSelect(record.name);
  if (record.evaluation) {
    renderSiteEvaluation({ evaluation: record.evaluation });
    $("site-status").textContent = "saved scenario";
    $("site-results").insertAdjacentHTML(
      "beforeend",
      '<p class="hint">Cached summary from the saved scenario. Evaluate again to refresh per-site and sensitivity results.</p>'
    );
  } else {
    $("site-scenario-summary").innerHTML = "";
    $("site-results").innerHTML = "";
    $("site-status").textContent = "ready";
  }
}

function renderSiteComparison() {
  const container = $("site-comparison");
  if (!container) return;
  const datasetId = state.dataset?.dataset_id || "";
  const schema = state.siteScenario.candidatesSchema || "";
  const records = readSiteScenarioLibrary()
    .filter(
      (record) =>
        record.evaluation &&
        record.dataset_id === datasetId &&
        (!schema || record.candidates_schema === schema)
    )
    .sort((first, second) => first.name.localeCompare(second.name));
  if (!records.length) {
    container.innerHTML =
      '<p class="site-comparison-note">Save evaluated scenarios to compare them here. Rows are not ranked.</p>';
    return;
  }
  const rows = records
    .map((record) => {
      const evaluation = record.evaluation;
      const trees = record.selected.length * record.assumptions.count;
      const cost = trees * record.assumptions.cost_cad;
      const water = trees * record.assumptions.water_l_per_year;
      const deltaPct =
        evaluation.delta_shade_pct == null
          ? "n/a"
          : `${evaluation.delta_shade_pct >= 0 ? "+" : ""}${Number(evaluation.delta_shade_pct).toFixed(4)}%`;
      return `<tr><td>${escapeHtml(record.name)}</td><td>${formatNumber(record.selected.length)}</td><td>${formatNumber(trees)}</td><td>${formatCompact(evaluation.baseline_shade_m2h, " m²h")}</td><td>${formatCompact(evaluation.scenario_shade_m2h, " m²h")}</td><td>${formatSiteDelta(evaluation.delta_shade_m2h)}</td><td>${deltaPct}</td><td>C$${formatNumber(cost)}</td><td>${formatNumber(water)} L</td></tr>`;
    })
    .join("");
  container.innerHTML = `
    <table><thead><tr><th>Scenario</th><th>Sites</th><th>Trees</th><th>Baseline</th><th>Scenario</th><th>Δ</th><th>Δ %</th><th>Cost</th><th>Water</th></tr></thead><tbody>${rows}</tbody></table>
    <p class="site-comparison-note">Saved evaluated scenarios for this dataset. Neutral name order; not a ranking or recommendation.</p>`;
}

function exportSiteScenarios() {
  const records = readSiteScenarioLibrary();
  if (!records.length) {
    toast("No saved scenarios to export.", true);
    return;
  }
  downloadText(
    JSON.stringify(
      {
        version: SITE_SCENARIO_LIBRARY_VERSION,
        exported_at: new Date().toISOString(),
        scenarios: records,
      },
      null,
      2
    ),
    "fresh-site-scenarios.json",
    "application/json"
  );
  toast(`Exported ${records.length} saved scenarios`);
}

async function importSiteScenarios(event) {
  const input = event.target;
  const file = input.files?.[0];
  if (!file) return;
  try {
    if (file.size > SITE_SCENARIO_IMPORT_LIMIT) {
      toast("That scenario file is too large.", true);
      return;
    }
    const payload = JSON.parse(await file.text());
    if (
      !payload ||
      payload.version !== SITE_SCENARIO_LIBRARY_VERSION ||
      !Array.isArray(payload.scenarios) ||
      payload.scenarios.length > SITE_SCENARIO_LIMIT
    ) {
      toast("That JSON file is not a valid version 1 site-scenario library.", true);
      return;
    }
    const imported = [];
    for (const entry of payload.scenarios) {
      const record = normalizeSiteScenarioRecord(entry);
      if (!record) {
        toast("That JSON file contains an invalid site scenario.", true);
        return;
      }
      imported.push(record);
    }
    const merged = new Map(readSiteScenarioLibrary().map((record) => [record.name, record]));
    for (const record of imported) merged.set(record.name, record);
    const records = Array.from(merged.values()).slice(0, SITE_SCENARIO_LIMIT);
    if (!writeSiteScenarioLibrary(records)) return;
    refreshSiteScenarioSelect();
    toast(`Imported ${imported.length} scenarios; ${records.length} saved locally`);
  } catch (error) {
    toast(`Could not import site scenarios: ${error.message}`, true);
  } finally {
    input.value = "";
  }
}

function deleteSiteScenario() {
  const name = $("site-saved-select").value;
  if (!name) {
    toast("Choose a saved scenario first.", true);
    return;
  }
  const records = readSiteScenarioLibrary().filter((record) => record.name !== name);
  if (!writeSiteScenarioLibrary(records)) return;
  if (state.siteScenario.savedName === name) state.siteScenario.savedName = null;
  refreshSiteScenarioSelect();
  toast(`Deleted scenario “${name}”`);
}

function siteFeatureCollection() {
  const features = [];
  for (const siteId of state.siteScenario.selected) {
    const site = state.siteScenario.candidates.get(siteId);
    if (!site) continue;
    features.push({
      type: "Feature",
      properties: {
        site_id: site.site_id,
        action_class: site.action_class,
        action_label: site.action_label,
      },
      geometry: { type: "Point", coordinates: [site.lon, site.lat] },
    });
  }
  return { type: "FeatureCollection", features };
}

function siteCandidateColor() {
  return [
    "match",
    ["get", "action_class"],
    "plant_cool",
    "#377e22",
    "expand_canopy",
    "#e6911e",
    "structural_shade",
    "#3182bd",
    "protect_loss",
    "#c51b7d",
    "#8c8c8c",
  ];
}

async function ensureSitesView() {
  const scenario = state.siteScenario;
  if (scenario.map) {
    scenario.map.resize();
    return;
  }
  if (scenario.loading) return;
  scenario.loading = true;
  $("site-status").textContent = "loading";
  try {
    const payload = await api("api/site-candidates");
    scenario.candidates = new Map(
      (payload.sites || []).map((record) => [String(record.site_id), record])
    );
    scenario.candidatesSchema = String(payload.schema_version || "");
    const [west, south, east, north] = state.scene.bounds_wgs84;
    const coordinates = state.scene.corners_wgs84 || [
      [west, north],
      [east, north],
      [east, south],
      [west, south],
    ];
    const map = new maplibregl.Map({
      container: "map-sites",
      style: {
        version: 8,
        sources: {
          hillshade: { type: "image", url: "api/hillshade.png?width=1400", coordinates },
          canopy: { type: "image", url: "api/canopy.png?width=1400", coordinates },
          buildings: { type: "geojson", data: buildingFeatures() },
          roads: {
            type: "geojson",
            data: state.roads || { type: "FeatureCollection", features: [] },
          },
          boundary: { type: "geojson", data: boundaryFeatures() },
          siteCandidates: { type: "geojson", data: "api/site-candidates.geojson" },
          siteSelected: { type: "geojson", data: siteFeatureCollection() },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#e6eae2" } },
          {
            id: "hillshade",
            type: "raster",
            source: "hillshade",
            paint: { "raster-opacity": 0.32, "raster-resampling": "linear" },
          },
          {
            id: "canopy",
            type: "raster",
            source: "canopy",
            paint: { "raster-opacity": 0.46, "raster-resampling": "linear" },
          },
          {
            id: "roads",
            type: "line",
            source: "roads",
            paint: { "line-color": "#7b8479", "line-width": 0.8, "line-opacity": 0.65 },
          },
          {
            id: "buildings",
            type: "fill",
            source: "buildings",
            paint: { "fill-color": "#b6beb3", "fill-opacity": 0.82 },
          },
          {
            id: "site-candidates",
            type: "circle",
            source: "siteCandidates",
            paint: {
              "circle-color": siteCandidateColor(),
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 2.5, 16, 6],
              "circle-opacity": 0.82,
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 0.7,
            },
          },
          {
            id: "site-selected",
            type: "circle",
            source: "siteSelected",
            paint: {
              "circle-color": "#17231d",
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 5, 16, 10],
              "circle-stroke-color": "#ffffff",
              "circle-stroke-width": 2,
            },
          },
          {
            id: "boundary",
            type: "line",
            source: "boundary",
            paint: { "line-color": "#2f6b4f", "line-width": 1.1, "line-dasharray": [2, 2] },
          },
        ],
      },
      center: [(west + east) / 2, (south + north) / 2],
      zoom: 12,
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
      applySiteFilter();
      updateSiteSelectedSource();
    });
    const toggle = (event) => {
      const feature = event.features?.[0];
      const siteId = feature?.properties?.site_id;
      if (siteId) toggleSiteSelection(String(siteId));
    };
    map.on("click", "site-candidates", toggle);
    map.on("click", "site-selected", toggle);
    map.on("mousemove", "site-candidates", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "site-candidates", () => {
      map.getCanvas().style.cursor = "";
    });
    scenario.map = map;
    scenario.loading = false;
    $("site-status").textContent = `${scenario.candidates.size} candidates`;
    renderSiteSelection();
    renderSiteComparison();
  } catch (error) {
    scenario.loading = false;
    $("site-status").textContent = "unavailable";
    toast(`Could not load candidate sites: ${error.message}`, true);
  }
}

function applySiteFilter() {
  const map = state.siteScenario.map;
  if (!map || !map.getLayer("site-candidates")) return;
  const value = $("site-action-filter").value;
  map.setFilter("site-candidates", value === "all" ? null : ["==", ["get", "action_class"], value]);
}

function updateSiteSelectedSource() {
  const map = state.siteScenario.map;
  if (!map) return;
  const source = map.getSource("siteSelected");
  if (source) source.setData(siteFeatureCollection());
}

function toggleSiteSelection(siteId) {
  const scenario = state.siteScenario;
  if (!scenario.candidates.has(siteId)) return;
  if (scenario.selected.has(siteId)) scenario.selected.delete(siteId);
  else scenario.selected.add(siteId);
  invalidateSiteEvaluation();
  updateSiteSelectedSource();
  renderSiteSelection();
}

function selectSixSiteCandidates() {
  const scenario = state.siteScenario;
  const candidates = [...scenario.candidates.values()];
  const preferred = candidates.filter((site) => site.action_class === "plant_cool");
  const chosen = (preferred.length ? preferred : candidates).slice(0, 6);
  scenario.selected = new Set(chosen.map((site) => site.site_id));
  invalidateSiteEvaluation();
  updateSiteSelectedSource();
  renderSiteSelection();
  if (!chosen.length) toast("No candidate sites are available.", true);
}

function clearSiteSelection() {
  state.siteScenario.selected.clear();
  invalidateSiteEvaluation();
  updateSiteSelectedSource();
  renderSiteSelection();
  $("site-status").textContent = `${state.siteScenario.candidates.size} candidates`;
}

function invalidateSiteEvaluation() {
  state.siteScenario.evaluation = null;
  state.siteScenario.scenario = null;
  $("site-scenario-summary").innerHTML = "";
  $("site-results").innerHTML = "";
  if (state.siteScenario.selected.size) $("site-status").textContent = "ready";
}

function renderSiteSelection() {
  const scenario = state.siteScenario;
  const selected = [...scenario.selected]
    .map((siteId) => scenario.candidates.get(siteId))
    .filter(Boolean);
  const count = Math.max(1, Math.round(Number($("site-count").value || 1)));
  const cost = Math.max(0, Number($("site-cost").value || 0));
  const water = Math.max(0, Number($("site-water").value || 0));
  const trees = selected.length * count;
  $("site-selection-summary").textContent = selected.length
    ? `${selected.length} site${selected.length === 1 ? "" : "s"} · ${formatNumber(trees)} trees · C$${formatNumber(trees * cost)} · ${formatNumber(trees * water)} L/yr`
    : "Click candidate sites on the map to add or remove them.";
  $("site-evaluate").disabled = scenario.busy || !selected.length;
  $("site-open-3d").disabled = scenario.busy || !selected.length;
}

function siteWhenIso() {
  const date = $("site-date").value || "2026-06-21";
  const time = $("site-time").value || "12:00";
  const approx = new Date(`${date}T${time}:00Z`);
  const zone = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Vancouver",
    timeZoneName: "longOffset",
  })
    .formatToParts(approx)
    .find((part) => part.type === "timeZoneName")?.value;
  const offset = zone?.replace("GMT", "") || "-07:00";
  const parsed = new Date(`${date}T${time}:00${offset}`);
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
}

function buildSiteScenarioPayload() {
  const scenario = state.siteScenario;
  const count = Math.max(1, Math.round(Number($("site-count").value || 1)));
  const height = Number($("site-height").value || 8);
  const crown = Number($("site-crown").value || 3);
  const cost = Number($("site-cost").value || 0);
  const water = Number($("site-water").value || 0);
  const species = $("site-species").value.trim() || "Acer rubrum";
  const maintenance = $("site-maintenance").value.trim() || "unspecified";
  const sites = [...scenario.selected]
    .map((siteId) => scenario.candidates.get(siteId))
    .filter(Boolean)
    .map((site) => ({
      site_id: site.site_id,
      species,
      height_m: height,
      crown_radius_m: crown,
      count,
      cost_cad: cost,
      water_l_per_year: water,
      maintenance,
      assumption_source: "browser scenario input",
    }));
  return {
    schema_version: "fresh-urban-forest.site-scenario.v1",
    scenario_id: `scenario-site-${Date.now().toString(36)}`,
    label: "Site planting scenario",
    created_at: new Date().toISOString(),
    settings: {
      date: $("site-date").value,
      time: $("site-time").value,
      target_height_m: Number($("site-target-height").value || 1.5),
    },
    sites,
  };
}

async function evaluateSiteScenario() {
  const scenario = state.siteScenario;
  if (!scenario.selected.size || scenario.busy) return;
  scenario.busy = true;
  renderSiteSelection();
  $("site-status").textContent = "evaluating";
  $("site-results").innerHTML = '<p class="hint">Running baseline and scenario shadow accumulation...</p>';
  try {
    const document = buildSiteScenarioPayload();
    const payload = await api("api/site-scenario/evaluate", {
      method: "POST",
      body: JSON.stringify({
        scenario: document,
        whens: [siteWhenIso()],
        target_height_m: Number($("site-target-height").value || 1.5),
        include_per_site: true,
        include_sensitivity: $("site-sensitivity").checked,
      }),
    });
    scenario.evaluation = payload.evaluation;
    scenario.scenario = payload.scenario;
    renderSiteEvaluation(payload);
    $("site-status").textContent = "evaluated";
  } catch (error) {
    $("site-status").textContent = "error";
    $("site-results").innerHTML = `<p class="hint">Evaluation failed: ${escapeHtml(error.message)}</p>`;
    toast(`Site scenario failed: ${error.message}`, true);
  } finally {
    scenario.busy = false;
    renderSiteSelection();
  }
}

function formatSiteDelta(value, digits = 0) {
  const number = Number(value || 0);
  return `${number >= 0 ? "+" : ""}${formatNumber(number, digits)}`;
}

function renderSiteEvaluation(payload) {
  const evaluation = payload.evaluation || payload;
  const baseline = Number(evaluation.baseline_shade_m2h || 0);
  const scenario = Number(evaluation.scenario_shade_m2h || 0);
  const delta = Number(evaluation.delta_shade_m2h || 0);
  const percent = evaluation.delta_shade_pct;
  const deltaClass = delta >= 0 ? "gain" : "loss";
  $("site-scenario-summary").innerHTML = `
    <div class="change-stat"><span>Baseline</span><strong>${formatCompact(baseline, " m²h")}</strong></div>
    <div class="change-stat"><span>Scenario</span><strong>${formatCompact(scenario, " m²h")}</strong></div>
    <div class="change-stat ${deltaClass}"><span>Delta</span><strong>${formatCompact(delta, " m²h")}</strong></div>
    <div class="change-stat ${deltaClass}"><span>Delta</span><strong>${percent == null ? "n/a" : `${delta >= 0 ? "+" : ""}${Number(percent).toFixed(4)}%`}</strong></div>`;
  const rows = (evaluation.per_site || [])
    .map(
      (site) => `<tr><td>${escapeHtml(String(site.site_id))}</td><td>${formatNumber(site.trees)}</td><td>${formatSiteDelta(site.delta_shade_m2h)}</td><td>${site.delta_shade_pct == null ? "n/a" : `${site.delta_shade_pct >= 0 ? "+" : ""}${Number(site.delta_shade_pct).toFixed(4)}%`}</td></tr>`
    )
    .join("");
  const sensitivity = (evaluation.sensitivity || [])
    .map(
      (entry) => `<tr><td>${escapeHtml(String(entry.case))}</td><td>${formatNumber(entry.height_scale, 2)}</td><td>${formatNumber(entry.crown_scale, 2)}</td><td>${formatSiteDelta(entry.delta_shade_m2h)}</td></tr>`
    )
    .join("");
  $("site-results").innerHTML = `
    <table><thead><tr><th>Site</th><th>Trees</th><th>Δ m²h</th><th>Δ %</th></tr></thead><tbody>${rows}</tbody></table>
    ${sensitivity ? `<p class="hint">Height / crown sensitivity</p><table><thead><tr><th>Case</th><th>Height</th><th>Crown</th><th>Δ m²h</th></tr></thead><tbody>${sensitivity}</tbody></table>` : ""}
    <p class="hint"><strong>${escapeHtml(String(evaluation.method || "shadow model"))}</strong> · ${escapeHtml(String(evaluation.uncertainty?.status || "scenario screen"))} · not an observed outcome.</p>`;
}

async function openSiteScenario3D() {
  const scenario = state.siteScenario;
  if (!scenario.selected.size || scenario.busy) return;
  const count = Math.max(1, Math.round(Number($("site-count").value || 1)));
  const height = Number($("site-height").value || 8);
  const crown = Number($("site-crown").value || 3);
  const species = $("site-species").value.trim() || "Acer rubrum";
  const edits = [];
  for (const siteId of scenario.selected) {
    const site = scenario.candidates.get(siteId);
    if (!site) continue;
    for (let index = 0; index < count; index += 1) {
      edits.push({
        kind: "plant",
        tree_id: `p48-${site.site_id}-${index}`,
        lon: site.lon,
        lat: site.lat,
        species,
        common_name: species,
        dbh_cm: 8,
        height_m: height,
        crown_width_m: crown * 2,
        note: "P48 hypothetical site scenario",
      });
    }
  }
  if (!edits.length) return;
  if (edits.length > 1000) {
    toast("That scenario is too large for the 3D preview.", true);
    return;
  }
  scenario.busy = true;
  renderSiteSelection();
  $("site-status").textContent = "opening 3D";
  try {
    const created = await api("/api/scenarios", {
      method: "POST",
      body: JSON.stringify({ name: "P48 site scenario", years: 0, edits }),
    });
    await refreshScenarioOptions();
    await loadScenario(created.scenario_id);
  } catch (error) {
    $("site-status").textContent = "3D error";
    toast(`Could not open scenario in 3D: ${error.message}`, true);
  } finally {
    scenario.busy = false;
    renderSiteSelection();
  }
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
        offInventory: {
          type: "geojson",
          data: state.dataset?.has_off_inventory
            ? "api/off-inventory.geojson"
            : offInventoryFeatures(),
        },
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

async function exportLabReport() {
  try {
    const params = new URLSearchParams();
    if (state.scenarioId) {
      params.set("scenario_id", state.scenarioId);
      params.set("year", String(state.previewYear || state.years));
    }
    const payload = await api(`api/report${params.toString() ? `?${params}` : ""}`);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = state.scenarioId ? `${state.scenarioId}-lab-report.json` : "baseline-lab-report.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    toast("Lab report exported");
  } catch (error) {
    toast(`Could not export the report: ${error.message}`, true);
  }
}

async function loadBirds() {
  if (state.birdsLoading) return;
  state.birdsLoading = true;
  try {
    const params = new URLSearchParams();
    if (state.scenarioId) {
      params.set("scenario_id", state.scenarioId);
      params.set("year", String(state.previewYear || state.years));
    }
    const payload = await api(`api/birds${params.toString() ? `?${params}` : ""}`);
    state.birds = payload;
    renderBirds(payload);
  } catch (error) {
    $("birds-note").textContent = `Bird view unavailable: ${error.message}`;
  } finally {
    state.birdsLoading = false;
  }
}

function renderBirds(payload) {
  const metrics = payload.metrics || {};
  $("birds-metrics").innerHTML = `
    <div class="bird-metric-grid">
      <div><span>Habitat score</span><strong>${formatNumber(Number(metrics.habitat_score || 0), 2)}</strong></div>
      <div><span>P95 height</span><strong>${formatNumber(Number(metrics.p95_height_m || 0), 1)} m</strong></div>
      <div><span>Foliage diversity</span><strong>${formatNumber(Number(metrics.foliage_height_diversity || 0), 2)}</strong></div>
      <div><span>Layers</span><strong>${formatNumber(Number(metrics.layering_count || 0))}</strong></div>
      <div><span>Gap fraction</span><strong>${formatNumber(Number(metrics.gap_fraction || 0) * 100, 0)}%</strong></div>
      <div><span>Native share</span><strong>${formatNumber(Number(metrics.native_fraction || 0) * 100, 0)}%</strong></div>
    </div>
    ${evidenceBadge(payload.evidence || {})}`;
  const guilds = payload.guilds || [];
  $("birds-guilds").innerHTML = guilds
    .map(
      (item) => `<div class="guild-row">
        <div class="guild-meta"><span>${escapeHtml(item.guild.label)}</span><code>${formatNumber(Number(item.relative_abundance_index || 0), 1)}</code></div>
        <div class="bar-track"><div class="bar-fill" style="width:${Number(item.suitability || 0) * 100}%"></div></div>
        <small>suitability ${formatNumber(Number(item.suitability || 0), 2)} · λ ${formatNumber(Number(item.demography?.lambda || 0), 2)}</small>
      </div>`
    )
    .join("");
  const select = $("birds-guild-select");
  const current = select.value;
  select.innerHTML = guilds
    .map((item, index) => `<option value="${index}">${escapeHtml(item.guild.label)}</option>`)
    .join("");
  select.value = current && Number(current) < guilds.length ? current : "0";
  select.onchange = () => renderBirdsGuild(guilds[Number(select.value) || 0]);
  renderBirdsGuild(guilds[Number(select.value) || 0]);
  $("birds-note").textContent = payload.caveat || "Relative abundance is a screening index, not a density.";
}

function renderBirdsGuild(item) {
  if (!item) return;
  const demo = item.demography || {};
  const range = demo.prior_range || [0, 0];
  $("birds-demography").innerHTML = `
    <div class="bird-metric-grid">
      <div><span>Lambda</span><strong>${formatNumber(Number(demo.lambda || 0), 2)}</strong></div>
      <div><span>Prior range</span><strong>${formatNumber(Number(range[0] || 0), 2)}–${formatNumber(Number(range[1] || 0), 2)}</strong></div>
      <div><span>Stable adult share</span><strong>${formatNumber(Number(demo.stable_adult_fraction || 0) * 100, 0)}%</strong></div>
      <div><span>Adult survival sensitivity</span><strong>${formatNumber(Number(demo.sensitivity?.adult_survival || 0), 2)}</strong></div>
    </div>
    <p class="hint">${escapeHtml((item.limiting_factors || []).length ? `Limiting: ${(item.limiting_factors || []).join(", ")}` : "No structural factor is below 0.4.")}</p>`;
  renderBirdsChart(demo.survival_curve || []);
}

function renderBirdsChart(values) {
  const svg = $("birds-chart");
  const width = 640;
  const height = 220;
  const padding = { left: 38, right: 14, top: 18, bottom: 28 };
  const pointCount = Math.max(values.length, 2);
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const x = (index) => padding.left + (index / Math.max(pointCount - 1, 1)) * plotWidth;
  const y = (value) => padding.top + plotHeight - Math.max(0, Math.min(1, value)) * plotHeight;
  const points = values
    .map((value, index) => `${index === 0 ? "M" : "L"}${x(index).toFixed(1)},${y(Number(value)).toFixed(1)}`)
    .join(" ");
  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((fraction) => {
      const position = y(fraction);
      return `<line x1="${padding.left}" y1="${position}" x2="${width - padding.right}" y2="${position}" stroke="#e6ebe1" stroke-width="1"/>
        <text x="${padding.left - 7}" y="${position + 4}" text-anchor="end" font-size="10" fill="#6b7a70">${fraction.toFixed(2)}</text>`;
    })
    .join("");
  svg.innerHTML = `${grid}<path d="${points}" fill="none" stroke="#2f6b4f" stroke-width="2.5"></path>
    <text x="${padding.left}" y="${height - 8}" font-size="10" fill="#6b7a70">year 0</text>
    <text x="${width - padding.right}" y="${height - 8}" text-anchor="end" font-size="10" fill="#6b7a70">year ${values.length - 1}</text>`;
}

function initOptimizeControls() {
  $("optimize-run").addEventListener("click", runOptimization);
  $("optimize-load-saved").addEventListener("click", () => loadSavedArchive());
  $("optimize-rename").addEventListener("click", renameSavedArchive);
  $("optimize-delete-saved").addEventListener("click", deleteSavedArchive);
  $("opt-saved").addEventListener("change", () => {
    const job = state.optimize.savedRuns.find((item) => item.job_id === $("opt-saved").value);
    if (job) updateSavedArchiveMeta(job);
  });
  $("optimize-reset").addEventListener("click", resetParetoView);
  $("pareto-load").addEventListener("click", loadParetoScenario);
  $("pareto-pin").addEventListener("click", pinSelectedSolution);
  $("pareto-clear-pins").addEventListener("click", clearPinnedSolutions);
  refreshSavedRuns();
  for (const id of ["pareto-x", "pareto-y", "pareto-z", "pareto-colour", "pareto-size"]) {
    $(id).addEventListener("change", drawPareto);
  }
  $("pareto-slice-objective").addEventListener("change", drawPareto);
  $("pareto-slice").addEventListener("input", () => {
    const value = Number($("pareto-slice").value) / 100;
    $("pareto-slice-value").textContent = value <= 0 ? "all" : `>= ${value.toFixed(2)}`;
    drawPareto();
  });
  $("pareto-floor").addEventListener("input", () => {
    const value = Number($("pareto-floor").value) / 100;
    $("pareto-floor-value").textContent = value <= 0 ? "all" : `>= ${value.toFixed(2)}`;
    drawPareto();
    persistParetoViewState();
  });
  $("pareto-reference").addEventListener("click", setParetoReference);
  $("pareto-clear-reference").addEventListener("click", clearParetoReference);
  $("pareto-copy-link").addEventListener("click", copyParetoLink);
  $("pareto-download-csv").addEventListener("click", downloadParetoCsv);
  $("parallel-clear-brush").addEventListener("click", clearParallelBrushes);
  $("pareto-view-save").addEventListener("click", saveParetoView);
  $("pareto-view-load").addEventListener("click", loadParetoView);
  $("pareto-view-delete").addEventListener("click", deleteParetoView);
  $("pareto-view-export").addEventListener("click", exportParetoViews);
  $("pareto-view-copy").addEventListener("click", copyParetoPresetLink);
  $("pareto-view-import").addEventListener("change", importParetoViews);
  $("pareto-view-select").addEventListener("change", () => {
    $("pareto-view-name").value = $("pareto-view-select").value;
    updateParetoViewButtons();
  });
  refreshParetoViewSelect();
  initParallelEvents();
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
  const axes = buildParetoAxes();
  scene.add(axes);
  const markerMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true, opacity: 0.95 });
  const referenceMaterial = new THREE.MeshBasicMaterial({ color: 0xffd24a, depthTest: false, transparent: true, opacity: 0.95 });
  const marker = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 12), markerMaterial);
  const referenceMarker = new THREE.Mesh(new THREE.SphereGeometry(0.075, 16, 12), referenceMaterial);
  marker.renderOrder = 10;
  referenceMarker.renderOrder = 9;
  marker.visible = false;
  referenceMarker.visible = false;
  scene.add(marker, referenceMarker);
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  canvas.addEventListener("pointermove", (event) => {
    if (!state.optimize.mesh) {
      $("pareto-tooltip").hidden = true;
      return;
    }
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObject(state.optimize.mesh, false);
    if (!hits.length) {
      $("pareto-tooltip").hidden = true;
      return;
    }
    const index = hits[0].instanceId;
    const solutions = state.optimize.mesh.userData.solutions || [];
    const solution = index !== undefined ? solutions[index] : null;
    if (!solution) {
      $("pareto-tooltip").hidden = true;
      return;
    }
    showParetoTooltip(solution, event);
  });
  canvas.addEventListener("pointerleave", () => {
    $("pareto-tooltip").hidden = true;
  });
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
  const chart = { renderer, scene, camera, controls, canvas, mesh: null, axes, marker, referenceMarker };
  window.addEventListener("resize", () => {
    if (!chart.canvas.clientWidth) return;
    renderer.setSize(chart.canvas.clientWidth, Math.max(chart.canvas.clientHeight, 1), false);
    camera.aspect = chart.canvas.clientWidth / Math.max(chart.canvas.clientHeight, 1);
    camera.updateProjectionMatrix();
  });
  state.optimize.chart = chart;
  updateParetoAxes(chart, { x: "X", y: "Y", z: "Z" });
  animatePareto();
  return chart;
}

function buildParetoAxes() {
  const group = new THREE.Group();
  const origin = new THREE.Vector3(0, 0, 0);
  const end = 1.8;
  const axes = [
    [new THREE.Vector3(end, 0, 0), 0xc85555],
    [new THREE.Vector3(0, end, 0), 0x5f9f54],
    [new THREE.Vector3(0, 0, end), 0x4d7fc4],
  ];
  for (const [target, colour] of axes) {
    const geometry = new THREE.BufferGeometry().setFromPoints([origin, target]);
    const material = new THREE.LineBasicMaterial({ color: colour, transparent: true, opacity: 0.9 });
    group.add(new THREE.Line(geometry, material));
    const cone = new THREE.Mesh(
      new THREE.ConeGeometry(0.07, 0.2, 10),
      new THREE.MeshBasicMaterial({ color: colour })
    );
    cone.position.copy(target);
    cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), target.clone().sub(origin).normalize());
    group.add(cone);
  }
  return group;
}

function updateParetoAxes(chart, labels) {
  chart.axisLabelText = labels;
  $("pareto-axis-x").textContent = `X: ${labels.x || "X"}`;
  $("pareto-axis-y").textContent = `Y: ${labels.y || "Y"}`;
  $("pareto-axis-z").textContent = `Z: ${labels.z || "Z"}`;
}

function positionParetoAxisLabels(chart) {
  if (!chart.axisLabelText) return;
  const endpoints = [
    [2.08, 0, 0],
    [0, 2.08, 0],
    [0, 0, 2.08],
  ];
  const ids = ["pareto-axis-x", "pareto-axis-y", "pareto-axis-z"];
  const point = new THREE.Vector3();
  endpoints.forEach((endpoint, index) => {
    point.set(endpoint[0], endpoint[1], endpoint[2]);
    point.project(chart.camera);
    const element = $(ids[index]);
    if (point.z > 1) {
      element.style.display = "none";
      return;
    }
    element.style.display = "";
    const panel = document.querySelector(".optimize-panel");
    const panelRect = panel?.getBoundingClientRect();
    const canvasRect = chart.canvas.getBoundingClientRect();
    const minLeft = panelRect
      ? panelRect.right - canvasRect.left + element.offsetWidth / 2 + 8
      : 8 + element.offsetWidth / 2;
    const maxLeft = chart.canvas.clientWidth - element.offsetWidth / 2 - 8;
    const left = Math.max(minLeft, Math.min(maxLeft, (point.x * 0.5 + 0.5) * chart.canvas.clientWidth));
    const top = Math.max(
      12,
      Math.min(chart.canvas.clientHeight - 12, (-point.y * 0.5 + 0.5) * chart.canvas.clientHeight)
    );
    element.style.left = `${left}px`;
    element.style.top = `${top}px`;
  });
}

function animatePareto() {
  const chart = state.optimize.chart;
  if (!chart) return;
  chart.controls.update();
  positionParetoAxisLabels(chart);
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
    state.optimize.presetName = null;
    state.optimize.pinned = [];
    const params = new URLSearchParams(location.search);
    params.delete("opt_preset");
    history.replaceState(null, "", `${params.toString() ? `?${params.toString()}` : ""}${location.hash || "#optimize"}`);
    $("pareto-load").disabled = true;
    $("pareto-pin").disabled = true;
    $("pareto-clear-pins").disabled = true;
    $("pareto-compare").innerHTML = "";
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
      refreshSavedRuns();
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

async function refreshSavedRuns() {
  try {
    const payload = await api("api/optimize");
    const jobs = (payload.jobs || []).filter((job) => job.status === "done");
    state.optimize.savedRuns = jobs;
    const select = $("opt-saved");
    const current = select.value || state.optimize.jobId || "";
    select.innerHTML = jobs.length
      ? jobs
          .map(
            (job) =>
              `<option value="${escapeHtml(job.job_id)}">${escapeHtml(job.name || job.job_id)} · ${formatNumber(job.archive_size)} solutions · HV ${formatNumber(job.hypervolume || 0, 4)}</option>`
          )
          .join("")
      : '<option value="">No saved runs yet — run one first</option>';
    if (jobs.some((job) => job.job_id === current)) select.value = current;
    if (jobs.length) {
      const selected = jobs.find((job) => job.job_id === select.value) || jobs[0];
      select.value = selected.job_id;
      updateSavedArchiveMeta(selected);
      const urlJob = new URLSearchParams(location.search).get("opt_job");
      if (!state.optimize.result && urlJob && jobs.some((job) => job.job_id === urlJob)) {
        select.value = urlJob;
        await loadSavedArchive(urlJob);
      }
    } else {
      updateSavedArchiveMeta(null);
    }
    $("optimize-load-saved").disabled = jobs.length === 0;
  } catch (_error) {
    $("opt-saved").innerHTML = '<option value="">Saved runs unavailable</option>';
    $("optimize-load-saved").disabled = true;
    updateSavedArchiveMeta(null);
  }
}

function updateSavedArchiveMeta(job) {
  const enabled = Boolean(job);
  $("optimize-rename").disabled = !enabled;
  $("optimize-delete-saved").disabled = !enabled;
  if (!job) {
    $("opt-archive-name").value = "";
    $("opt-saved-meta").textContent = "A scenario is one plan. A saved run loads the whole Pareto front.";
    return;
  }
  $("opt-archive-name").value = job.name || job.job_id;
  const parts = [
    job.dataset_id || "dataset",
    `${formatNumber(job.horizon)}-year`,
    `$${formatNumber(job.budget_cad)} budget`,
    `max ${formatNumber(job.max_sites)} sites`,
  ];
  if (job.saved_utc) parts.push(job.saved_utc.slice(0, 10));
  $("opt-saved-meta").textContent = `${parts.join(" · ")}. A scenario is one plan; this archive is the whole front.`;
}

async function renameSavedArchive() {
  const jobId = $("opt-saved").value;
  const name = $("opt-archive-name").value.trim();
  if (!jobId || !name) return;
  try {
    await api(`api/optimize/${encodeURIComponent(jobId)}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    await refreshSavedRuns();
    toast("Archive renamed");
  } catch (error) {
    toast(`Could not rename the archive: ${error.message}`, true);
  }
}

async function deleteSavedArchive() {
  const jobId = $("opt-saved").value;
  if (!jobId || !window.confirm(`Delete saved archive ${jobId}?`)) return;
  try {
    await api(`api/optimize/${encodeURIComponent(jobId)}`, { method: "DELETE" });
    if (state.optimize.jobId === jobId) {
      state.optimize.jobId = null;
      state.optimize.result = null;
      state.optimize.selected = null;
      state.optimize.pinned = [];
      clearParetoMesh();
      $("pareto-load").disabled = true;
      $("pareto-pin").disabled = true;
      $("pareto-clear-pins").disabled = true;
      $("pareto-compare").innerHTML = "";
      $("pareto-info").innerHTML = '<p class="muted">Archive deleted. Load or run another front.</p>';
      $("optimize-status").textContent = "idle";
    }
    await refreshSavedRuns();
    toast("Archive deleted");
  } catch (error) {
    toast(`Could not delete the archive: ${error.message}`, true);
  }
}

async function loadSavedArchive(jobId = null) {
  const selectedJobId = jobId || $("opt-saved").value;
  if (!selectedJobId) return;
  if (state.optimize.jobId && state.optimize.jobId !== selectedJobId) {
    state.optimize.presetName = null;
    const params = new URLSearchParams(location.search);
    params.delete("opt_preset");
    history.replaceState(null, "", `${params.toString() ? `?${params.toString()}` : ""}${location.hash || "#optimize"}`);
  }
  $("optimize-status").textContent = "loading archive";
  try {
    const payload = await api(`api/optimize/${encodeURIComponent(selectedJobId)}`);
    if (!payload.result) throw new Error("saved result is unavailable");
    state.optimize.jobId = selectedJobId;
    state.optimize.result = payload.result;
    state.optimize.pinned = [];
    renderParetoArchive(payload.result);
    $("optimize-status").textContent = "loaded";
    const job = state.optimize.savedRuns.find((item) => item.job_id === selectedJobId);
    updateSavedArchiveMeta(job || null);
    toast(`Loaded ${job?.name || selectedJobId}`);
  } catch (error) {
    $("optimize-status").textContent = "load error";
    toast(`Could not load the saved archive: ${error.message}`, true);
  }
}

function renderParetoArchive(result) {
  const archive = result.archive;
  if (!archive || !archive.solutions || !archive.solutions.length) {
    $("pareto-info").innerHTML = '<p class="hint">No feasible non-dominated solutions were found.</p>';
    return;
  }
  populateParetoSelects(archive.objectives || []);
  state.optimize.pinned = [];
  renderParetoStats({
    status: "done",
    progress: result.scalarizations,
    total: result.scalarizations,
    result,
  });
  renderParetoCompare();
  restoreParetoViewState();
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

function updateParetoRanges(archive, xIndex, yIndex, zIndex) {
  const labels = archive.objectives.map((objective) => objective.label || objective.name);
  const ranges = archive.ideal.map((value, index) => {
    const low = Math.min(Number(value), Number(archive.nadir[index]));
    const high = Math.max(Number(value), Number(archive.nadir[index]));
    return [low, high];
  });
  const parts = [
    ["X", xIndex],
    ["Y", yIndex],
    ["Z", zIndex],
  ].map(([axis, index]) => {
    const label = labels[index] || axis;
    const [low, high] = ranges[index] || [0, 0];
    const constant = Math.abs(high - low) <= 1e-12;
    return `${axis} ${label}: ${formatNumber(low, 4)}–${formatNumber(high, 4)}${constant ? " · constant" : ""}`;
  });
  $("pareto-ranges").textContent = `${parts.join("  ·  ")}  ·  axes normalized`;
}

function paretoNormalizedPoint(archive, solution) {
  if (!archive || !solution) return null;
  const xIndex = Number($("pareto-x").value || 0);
  const yIndex = Number($("pareto-y").value || 1);
  const zIndex = Number($("pareto-z").value || 2);
  return {
    x: paretoNorm(archive, xIndex, Number(solution.objectives[xIndex])),
    y: paretoNorm(archive, yIndex, Number(solution.objectives[yIndex])),
    z: paretoNorm(archive, zIndex, Number(solution.objectives[zIndex])),
  };
}

function updateParetoMarkers() {
  const chart = state.optimize.chart;
  const result = state.optimize.result;
  if (!chart || !result || !result.archive) return;
  const place = (marker, solution) => {
    const point = paretoNormalizedPoint(result.archive, solution);
    if (!point) {
      marker.visible = false;
      return;
    }
    marker.position.set((point.x - 0.5) * 3.2, (point.y - 0.5) * 3.2, (point.z - 0.5) * 3.2);
    marker.visible = true;
  };
  place(chart.marker, state.optimize.selected);
  place(chart.referenceMarker, state.optimize.reference);
}

function showParetoTooltip(solution, event) {
  const result = state.optimize.result;
  if (!result || !result.archive) return;
  const labels = result.archive.objectives.map((objective) => objective.label || objective.name);
  const rows = labels
    .map(
      (label, index) =>
        `<div><span>${escapeHtml(label)}</span> <strong>${formatNumber(Number(solution.objectives[index] || 0), 3)}</strong></div>`,
    )
    .join("");
  const tooltip = $("pareto-tooltip");
  tooltip.innerHTML = `<strong>${escapeHtml(String(solution.solution_id || "").slice(0, 10))}</strong>${rows}`;
  tooltip.hidden = false;
  const rect = $("pareto-canvas").getBoundingClientRect();
  tooltip.style.left = `${Math.min(event.clientX - rect.left + 12, rect.width - 220)}px`;
  tooltip.style.top = `${Math.min(event.clientY - rect.top + 12, rect.height - 120)}px`;
}

function setParetoReference() {
  const selected = state.optimize.selected;
  if (!selected) return;
  state.optimize.reference = selected;
  updateParetoMarkers();
  renderParetoDelta();
  drawParallelCoordinates();
  $("pareto-clear-reference").disabled = false;
  persistParetoViewState();
  toast("Reference point set");
}

function clearParetoReference() {
  state.optimize.reference = null;
  updateParetoMarkers();
  renderParetoDelta();
  drawParallelCoordinates();
  $("pareto-clear-reference").disabled = true;
  persistParetoViewState();
}

function renderParetoDelta() {
  const container = $("pareto-delta");
  const selected = state.optimize.selected;
  const reference = state.optimize.reference;
  const result = state.optimize.result;
  if (!container) return;
  if (!result || !result.archive) {
    container.innerHTML = "";
    return;
  }
  if (!reference) {
    container.innerHTML = '<p class="hint">Set one solution as the reference to compare objective deltas.</p>';
    return;
  }
  const labels = result.archive.objectives.map((objective) => objective.label || objective.name);
  const rows = labels
    .map((label, index) => {
      const selectedValue = selected ? Number(selected.objectives[index] || 0) : null;
      const referenceValue = Number(reference.objectives[index] || 0);
      if (selectedValue === null) {
        return `<div class="delta-card"><span>${escapeHtml(label)}</span><strong>—</strong></div>`;
      }
      const delta = selectedValue - referenceValue;
      return `<div class="delta-card"><span>${escapeHtml(label)}</span><strong class="${delta < 0 ? "delta-bad" : ""}">${delta >= 0 ? "+" : ""}${formatNumber(delta, 4)}</strong></div>`;
    })
    .join("");
  container.innerHTML = `<p class="hint">Selected vs reference ${escapeHtml(String(reference.solution_id || "").slice(0, 10))}</p><div class="delta-grid">${rows}</div>`;
}

function normalizeParetoViewerState(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const axis = (value, allowUniform = false) => {
    const number = Number(value);
    if (!Number.isInteger(number) || number < (allowUniform ? -1 : 0)) return null;
    return String(number);
  };
  const x = axis(raw.x);
  const y = axis(raw.y);
  const z = axis(raw.z);
  const colour = axis(raw.colour);
  const size = axis(raw.size, true);
  if (x === null || y === null || z === null || colour === null || size === null) return null;
  const floor = Number(raw.floor);
  if (!Number.isFinite(floor) || floor < 0 || floor > 100) return null;
  if (!Array.isArray(raw.brushes) || raw.brushes.length > 12) return null;
  const brushes = [];
  for (const brush of raw.brushes) {
    if (!brush || typeof brush !== "object") return null;
    const axisKey = String(brush.axis || "");
    const min = Number(brush.min);
    const max = Number(brush.max);
    if (!/^[A-Za-z0-9_]{1,40}$/.test(axisKey)) return null;
    if (!Number.isFinite(min) || !Number.isFinite(max) || min < 0 || max > 1) return null;
    brushes.push({ axis: axisKey, min: Math.min(min, max), max: Math.max(min, max) });
  }
  const point =
    raw.point === null || raw.point === undefined
      ? null
      : typeof raw.point === "string" && raw.point.length <= 120
        ? raw.point
        : null;
  const reference =
    raw.reference === null || raw.reference === undefined
      ? null
      : typeof raw.reference === "string" && raw.reference.length <= 120
        ? raw.reference
        : null;
  return { x, y, z, colour, size, floor, brushes, point, reference };
}

function normalizeParetoView(raw) {
  if (!raw || typeof raw !== "object" || raw.version !== PARETO_VIEW_VERSION) return null;
  const name = String(raw.name || "").trim().slice(0, 80);
  if (!name) return null;
  const jobId = String(raw.job_id || "").trim().slice(0, 120);
  if (!jobId) return null;
  const viewer = normalizeParetoViewerState(raw.state);
  if (!viewer) return null;
  return {
    version: PARETO_VIEW_VERSION,
    name,
    job_id: jobId,
    created_at:
      typeof raw.created_at === "string" && raw.created_at.length <= 40
        ? raw.created_at
        : new Date().toISOString(),
    state: viewer,
  };
}

function normalizeParetoViewLibrary(raw) {
  if (!raw || typeof raw !== "object" || raw.version !== PARETO_VIEW_VERSION) return null;
  if (!Array.isArray(raw.views) || raw.views.length > PARETO_VIEW_LIMIT) return null;
  const views = [];
  for (const entry of raw.views) {
    const view = normalizeParetoView(entry);
    if (!view) return null;
    const existing = views.findIndex((item) => item.name === view.name);
    if (existing >= 0) views[existing] = view;
    else views.push(view);
  }
  return views;
}

function readParetoViewLibrary() {
  try {
    const raw = localStorage.getItem(PARETO_VIEW_STORAGE_KEY);
    if (!raw) return [];
    return normalizeParetoViewLibrary(JSON.parse(raw)) || [];
  } catch (_error) {
    return [];
  }
}

function writeParetoViewLibrary(views) {
  try {
    localStorage.setItem(
      PARETO_VIEW_STORAGE_KEY,
      JSON.stringify({ version: PARETO_VIEW_VERSION, views: views.slice(0, PARETO_VIEW_LIMIT) }),
    );
    return true;
  } catch (error) {
    toast(`Could not save local views: ${error.message}`, true);
    return false;
  }
}

function updateParetoViewButtons() {
  const selected = $("pareto-view-select")?.value || "";
  $("pareto-view-load").disabled = !selected;
  $("pareto-view-delete").disabled = !selected;
}

function refreshParetoViewSelect(selectedName = null) {
  const select = $("pareto-view-select");
  if (!select) return;
  const views = readParetoViewLibrary();
  const current = selectedName || "";
  select.innerHTML =
    `<option value="">${views.length ? "— choose a saved view —" : "— no saved views —"}</option>` +
    views
      .map((view) => `<option value="${escapeHtml(view.name)}">${escapeHtml(view.name)}</option>`)
      .join("");
  if (current && views.some((view) => view.name === current)) select.value = current;
  updateParetoViewButtons();
  $("pareto-view-meta").textContent = `${views.length} local view${views.length === 1 ? "" : "s"} stored in this browser for this archive.`;
}

function currentParetoViewerState() {
  return {
    x: $("pareto-x").value || "0",
    y: $("pareto-y").value || "1",
    z: $("pareto-z").value || "2",
    colour: $("pareto-colour").value || "0",
    size: $("pareto-size").value || "-1",
    floor: Number($("pareto-floor").value || 0),
    brushes: (state.optimize.brushes || []).map((brush) => ({ ...brush })),
    point: state.optimize.selected?.solution_id || null,
    reference: state.optimize.reference?.solution_id || null,
  };
}

function saveParetoView() {
  if (!state.optimize.result?.archive) {
    toast("Load an archive before saving a view.", true);
    return;
  }
  const name = $("pareto-view-name").value.trim();
  if (!name) {
    toast("Name the view before saving.", true);
    return;
  }
  const view = normalizeParetoView({
    version: PARETO_VIEW_VERSION,
    name,
    job_id: state.optimize.jobId || "",
    created_at: new Date().toISOString(),
    state: currentParetoViewerState(),
  });
  if (!view) {
    toast("Could not read the current viewer state.", true);
    return;
  }
  const views = [view, ...readParetoViewLibrary().filter((item) => item.name !== view.name)].slice(
    0,
    PARETO_VIEW_LIMIT,
  );
  if (!writeParetoViewLibrary(views)) return;
  state.optimize.presetName = view.name;
  refreshParetoViewSelect(view.name);
  persistParetoViewState();
  toast(`Saved view “${view.name}”`);
}

function validateParetoViewForArchive(view) {
  const archive = state.optimize.result?.archive;
  if (!archive) return { ok: false, message: "Load the matching archive first." };
  if (view.job_id && state.optimize.jobId && view.job_id !== state.optimize.jobId) {
    return { ok: false, message: "This view belongs to a different archive. Load that archive first." };
  }
  for (const id of ["pareto-x", "pareto-y", "pareto-z", "pareto-colour", "pareto-size"]) {
    const select = $(id);
    if (!Array.from(select.options).some((option) => option.value === String(view.state[id.split("-")[1]]))) {
      return { ok: false, message: "This view uses an axis that is not available in the current archive." };
    }
  }
  const solutionIds = new Set((archive.solutions || []).map((solution) => solution.solution_id));
  if (view.state.point && !solutionIds.has(view.state.point)) {
    return { ok: false, message: "The selected solution is not present in this archive." };
  }
  if (view.state.reference && !solutionIds.has(view.state.reference)) {
    return { ok: false, message: "The reference solution is not present in this archive." };
  }
  const axes = parallelAxesForArchive(archive).map((axis) => axis.key);
  if (view.state.brushes.some((brush) => !axes.includes(brush.axis))) {
    return { ok: false, message: "This view uses a brush axis that is not available in the current archive." };
  }
  return { ok: true };
}

function applyParetoView(view) {
  const validation = validateParetoViewForArchive(view);
  if (!validation.ok) {
    toast(validation.message, true);
    return false;
  }
  const archive = state.optimize.result.archive;
  const viewer = view.state;
  $("pareto-x").value = String(viewer.x);
  $("pareto-y").value = String(viewer.y);
  $("pareto-z").value = String(viewer.z);
  $("pareto-colour").value = String(viewer.colour);
  $("pareto-size").value = String(viewer.size);
  $("pareto-floor").value = String(viewer.floor);
  $("pareto-floor-value").textContent = viewer.floor <= 0 ? "all" : `>= ${(viewer.floor / 100).toFixed(2)}`;
  state.optimize.brushes = viewer.brushes.map((brush) => ({ ...brush }));
  state.optimize.selected =
    (viewer.point && archive.solutions.find((solution) => solution.solution_id === viewer.point)) || null;
  state.optimize.reference =
    (viewer.reference && archive.solutions.find((solution) => solution.solution_id === viewer.reference)) || null;
  state.optimize.presetName = view.name;
  $("pareto-view-name").value = view.name;
  $("pareto-reference").disabled = !state.optimize.selected;
  $("pareto-clear-reference").disabled = !state.optimize.reference;
  $("pareto-load").disabled = !state.optimize.selected;
  $("pareto-pin").disabled = !state.optimize.selected;
  drawPareto();
  if (state.optimize.selected) {
    renderParetoInfo(state.optimize.selected);
  } else {
    $("pareto-info").innerHTML = `<p class="muted">${state.optimize.filtered.length} visible solutions. Click a sphere or parallel line to inspect it.</p>`;
    renderParetoDelta();
    drawParallelCoordinates();
  }
  refreshParetoViewSelect(view.name);
  persistParetoViewState();
  toast(`Loaded view “${view.name}”`);
  return true;
}

async function loadParetoView() {
  const name = $("pareto-view-select").value;
  if (!name) {
    toast("Choose a saved view first.", true);
    return;
  }
  const view = readParetoViewLibrary().find((item) => item.name === name);
  if (!view) {
    toast("That local view is no longer available.", true);
    refreshParetoViewSelect();
    return;
  }
  if (view.job_id && view.job_id !== state.optimize.jobId) {
    const saved = state.optimize.savedRuns.find((item) => item.job_id === view.job_id);
    if (!saved) {
      toast("The archive for this view is not available. Load the matching archive first.", true);
      return;
    }
    await loadSavedArchive(view.job_id);
  }
  applyParetoView(view);
}

function deleteParetoView() {
  const name = $("pareto-view-select").value;
  if (!name) {
    toast("Choose a saved view first.", true);
    return;
  }
  const views = readParetoViewLibrary().filter((view) => view.name !== name);
  if (!writeParetoViewLibrary(views)) return;
  if (state.optimize.presetName === name) {
    state.optimize.presetName = null;
    persistParetoViewState();
  }
  refreshParetoViewSelect();
  toast(`Deleted view “${name}”`);
}

function downloadText(text, filename, type) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function exportParetoViews() {
  const views = readParetoViewLibrary();
  if (!views.length) {
    toast("No local views to export.", true);
    return;
  }
  downloadText(
    JSON.stringify({ version: PARETO_VIEW_VERSION, exported_at: new Date().toISOString(), views }, null, 2),
    "fresh-pareto-views.json",
    "application/json",
  );
  toast(`Exported ${views.length} local views`);
}

async function importParetoViews(event) {
  const input = event.target;
  const file = input.files?.[0];
  if (!file) return;
  try {
    if (file.size > PARETO_VIEW_IMPORT_LIMIT) {
      toast("That view file is too large.", true);
      return;
    }
    const payload = JSON.parse(await file.text());
    const imported = normalizeParetoViewLibrary(payload);
    if (!imported) {
      toast("That JSON file is not a valid version 1 local-view library.", true);
      return;
    }
    const merged = new Map(readParetoViewLibrary().map((view) => [view.name, view]));
    for (const view of imported) merged.set(view.name, view);
    const views = Array.from(merged.values()).slice(0, PARETO_VIEW_LIMIT);
    if (!writeParetoViewLibrary(views)) return;
    refreshParetoViewSelect();
    toast(`Imported ${imported.length} views; ${views.length} local views available`);
  } catch (error) {
    toast(`Could not import views: ${error.message}`, true);
  } finally {
    input.value = "";
  }
}

async function copyParetoPresetLink() {
  if (!state.optimize.presetName) {
    toast("Save or load a named view before copying a preset link.", true);
    return;
  }
  persistParetoViewState();
  await copyText(location.href, `Preset link copied · ${state.optimize.presetName}`);
}

function persistParetoViewState() {
  const result = state.optimize.result;
  if (!result || !result.archive) return;
  const params = new URLSearchParams(location.search);
  params.set("opt_x", $("pareto-x").value || "0");
  params.set("opt_y", $("pareto-y").value || "1");
  params.set("opt_z", $("pareto-z").value || "2");
  params.set("opt_colour", $("pareto-colour").value || "0");
  params.set("opt_size", $("pareto-size").value || "-1");
  params.set("opt_floor", $("pareto-floor").value || "0");
  if ((state.optimize.brushes || []).length) {
    params.set(
      "opt_brushes",
      state.optimize.brushes
        .map((brush) => `${brush.axis}:${brush.min.toFixed(3)}:${brush.max.toFixed(3)}`)
        .join("~"),
    );
  } else {
    params.delete("opt_brushes");
  }
  if (state.optimize.jobId) params.set("opt_job", state.optimize.jobId);
  else params.delete("opt_job");
  if (state.optimize.presetName) params.set("opt_preset", state.optimize.presetName);
  else params.delete("opt_preset");
  if (state.optimize.selected?.solution_id) params.set("opt_point", state.optimize.selected.solution_id);
  else params.delete("opt_point");
  if (state.optimize.reference?.solution_id) params.set("opt_reference", state.optimize.reference.solution_id);
  else params.delete("opt_reference");
  const search = params.toString();
  history.replaceState(null, "", `${search ? `?${search}` : ""}${location.hash || "#optimize"}`);
}

function restoreParetoViewState() {
  const result = state.optimize.result;
  if (!result || !result.archive) return;
  const params = new URLSearchParams(location.search);
  const presetName = params.get("opt_preset");
  state.optimize.presetName = presetName ? presetName.slice(0, 80) : null;
  refreshParetoViewSelect(state.optimize.presetName);
  const setSelect = (id, key) => {
    const select = $(id);
    const value = params.get(key);
    if (!select || value === null) return;
    if (Array.from(select.options).some((option) => option.value === value)) select.value = value;
  };
  setSelect("pareto-x", "opt_x");
  setSelect("pareto-y", "opt_y");
  setSelect("pareto-z", "opt_z");
  setSelect("pareto-colour", "opt_colour");
  setSelect("pareto-size", "opt_size");
  const floor = Number(params.get("opt_floor") || 0);
  if (Number.isFinite(floor)) {
    $("pareto-floor").value = String(Math.max(0, Math.min(100, floor)));
    $("pareto-floor-value").textContent = floor <= 0 ? "all" : `>= ${(floor / 100).toFixed(2)}`;
  }
  const brushValue = params.get("opt_brushes");
  state.optimize.brushes = brushValue
    ? brushValue
        .split("~")
        .map((entry) => {
          const [axis, min, max] = entry.split(":");
          const lower = Number(min);
          const upper = Number(max);
          if (!axis || !Number.isFinite(lower) || !Number.isFinite(upper)) return null;
          return {
            axis,
            min: Math.max(0, Math.min(1, Math.min(lower, upper))),
            max: Math.max(0, Math.min(1, Math.max(lower, upper))),
          };
        })
        .filter(Boolean)
    : [];
  const pointId = params.get("opt_point");
  if (pointId) {
    const solution = result.archive.solutions.find((item) => item.solution_id === pointId);
    if (solution) renderParetoInfo(solution);
  }
  const referenceId = params.get("opt_reference");
  if (referenceId) {
    const reference = result.archive.solutions.find((item) => item.solution_id === referenceId);
    if (reference) {
      state.optimize.reference = reference;
      $("pareto-clear-reference").disabled = false;
      updateParetoMarkers();
      renderParetoDelta();
    }
  }
  drawPareto();
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    toast(message);
    return;
  } catch (_error) {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    toast(message);
  }
}

async function copyParetoLink() {
  persistParetoViewState();
  await copyText(location.href, "View link copied");
}

function downloadParetoCsv() {
  const result = state.optimize.result;
  const points = state.optimize.filtered || [];
  if (!result || !result.archive || !points.length) {
    toast("No visible solutions to export", true);
    return;
  }
  const archive = result.archive;
  const labels = archive.objectives.map((objective) => objective.label || objective.name);
  const metrics = Object.keys(points[0].metrics || {});
  const header = ["solution_id", ...labels, ...metrics, "robustness", "constraint_violation", "planted_sites"];
  const rows = points.map((solution) => [
    solution.solution_id,
    ...archive.objectives.map((_, index) => solution.objectives[index]),
    ...metrics.map((key) => solution.metrics?.[key] ?? ""),
    solution.robustness ?? "",
    solution.constraint_violation ?? "",
    (solution.planted || []).length,
  ]);
  const csv = [header, ...rows]
    .map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv + "\n"], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "pareto-visible-solutions.csv";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  toast(`Exported ${points.length} visible solutions`);
}

const PARALLEL_METRICS = [
  {
    key: "robustness",
    label: "Robustness",
    getter: (solution) => Number(solution.robustness || 0),
  },
  {
    key: "planted_sites",
    label: "Planted sites",
    getter: (solution) => (solution.planted || []).length,
  },
  {
    key: "cost_cad",
    label: "Cost (C$)",
    objectiveName: "cost",
    getter: (solution) => Number(solution.metrics?.cost_cad ?? 0),
  },
  {
    key: "water_l",
    label: "Water (L)",
    objectiveName: "water",
    getter: (solution) => Number(solution.metrics?.water_l ?? 0),
  },
  {
    key: "habitat_index",
    label: "Habitat",
    getter: (solution) => Number(solution.metrics?.habitat_index ?? 0),
  },
];

function parallelAxesForArchive(archive) {
  const axes = [];
  const solutions = archive.solutions || [];
  const ideal = archive.ideal || [];
  const nadir = archive.nadir || [];
  const objectiveNames = new Set((archive.objectives || []).map((objective) => objective.name));
  (archive.objectives || []).forEach((objective, index) => {
    const low = Math.min(Number(ideal[index] ?? 0), Number(nadir[index] ?? 0));
    const high = Math.max(Number(ideal[index] ?? 0), Number(nadir[index] ?? 0));
    if (!Number.isFinite(low) || !Number.isFinite(high) || high - low <= 1e-12) return;
    axes.push({
      key: `obj${index}`,
      label: objective.label || objective.name || `Objective ${index + 1}`,
      low,
      high,
      kind: "objective",
      index,
    });
  });
  for (const definition of PARALLEL_METRICS) {
    if (definition.objectiveName && objectiveNames.has(definition.objectiveName)) continue;
    const values = solutions.map(definition.getter).map(Number).filter(Number.isFinite);
    if (!values.length) continue;
    const low = Math.min(...values);
    const high = Math.max(...values);
    if (high - low <= 1e-12) continue;
    axes.push({ key: definition.key, label: definition.label, low, high, kind: "metric", getter: definition.getter });
  }
  return axes.slice(0, 12);
}

function parallelAxisValue(axis, solution) {
  if (axis.kind === "objective") return Number(solution.objectives?.[axis.index] ?? 0);
  return Number(axis.getter(solution) || 0);
}

function parallelAxisNorm(axis, solution) {
  const value = parallelAxisValue(axis, solution);
  if (!Number.isFinite(value) || axis.high - axis.low <= 1e-12) return 0.5;
  return Math.max(0, Math.min(1, (value - axis.low) / (axis.high - axis.low)));
}

function parallelBrushMatches(solution, axes) {
  const brushes = state.optimize.brushes || [];
  if (!brushes.length) return true;
  for (const brush of brushes) {
    const axis = axes.find((item) => item.key === brush.axis);
    if (!axis) continue;
    const value = parallelAxisNorm(axis, solution);
    if (value < brush.min - 1e-9 || value > brush.max + 1e-9) return false;
  }
  return true;
}

function parallelCompact(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const absolute = Math.abs(number);
  if (absolute >= 1e9) return `${(number / 1e9).toFixed(1)}b`;
  if (absolute >= 1e6) return `${(number / 1e6).toFixed(1)}m`;
  if (absolute >= 1e3) return `${(number / 1e3).toFixed(1)}k`;
  if (absolute >= 10) return number.toFixed(0);
  return number.toFixed(2);
}

function parallelLocalPoint(event) {
  const svg = $("parallel-chart");
  if (!svg) return { x: 0, y: 0 };
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  const matrix = svg.getScreenCTM();
  if (!matrix) return { x: 0, y: 0 };
  return point.matrixTransform(matrix.inverse());
}

function updateParallelBrushChips(axes) {
  const container = $("parallel-brush-label");
  const clear = $("parallel-clear-brush");
  if (!container || !clear) return;
  const brushes = state.optimize.brushes || [];
  clear.disabled = brushes.length === 0;
  if (!brushes.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = brushes
    .map((brush) => {
      const axis = axes.find((item) => item.key === brush.axis);
      const label = axis?.label || brush.axis;
      const low = axis ? axis.low + (axis.high - axis.low) * brush.min : brush.min;
      const high = axis ? axis.low + (axis.high - axis.low) * brush.max : brush.max;
      return `<span class="chip">${escapeHtml(label)} ${parallelCompact(low)}–${parallelCompact(high)} <button type="button" data-brush-axis="${escapeHtml(brush.axis)}" aria-label="Remove ${escapeHtml(label)} brush">×</button></span>`;
    })
    .join("");
  container.querySelectorAll("[data-brush-axis]").forEach((button) => {
    button.addEventListener("click", () => removeParallelBrush(button.dataset.brushAxis));
  });
}

function removeParallelBrush(axisKey) {
  state.optimize.brushes = (state.optimize.brushes || []).filter((brush) => brush.axis !== axisKey);
  drawPareto();
  persistParetoViewState();
}

function clearParallelBrushes() {
  state.optimize.brushes = [];
  state.optimize.parallelDrag = null;
  drawPareto();
  persistParetoViewState();
}

function drawParallelCoordinates() {
  const svg = $("parallel-chart");
  if (!svg) return;
  const result = state.optimize.result;
  const archive = result?.archive;
  const count = $("parallel-count");
  if (!archive) {
    svg.innerHTML = "";
    if (count) count.textContent = "--";
    updateParallelBrushChips([]);
    return;
  }
  const axes = state.optimize.parallelAxes.length
    ? state.optimize.parallelAxes
    : parallelAxesForArchive(archive);
  const visible = state.optimize.filtered || [];
  if (count) count.textContent = `${visible.length} of ${(archive.solutions || []).length} visible`;
  updateParallelBrushChips(axes);
  if (!axes.length) {
    svg.innerHTML = '<text class="parallel-empty" x="500" y="150">No variable axes available.</text>';
    return;
  }
  const width = 1000;
  const height = 300;
  const left = 42;
  const right = 42;
  const top = 36;
  const bottom = 24;
  const innerWidth = width - left - right;
  const innerHeight = height - top - bottom;
  const xFor = (index) => left + (axes.length === 1 ? innerWidth / 2 : (index * innerWidth) / (axes.length - 1));
  const yFor = (value) => top + (1 - value) * innerHeight;
  let markup = "";
  axes.forEach((axis, index) => {
    const x = xFor(index);
    const low = parallelCompact(axis.low);
    const high = parallelCompact(axis.high);
    markup += `<line class="parallel-axis" x1="${x}" y1="${top}" x2="${x}" y2="${top + innerHeight}"></line>`;
    markup += `<text class="parallel-axis-label" x="${x}" y="14">${escapeHtml(axis.label)}</text>`;
    markup += `<text class="parallel-tick" x="${x}" y="${top + innerHeight + 14}">${escapeHtml(low)}</text>`;
    markup += `<text class="parallel-tick" x="${x}" y="${top - 5}">${escapeHtml(high)}</text>`;
  });
  for (const brush of state.optimize.brushes || []) {
    const axis = axes.find((item) => item.key === brush.axis);
    if (!axis) continue;
    const index = axes.indexOf(axis);
    const x = xFor(index);
    const y1 = yFor(brush.max);
    const y2 = yFor(brush.min);
    markup += `<rect class="parallel-brush" x="${x - 5}" y="${Math.min(y1, y2)}" width="10" height="${Math.abs(y2 - y1)}"></rect>`;
  }
  const drag = state.optimize.parallelDrag;
  if (drag) {
    const axis = axes.find((item) => item.key === drag.axisKey);
    if (axis) {
      const index = axes.indexOf(axis);
      const x = xFor(index);
      const y1 = yFor(Math.max(drag.startY, drag.currentY));
      const y2 = yFor(Math.min(drag.startY, drag.currentY));
      markup += `<rect class="parallel-brush" opacity="0.55" x="${x - 5}" y="${Math.min(y1, y2)}" width="10" height="${Math.abs(y2 - y1)}"></rect>`;
    }
  }
  axes.forEach((axis, index) => {
    const x = xFor(index);
    markup += `<rect class="parallel-brush-hit" data-axis="${escapeHtml(axis.key)}" x="${x - 11}" y="${top}" width="22" height="${innerHeight}"></rect>`;
  });
  const displayed = visible.slice(0, 1200);
  const solutionsById = new Map(displayed.map((solution) => [solution.solution_id, solution]));
  const selectedId = state.optimize.selected?.solution_id;
  const referenceId = state.optimize.reference?.solution_id;
  for (const solution of displayed) {
    const points = axes
      .map((axis, index) => `${xFor(index)},${yFor(parallelAxisNorm(axis, solution))}`)
      .join(" ");
    const classes = ["parallel-line"];
    if (solution.solution_id === selectedId) classes.push("selected");
    if (solution.solution_id === referenceId) classes.push("reference");
    markup += `<polyline class="${classes.join(" ")}" points="${points}" data-solution-id="${escapeHtml(solution.solution_id)}"></polyline>`;
  }
  if (!visible.length) {
    markup += '<text class="parallel-empty" x="500" y="150">No solutions match the current filters.</text>';
  } else if (visible.length > displayed.length) {
    markup += `<text class="parallel-empty" x="500" y="150">Showing ${displayed.length} of ${visible.length} lines.</text>`;
  }
  svg.innerHTML = markup;
  svg.querySelectorAll(".parallel-line").forEach((line) => {
    line.addEventListener("click", (event) => {
      event.stopPropagation();
      const solution = solutionsById.get(line.dataset.solutionId);
      if (solution) renderParetoInfo(solution);
    });
  });
  svg.querySelectorAll(".parallel-brush-hit").forEach((hit) => {
    hit.addEventListener("pointerdown", beginParallelBrush);
  });
}

function initParallelEvents() {
  const svg = $("parallel-chart");
  if (!svg) return;
  svg.addEventListener("pointermove", updateParallelBrush);
  svg.addEventListener("pointerup", finishParallelBrush);
  svg.addEventListener("pointercancel", finishParallelBrush);
}

function beginParallelBrush(event) {
  const hit = event.target.closest?.(".parallel-brush-hit");
  if (!hit) return;
  event.preventDefault();
  event.stopPropagation();
  const svg = $("parallel-chart");
  const local = parallelLocalPoint(event);
  state.optimize.parallelDrag = {
    axisKey: hit.dataset.axis,
    add: event.shiftKey,
    startY: local.y,
    currentY: local.y,
  };
  state.optimize.parallelPointerId = event.pointerId;
  if (svg?.setPointerCapture) svg.setPointerCapture(event.pointerId);
  drawParallelCoordinates();
}

function updateParallelBrush(event) {
  const drag = state.optimize.parallelDrag;
  if (!drag || (state.optimize.parallelPointerId !== null && event.pointerId !== state.optimize.parallelPointerId)) return;
  const local = parallelLocalPoint(event);
  drag.currentY = local.y;
  drawParallelCoordinates();
}

function finishParallelBrush(event) {
  const drag = state.optimize.parallelDrag;
  if (!drag) return;
  const local = parallelLocalPoint(event);
  drag.currentY = local.y;
  const min = Math.min(drag.startY, drag.currentY);
  const max = Math.max(drag.startY, drag.currentY);
  const axis = state.optimize.parallelAxes.find((item) => item.key === drag.axisKey);
  const svg = $("parallel-chart");
  if (svg?.releasePointerCapture && state.optimize.parallelPointerId !== null) {
    try {
      svg.releasePointerCapture(state.optimize.parallelPointerId);
    } catch (_error) {
      // The pointer may already be released by the browser.
    }
  }
  state.optimize.parallelDrag = null;
  state.optimize.parallelPointerId = null;
  if (axis && max - min > 0.01) {
    const top = 36;
    const innerHeight = 240;
    const normalize = (y) => Math.max(0, Math.min(1, (top + innerHeight - y) / innerHeight));
    const first = normalize(min);
    const second = normalize(max);
    state.optimize.brushes = (state.optimize.brushes || []).filter((brush) => brush.axis !== drag.axisKey);
    state.optimize.brushes.push({
      axis: drag.axisKey,
      min: Math.min(first, second),
      max: Math.max(first, second),
    });
  }
  drawPareto();
  persistParetoViewState();
}

function drawPareto() {
  const chart = ensureOptimizeChart();
  const result = state.optimize.result;
  if (!result || !result.archive) return;
  const archive = result.archive;
  const solutions = archive.solutions || [];
  state.optimize.parallelAxes = parallelAxesForArchive(archive);
  const xIndex = Number($("pareto-x").value || 0);
  const yIndex = Number($("pareto-y").value || 1);
  const zIndex = Number($("pareto-z").value || 2);
  const colourIndex = Number($("pareto-colour").value || 0);
  const sizeIndex = Number($("pareto-size").value || -1);
  const sliceIndex = Number($("pareto-slice-objective").value || 0);
  const threshold = Number($("pareto-slice").value) / 100;
  const robustnessFloor = Number($("pareto-floor").value || 0) / 100;
  const filtered = solutions
    .map((solution) => ({
      solution,
      x: paretoNorm(archive, xIndex, Number(solution.objectives[xIndex])),
      y: paretoNorm(archive, yIndex, Number(solution.objectives[yIndex])),
      z: paretoNorm(archive, zIndex, Number(solution.objectives[zIndex])),
      colour: paretoNorm(archive, colourIndex, Number(solution.objectives[colourIndex])),
      size: sizeIndex >= 0 ? paretoNorm(archive, sizeIndex, Number(solution.objectives[sizeIndex])) : 0.5,
      slice: paretoNorm(archive, sliceIndex, Number(solution.objectives[sliceIndex])),
      robustness: Number(solution.robustness || 0),
    }))
    .filter(
      (point) =>
        (threshold <= 0 || point.slice >= threshold) &&
        (robustnessFloor <= 0 || point.robustness >= robustnessFloor) &&
        parallelBrushMatches(point.solution, state.optimize.parallelAxes),
    );
  state.optimize.filtered = filtered.map((point) => point.solution);
  clearParetoMesh();
  if (!filtered.length) {
    $("pareto-info").innerHTML =
      '<p class="hint">No solutions match the current filters. Lower the slice or robustness floor, or clear a brush.</p>';
    drawParallelCoordinates();
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
  $("pareto-axis-x").textContent = `X: ${labels[xIndex] || ""}`;
  $("pareto-axis-y").textContent = `Y: ${labels[yIndex] || ""}`;
  $("pareto-axis-z").textContent = `Z: ${labels[zIndex] || ""}`;
  updateParetoAxes(chart, { x: labels[xIndex], y: labels[yIndex], z: labels[zIndex] });
  $("pareto-legend").innerHTML =
    `<span><i class="change-swatch" style="background:hsl(210 68% 48%)"></i>low ${escapeHtml(labels[colourIndex] || "")}</span>` +
    `<span><i class="change-swatch" style="background:hsl(73 68% 48%)"></i>high ${escapeHtml(labels[colourIndex] || "")}</span>` +
    `<span>${filtered.length} of ${solutions.length} solutions</span>`;
  $("pareto-info").innerHTML = `<p class="muted">${filtered.length} visible solutions. Click a sphere to inspect it.</p>`;
  updateParetoRanges(archive, xIndex, yIndex, zIndex);
  updateParetoMarkers();
  drawParallelCoordinates();
  chart.renderer.render(chart.scene, chart.camera);
  persistParetoViewState();
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
  $("pareto-pin").disabled = false;
  $("pareto-reference").disabled = false;
  updateParetoMarkers();
  renderParetoDelta();
  drawParallelCoordinates();
  persistParetoViewState();
}

function pinSelectedSolution() {
  const solution = state.optimize.selected;
  if (!solution) return;
  if (state.optimize.pinned.some((item) => item.solution_id === solution.solution_id)) return;
  if (state.optimize.pinned.length >= 3) state.optimize.pinned.shift();
  state.optimize.pinned.push(solution);
  renderParetoCompare();
  toast(`Pinned ${solution.solution_id.slice(0, 8)}`);
}

function clearPinnedSolutions() {
  state.optimize.pinned = [];
  renderParetoCompare();
}

function selectParetoByIndex(index) {
  const solution = state.optimize.result?.archive?.solutions?.[index];
  if (solution) renderParetoInfo(solution);
}

async function focusParetoPoint(scenarioName) {
  const match = /^Pareto ([0-9a-f]{6,})/i.exec(scenarioName || "");
  if (!match) return false;
  const prefix = match[1].toLowerCase();
  const findIndex = (result) => {
    const solutions = result?.archive?.solutions || [];
    return solutions.findIndex((solution) =>
      String(solution.solution_id || "").toLowerCase().startsWith(prefix)
    );
  };
  if (state.optimize.result) {
    const index = findIndex(state.optimize.result);
    if (index >= 0) {
      selectParetoByIndex(index);
      return true;
    }
  }
  try {
    const listing = await api("api/optimize");
    for (const job of (listing.jobs || []).filter((item) => item.status === "done")) {
      const payload = await api(`api/optimize/${encodeURIComponent(job.job_id)}`);
      const result = payload.result;
      const index = findIndex(result);
      if (index < 0) continue;
      state.optimize.jobId = job.job_id;
      state.optimize.result = result;
      state.optimize.pinned = [];
      renderParetoArchive(result);
      selectParetoByIndex(index);
      $("opt-saved").value = job.job_id;
      updateSavedArchiveMeta(job);
      return true;
    }
  } catch (_error) {
    return false;
  }
  return false;
}

function renderParetoCompare() {
  const pinned = state.optimize.pinned || [];
  $("pareto-clear-pins").disabled = pinned.length === 0;
  if (!pinned.length) {
    $("pareto-compare").innerHTML = '<p class="hint">Pin up to three solutions to compare their objective vectors.</p>';
    return;
  }
  const result = state.optimize.result;
  const archive = result ? result.archive : null;
  if (!archive) return;
  const labels = archive.objectives.map((objective) => objective.label || objective.name);
  const header = pinned.map((solution) => `<th class="pin-id">${escapeHtml(solution.solution_id.slice(0, 8))}</th>`).join("");
  const rows = labels
    .map((label, index) => {
      const cells = pinned
        .map((solution) => `<td>${formatNumber(Number(solution.objectives[index] || 0), 2)}</td>`)
        .join("");
      return `<tr><td>${escapeHtml(label)}</td>${cells}</tr>`;
    })
    .join("");
  const planted = pinned
    .map((solution) => `<td>${formatNumber((solution.planted || []).length)}</td>`)
    .join("");
  $("pareto-compare").innerHTML = `<table><thead><tr><th>Objective</th>${header}</tr></thead><tbody>${rows}<tr><td>Planted sites</td>${planted}</tr></tbody></table>`;
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
    const control = products.find((product) => product.id === "change_control.json");
    if (control) {
      state.changeProduct = control.id;
      select.value = state.changeProduct;
    } else if (products.some((product) => product.id === state.changeProduct)) {
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
    const source = threeScene();
  rebuildThreeTrees(source.compact ? source.tree_arrays : source.trees);
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
    if ($("view-birds").classList.contains("active")) loadBirds();
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

async function loadScenario(scenarioId, { focusPareto = false } = {}) {
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
    if (focusPareto && (await focusParetoPoint(scenario.name))) {
      switchView("optimize");
      toast(`Loaded ${scenario.name} — source Pareto point selected`);
      return;
    }
    switchView("scene");
    toast(`Loaded ${scenario.name}`);
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

function focusDowntown() {
  if (!state.three) return;
  if (state.three.walkMode) setWalkMode(false);
  const span = sceneSpan();
  const source = threeScene();
  const [originLon, originLat] = source.origin_lonlat;
  const [mx, my] = source.meters_per_degree;
  const targetX = (-123.1207 - originLon) * mx;
  const targetZ = (originLat - 49.2827) * my;
  const distance = Math.max(700, span * 0.22);
  state.three.camera.position.set(
    targetX + distance * 0.55,
    distance * 0.48,
    targetZ + distance * 0.9,
  );
  state.three.controls.target.set(targetX, 25, targetZ);
  state.three.controls.maxDistance = span * 2.8;
  state.three.camera.far = span * 7;
  state.three.camera.updateProjectionMatrix();
  state.three.controls.update();
}

function threeScene() {
  return state.scene3d || state.scene;
}

function sceneSpan() {
  const bounds = threeScene()?.bounds || [0, 0, 100, 100];
  return Math.max(Number(bounds[2]) - Number(bounds[0]), Number(bounds[3]) - Number(bounds[1]), 100);
}

function resetCamera() {
  if (!state.three) return;
  if (state.three.walkMode) setWalkMode(false);
  const span = sceneSpan();
  const distance = Math.max(300, span * 0.62);
  state.three.camera.position.set(distance * 0.55, distance * 0.52, distance * 0.85);
  state.three.controls.target.set(0, Math.max(12, span * 0.01), 0);
  state.three.controls.maxDistance = span * 2.8;
  state.three.camera.far = span * 7;
  state.three.camera.updateProjectionMatrix();
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
