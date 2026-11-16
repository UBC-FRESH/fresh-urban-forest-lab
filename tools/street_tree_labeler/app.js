const state = {
  samples: [],
  labels: {},
  index: 0,
  saveTimer: null,
  saving: false,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).error || detail; } catch (_error) { /* noop */ }
    throw new Error(detail);
  }
  return response.json();
}

function current() { return state.samples[state.index]; }
function labels() { return state.labels[current()?.candidate_id] || {}; }

function reviewedCount() {
  return state.samples.filter((sample) => {
    const row = state.labels[sample.candidate_id] || {};
    return row.tree_present && row.trunk_visible && row.box_quality;
  }).length;
}

function setStatus(text, kind = "") {
  const element = $("save-status");
  element.textContent = text;
  element.className = `status ${kind}`.trim();
}

function render() {
  const sample = current();
  if (!sample) return;
  $("crop").src = `/crops/${encodeURIComponent(sample.crop)}`;
  $("candidate-id").textContent = sample.candidate_id;
  $("candidate-meta").textContent =
    `${sample.stratum} · ${sample.view_count} view${sample.view_count === 1 ? "" : "s"} · ` +
    `inventory ${Number(sample.nearest_inventory_m).toFixed(1)} m · ` +
    `unc ±${Number(sample.uncertainty_m).toFixed(1)} m`;
  const row = labels();
  for (const name of ["tree_present", "trunk_visible", "box_quality"]) {
    for (const input of document.querySelectorAll(`input[name="${name}"]`)) {
      input.checked = input.value === row[name];
    }
  }
  $("notes").value = row.notes || "";
  $("progress-count").textContent = `${reviewedCount()} / ${state.samples.length}`;
  setStatus("saved");
}

function readForm() {
  const row = { ...labels() };
  for (const name of ["tree_present", "trunk_visible", "box_quality"]) {
    row[name] = document.querySelector(`input[name="${name}"]:checked`)?.value || "";
  }
  row.notes = $("notes").value;
  return row;
}

function scheduleSave() {
  state.labels[current().candidate_id] = readForm();
  $("progress-count").textContent = `${reviewedCount()} / ${state.samples.length}`;
  setStatus("unsaved", "dirty");
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(save, 250);
}

async function save() {
  if (state.saving || !current()) return;
  state.saving = true;
  const candidateId = current().candidate_id;
  try {
    const response = await api("/api/labels", {
      method: "POST",
      body: JSON.stringify({ candidate_id: candidateId, ...readForm() }),
    });
    state.labels[candidateId] = response.labels;
    setStatus("saved");
    $("error").hidden = true;
  } catch (error) {
    setStatus("save failed", "error");
    $("error").textContent = error.message;
    $("error").hidden = false;
  } finally {
    state.saving = false;
  }
}

function go(delta) {
  clearTimeout(state.saveTimer);
  save();
  state.index = Math.max(0, Math.min(state.samples.length - 1, state.index + delta));
  render();
}

function bind() {
  for (const input of document.querySelectorAll("input[type=radio]")) {
    input.addEventListener("change", scheduleSave);
  }
  $("notes").addEventListener("input", scheduleSave);
  $("prev").addEventListener("click", () => go(-1));
  $("next").addEventListener("click", () => go(1));
  window.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
    const key = event.key.toLowerCase();
    const mapping = {
      "1": ["tree_present", "yes"], "2": ["tree_present", "partial"], "3": ["tree_present", "no"],
      y: ["trunk_visible", "yes"], n: ["trunk_visible", "no"],
      g: ["box_quality", "good"], l: ["box_quality", "loose"], b: ["box_quality", "bad"],
    };
    if (mapping[key]) {
      const [name, value] = mapping[key];
      const input = document.querySelector(`input[name="${name}"][value="${value}"]`);
      if (input) { input.checked = true; scheduleSave(); }
    } else if (key === "arrowleft") go(-1);
    else if (key === "arrowright") go(1);
  });
  window.addEventListener("beforeunload", () => { clearTimeout(state.saveTimer); });
}

async function init() {
  try {
    const [manifest, labels] = await Promise.all([api("/api/manifest"), api("/api/labels")]);
    state.samples = manifest.samples;
    state.labels = labels.labels;
    bind();
    render();
  } catch (error) {
    $("error").textContent = error.message;
    $("error").hidden = false;
  }
}

init();
