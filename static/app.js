const state = { scenario: null, mode: "vulnerable", preset: "normal", capacity: null };
let scenarioCatalog = [];
const RUN_TIMEOUT_MS = 90000;

const modeCopy = {
  vulnerable: "No prompt guard and no field authorization. Groq-selected fields are returned directly from SQLite.",
  prompt_only: "A Groq privacy prompt decides allow or refuse. The bypass exploits a deliberately fragile trust rule.",
  hardened: "Groq may request any field, but SQLite access is projected by application policy and output DLP.",
};
const flowNotes = {
  vulnerable: "This teaching mode intentionally lets model-selected data or actions reach an unsafe tool boundary.",
  prompt_only: "A model guard can refuse a request, but it is not an application security boundary.",
  hardened: "The model may plan the work; application policy independently authorizes data access and side effects.",
};
const emptyState = `<span class="empty-mark" aria-hidden="true">→</span><strong>Run or compare this request</strong><p>Use one mode for its full execution trace, or compare all three security postures.</p>`;
const presetCopy = {
  normal: { label: "Normal request", hint: "Legitimate request demonstrating authorized agent workflow." },
  attack: { label: "Vulnerable-mode attack", hint: "Attack request targeting the Vulnerable mode's missing application controls." },
  bypass: { label: "Prompt-only bypass", hint: "Plausible pretext designed to bypass the Prompt-only mode's model guard." },
  custom: { hint: "Custom user message entered directly in the console." },
};

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" })[char]);
const APP_PATH_PREFIX = "/who-let-the-agents-act";
const configuredBasePath = document.querySelector('meta[name="wlaa-base-path"]')?.content || "";
const APP_BASE_PATH = configuredBasePath || (window.location.pathname === APP_PATH_PREFIX || window.location.pathname.startsWith(`${APP_PATH_PREFIX}/`) ? APP_PATH_PREFIX : "");
const appUrl = (path) => `${APP_BASE_PATH}${path}`;
document.querySelectorAll("[data-app-path]").forEach((link) => {
  link.href = appUrl(link.dataset.appPath);
});
function locationScenario() {
  const queryScenario = new URLSearchParams(window.location.search).get("scenario");
  if (queryScenario) return queryScenario;
  const routeMatch = window.location.pathname.replace(new RegExp(`^${APP_BASE_PATH}`), "").match(/^\/labs?\/([^/]+)\/?$/);
  return routeMatch ? decodeURIComponent(routeMatch[1]) : null;
}
function updateDatabaseStatus(database) {
  $("#db-status").classList.remove("hidden");
  const count = database.customers ?? database.transfer_requests ?? database.refund_transactions ?? database.invoices ?? database.transactions ?? database.documents ?? database.diagnostics ?? database.payment_requests ?? database.fraud_cases ?? 0;
  const noun = database.customers !== undefined ? "CUSTOMERS" : database.refund_transactions !== undefined ? "REFUND TRANSACTIONS" : database.invoices !== undefined ? "INVOICES" : database.documents !== undefined ? "DOCUMENTS" : database.diagnostics !== undefined ? "DIAGNOSTIC RECORDS" : database.payment_requests !== undefined ? "PAYMENT REQUESTS" : database.fraud_cases !== undefined ? "FRAUD CASES" : "TRANSFER REQUESTS";
  $("#db-status").textContent = `● SQLITE / ${count} ${noun}`;
}
function updateLandingDatabaseStatus() {
  $("#db-status").classList.add("hidden");
}

function renderScenarioMeta() {
  const scenario = state.scenario;
  const category = scenario.category || scenario.domain;
  const vulnerability = scenario.vulnerability_type || "Agent security vulnerability";
  $("#title").textContent = scenario.title;
  $("#scenario-eyebrow").textContent = `${category.toUpperCase()} · ${vulnerability.toUpperCase()}`;
  $("#scenario-context").textContent = `SCENARIO ${String(scenario.number).padStart(2, "0")} OF ${String(scenarioCatalog.length || 9).padStart(2, "0")} · COMPARE THE SAME REQUEST ACROSS POSTURES`;
  $("#severity").textContent = scenario.severity.toUpperCase();
  $("#severity").className = `severity ${scenario.severity.toLowerCase()}`;
  $("#agentic-mechanism").textContent = scenario.agentic_mechanism || "Model-mediated tool use";
  $("#agent-decision").textContent = scenario.agent_decision || "How to pursue the user's goal";
  $("#security-boundary").textContent = scenario.security_boundary || "Application-enforced policy";
  document.title = `Who Let the Agents Act - ${scenario.title}`;
  $("#invoice-upload").classList.toggle("hidden", scenario.id !== "indirect-injection");
  $("#dependency-panel").classList.toggle("hidden", scenario.id !== "approval-service-outage");
  $("#reset-scenario").classList.toggle("hidden", !scenario.runtime_reset_available);
  renderActiveDocument();
  renderDependencyCondition();
  renderScenarioLibrary();
  syncCustomScenarioSelect();
}

function setScenarioView(focused, scroll = false) {
  document.body.classList.toggle("scenario-focused", focused);
  document.body.classList.toggle("scenario-index-page", !focused);
  $("#scenario-index-toggle").classList.toggle("hidden", !focused);
  renderScenarioLibrary();
  if (!focused) {
    $("#scenario-eyebrow").textContent = "WHO LET THE AGENTS ACT · LABS FOR SECURING AI AGENTS";
    $("#title").textContent = "Find the boundary that breaks";
    $("#summary").textContent = "Explore nine realistic agent-security failures, then compare how prompt instructions, model behavior, and application controls change the outcome.";
    $("#scenario-context").textContent = "";
    $("#severity").classList.add("hidden");
    $("#scenario-select").value = "";
    updateLandingDatabaseStatus();
    document.title = "Who Let the Agents Act - Labs for Securing AI Agents";
  } else {
    $("#severity").classList.remove("hidden");
  }
  syncCustomScenarioSelect();
  if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderScenarioLibrary() {
  const grid = $("#scenario-grid");
  if (!grid || !scenarioCatalog.length) return;
  grid.innerHTML = scenarioCatalog.map((item) => {
    const active = document.body.classList.contains("scenario-focused") && item.id === state.scenario?.id;
    const number = String(item.number).padStart(2, "0");
    const category = item.category || item.domain || "Agent security";
    return `<button class="scenario-tile ${active ? "active" : ""}" type="button" role="listitem" data-scenario-id="${escapeHtml(item.id)}" aria-pressed="${active}">
      <span class="scenario-tile-top"><small>${number} · ${escapeHtml(category)}</small><span class="scenario-tile-severity severity ${escapeHtml(String(item.severity || "high").toLowerCase())}">${escapeHtml(String(item.severity || "High").toUpperCase())}</span></span>
      <strong>${escapeHtml(item.title)}</strong>
      <span class="scenario-tile-type">${escapeHtml(item.vulnerability_type || "Agent security scenario")}</span>
      <span class="scenario-tile-summary">${escapeHtml(item.summary || "Explore the failure mode and its application boundary.")}</span>
      <span class="scenario-tile-cta">${active ? "CURRENT SCENARIO" : "OPEN SCENARIO →"}</span>
    </button>`;
  }).join("");
}

function renderActiveDocument() {
  const active = state.scenario?.database?.active_document;
  if (!active) { $("#active-document").textContent = ""; return; }
  $("#active-document").textContent = `ACTIVE DOCUMENT · ${active.document_variant.toUpperCase()} · v${active.document_version} · SHA-256 ${active.document_sha256.slice(0, 12)}…`;
}

function renderDependencyCondition() {
  const dependency = state.scenario?.database?.dependency;
  if (!dependency) return;
  const timedOut = dependency.state === "timeout";
  $("#dependency-indicator").className = `dependency-indicator ${timedOut ? "outage" : "healthy"}`;
  $("#dependency-indicator").textContent = timedOut ? "● SIMULATED OUTAGE" : "● HEALTHY";
  $("#dependency-detail").textContent = timedOut
    ? `Approval requests return no decision after ${dependency.timeout_ms} ms. Run the same payment in all three modes.`
    : "Approval requests return the database-backed policy decision.";
  document.querySelectorAll("[data-dependency-state]").forEach((button) => {
    button.classList.toggle("active", button.dataset.dependencyState === dependency.state);
  });
}

function renderPolicy(fields) {
  $("#field-policy").innerHTML = fields.map((field) => {
    const access = field.access || "catalog";
    return `<span class="field ${access === "deny" ? "denied" : "allowed"}">${escapeHtml(field.field_name || field.name)} · ${escapeHtml(field.classification)} · ${escapeHtml(access.toUpperCase())}</span>`;
  }).join("");
}

function syncCustomScenarioSelect() {
  const select = $("#scenario-select");
  const valueEl = $("#scenario-select-value");
  const menu = $("#scenario-select-menu");
  if (!select || !valueEl || !menu) return;

  const currentVal = select.value;
  const isFocused = document.body.classList.contains("scenario-focused");
  const selectedItem = scenarioCatalog.find((item) => item.id === currentVal);

  if (selectedItem && isFocused) {
    const num = String(selectedItem.number).padStart(2, "0");
    valueEl.textContent = `${num} · ${selectedItem.title}`;
  } else {
    valueEl.textContent = "CHOOSE A SCENARIO";
  }

  const chooseAllActive = !isFocused || !currentVal;
  let html = `
    <button type="button" class="custom-select-option ${chooseAllActive ? "active" : ""}" role="option" data-value="" aria-selected="${chooseAllActive}">
      <span class="custom-select-title">ALL SCENARIOS</span>
      ${chooseAllActive ? '<span class="custom-select-check" aria-hidden="true">✓</span>' : ''}
    </button>
  `;

  html += scenarioCatalog.map((item) => {
    const isSelected = isFocused && item.id === currentVal;
    const num = String(item.number).padStart(2, "0");
    return `
      <button type="button" class="custom-select-option ${isSelected ? "active" : ""}" role="option" data-value="${escapeHtml(item.id)}" aria-selected="${isSelected}">
        <span class="custom-select-num">${num}</span>
        <span class="custom-select-title">${escapeHtml(item.title)}</span>
        ${isSelected ? '<span class="custom-select-check" aria-hidden="true">✓</span>' : ''}
      </button>
    `;
  }).join("");

  menu.innerHTML = html;
}

function toggleCustomSelect(open) {
  const container = $("#custom-scenario-select");
  const trigger = $("#scenario-select-trigger");
  const menu = $("#scenario-select-menu");
  if (!container || !trigger || !menu) return;

  const willOpen = open !== undefined ? open : menu.classList.contains("hidden");
  if (willOpen) {
    menu.classList.remove("hidden");
    container.classList.add("open");
    trigger.setAttribute("aria-expanded", "true");
    const activeOpt = menu.querySelector(".custom-select-option.active") || menu.querySelector(".custom-select-option");
    if (activeOpt) activeOpt.focus();
  } else {
    menu.classList.add("hidden");
    container.classList.remove("open");
    trigger.setAttribute("aria-expanded", "false");
  }
}

async function init() {
  const generation = interactionGeneration;
  const catalogResponse = await fetch(appUrl("/api/scenarios"), { cache: "no-store" });
  if (!catalogResponse.ok) throw new Error("The lab could not load scenarios.");
  const catalog = await catalogResponse.json();
  scenarioCatalog = catalog;
  if (generation !== interactionGeneration) return;
  $("#scenario-select").innerHTML = `<option value="" disabled>CHOOSE A SCENARIO</option>${catalog.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(String(item.number).padStart(2, "0"))} · ${escapeHtml(item.title)}</option>`).join("")}`;
  const selectedScenario = locationScenario();
  $("#scenario-select").value = selectedScenario || catalog[0].id;
  const [scenarioResponse, healthResponse, capacityResponse] = await Promise.all([fetch(appUrl(`/api/scenario?scenario_id=${encodeURIComponent($("#scenario-select").value)}`), { cache: "no-store" }), fetch(appUrl("/api/health"), { cache: "no-store" }), fetch(appUrl("/api/capacity"), { cache: "no-store" })]);
  if (generation !== interactionGeneration) return;
  if (!scenarioResponse.ok || !healthResponse.ok || !capacityResponse.ok) throw new Error("The lab could not initialize.");
  state.scenario = await scenarioResponse.json();
  const health = await healthResponse.json();
  state.capacity = await capacityResponse.json();
  renderScenarioMeta();
  $("#summary").textContent = state.scenario.summary;
  $("#lesson").textContent = state.scenario.lesson;
  $("#groq-status").textContent = health.groq_configured ? `● GROQ / ${health.model}` : "○ GROQ NOT CONFIGURED";
  if (selectedScenario) updateDatabaseStatus(state.scenario.database);
  else updateLandingDatabaseStatus();
  $("#database-path").textContent = state.scenario.database.path;
  renderPolicy(state.scenario.field_policy);
  setMode("vulnerable");
  setPreset("normal");
  setScenarioView(Boolean(selectedScenario));
  syncCustomScenarioSelect();
  if (selectedScenario && window.location.pathname !== appUrl(`/lab/${encodeURIComponent(selectedScenario)}`)) history.replaceState(null, "", appUrl(`/lab/${encodeURIComponent(selectedScenario)}`));
}

async function switchScenario() {
  interactionGeneration += 1;
  const generation = interactionGeneration;
  const id = $("#scenario-select").value;
  if (!id) return;
  const response = await fetch(appUrl(`/api/scenario?scenario_id=${encodeURIComponent(id)}`), { cache: "no-store" });
  if (generation !== interactionGeneration) return;
  state.scenario = await response.json();
  history.replaceState(null, "", appUrl(`/lab/${encodeURIComponent(id)}`));
  renderScenarioMeta(); $("#summary").textContent = state.scenario.summary; $("#lesson").textContent = state.scenario.lesson;
  $("#database-path").textContent = state.scenario.database.path;
  updateDatabaseStatus(state.scenario.database);
  renderPolicy(state.scenario.field_policy);
  setMode("vulnerable"); setPreset("normal");
  setScenarioView(true, true);
}

function showScenarioIndex() {
  history.replaceState(null, "", appUrl("/"));
  setScenarioView(false, true);
  window.setTimeout(() => $("#scenario-library").scrollIntoView({ behavior: "smooth", block: "start" }), 80);
}

async function uploadInvoice() {
  const file = $("#invoice-file").files[0];
  if (!file) { $("#upload-status").textContent = "Choose a document first."; return; }
  const button = $("#upload-invoice");
  button.disabled = true;
  $("#upload-status").textContent = `Reading ${file.name}…`;
  try {
    const response = await fetch(appUrl(`/api/scenarios/indirect-injection/invoices/upload?invoice_id=INV-884&filename=${encodeURIComponent(file.name)}`), { method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "The invoice upload failed.");
    $("#upload-status").textContent = `Uploaded ${payload.filename} to ${payload.invoice_id} (${payload.characters} text characters). Run the agent to inspect it.`;
    await refreshScenarioState();
  } catch (error) { $("#upload-status").textContent = error.message; }
  finally { button.disabled = false; }
}

async function refreshScenarioState() {
  const response = await fetch(appUrl(`/api/scenario?scenario_id=${encodeURIComponent(state.scenario.id)}`), { cache: "no-store" });
  if (!response.ok) throw new Error("The scenario state could not be refreshed.");
  state.scenario = await response.json();
  updateDatabaseStatus(state.scenario.database);
  renderPolicy(state.scenario.field_policy);
  renderActiveDocument();
  renderDependencyCondition();
}

async function setDependencyState(dependencyState) {
  const buttons = document.querySelectorAll("[data-dependency-state]");
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const response = await fetch(appUrl(`/api/scenarios/approval-service-outage/dependency/${encodeURIComponent(dependencyState)}`), { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "The dependency simulator could not be changed.");
    await refreshScenarioState();
    clearResult();
  } catch (error) { renderError(error.message); }
  finally { buttons.forEach((button) => { button.disabled = false; }); }
}

async function loadInvoiceFixture(variant) {
  $("#upload-status").textContent = `Loading ${variant} fixture…`;
  const response = await fetch(appUrl(`/api/scenarios/indirect-injection/invoices/fixture/${encodeURIComponent(variant)}`), { method: "POST" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "The invoice fixture could not be loaded.");
  $("#upload-status").textContent = `Loaded ${payload.variant} fixture (${payload.filename}).`;
  await refreshScenarioState();
}

async function resetScenario() {
  const button = $("#reset-scenario");
  button.disabled = true;
  try {
    const response = await fetch(appUrl(`/api/scenarios/${encodeURIComponent(state.scenario.id)}/reset`), { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "The scenario could not be reset.");
    await refreshScenarioState();
    clearResult();
    if (state.scenario.id === "indirect-injection") $("#upload-status").textContent = "Clean invoice restored and runtime audit state cleared.";
  } catch (error) { renderError(error.message); }
  finally { button.disabled = false; }
}

async function resetSession() {
  if (!window.confirm("Reset all scenario state for this browser session?")) return;
  const button = $("#reset-session");
  button.disabled = true;
  try {
    const response = await fetch(appUrl("/api/session/reset"), { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "The session could not be reset.");
    await refreshScenarioState();
    clearResult();
    $("#reset-status").textContent = "All scenario state was reset for this browser session.";
  } catch (error) { renderError(error.message); }
  finally { button.disabled = false; }
}

function activeSystemPrompt() {
  if (state.scenario.id === "multi-agent-confused-deputy") {
    const prompts = state.scenario.system_prompts;
    const sequence = [
      `--- 1 · CASE COORDINATOR ---\n${prompts.planner}`,
      `--- 2 · FRAUD REVIEW AGENT ---\n${prompts.fraud_review_agent}`,
    ];
    if (state.mode === "prompt_only") sequence.push(`--- 3 · MODEL HANDOFF GUARD ---\n${prompts.prompt_only_guard}`);
    sequence.push(`--- ${state.mode === "prompt_only" ? 4 : 3} · ACCOUNT CONTROL AGENT ---\n${prompts.account_control_agent}`);
    if (state.mode === "hardened") sequence.push(`--- 4 · HARDENED RESPONSE ---\n${prompts.hardened_response}`);
    sequence.push(`--- UNSUPPORTED RESPONSE ---\n${prompts.unsupported_response}`);
    return sequence.join("\n\n");
  }
  const observation = state.scenario.system_prompts.observation_action ? `\n\n--- POST-TOOL REPLANNING ---\n${state.scenario.system_prompts.observation_action}` : "";
  const unsupported = `\n\n--- UNSUPPORTED RESPONSE ---\n${state.scenario.system_prompts.unsupported_response}`;
  if (state.mode === "prompt_only") return `${state.scenario.system_prompts.prompt_only_guard}\n\n--- TOOL PLANNER ---\n${state.scenario.system_prompts.planner}${observation}${unsupported}`;
  if (state.mode === "hardened") return `${state.scenario.system_prompts.planner}${observation}\n\n--- HARDENED RESPONSE ---\n${state.scenario.system_prompts.hardened_response}${unsupported}`;
  return `${state.scenario.system_prompts.planner}${observation}${unsupported}`;
}

function setMode(mode) {
  state.mode = mode;
  $("#mode-description").textContent = state.scenario?.mode_copy?.[mode] || modeCopy[mode];
  $("#flow-note").textContent = flowNotes[mode];
  document.querySelectorAll(".mode").forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $("#system-prompt").textContent = activeSystemPrompt();
  clearResult();
}

let currentRunResult = null;
let currentComparisonResults = null;
let interactionGeneration = 0;

function setPreset(preset) {
  state.preset = preset;
  $("#prompt").value = state.scenario.prompts[preset];
  document.querySelectorAll(".preset").forEach((button) => button.classList.toggle("active", button.dataset.preset === preset));
  $("#download-clean").classList.toggle("hidden", preset !== "normal");
  $("#download-attack").classList.toggle("hidden", preset !== "attack");
  $("#download-bypass").classList.toggle("hidden", preset !== "bypass");
  $("#preset-hint").textContent = presetCopy[preset]?.hint || "";
}

function markCustom() {
  if ($("#prompt").value === state.scenario.prompts[state.preset]) return;
  state.preset = "custom";
  document.querySelectorAll(".preset").forEach((button) => button.classList.remove("active"));
  ["#download-clean", "#download-attack", "#download-bypass"].forEach((selector) => $(selector).classList.add("hidden"));
  $("#preset-hint").textContent = presetCopy.custom.hint;
}

function clearResult() {
  currentRunResult = null;
  currentComparisonResults = null;
  $("#empty").classList.remove("hidden");
  $("#empty").classList.remove("pending");
  $("#empty").innerHTML = emptyState;
  $("#result").classList.add("hidden");
  $("#comparison").classList.add("hidden");
  $("#comparison").innerHTML = "";
  $("#trace-section").classList.add("hidden");
  $("#badge").textContent = "WAITING";
}

function showPending(message, detail) {
  $("#empty").classList.remove("hidden");
  $("#empty").classList.add("pending");
  $("#empty").innerHTML = `<span class="empty-mark" aria-hidden="true">•••</span><strong>${escapeHtml(message)}</strong><p>${escapeHtml(detail)}</p>`;
}

async function requestRun(mode, prompt) {
  showPending("The agent is working", "Planning, tool execution, and security checks will appear here when the run completes.");
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), RUN_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(appUrl("/api/run"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_id: state.scenario.id, mode, prompt }),
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The agent took too long to respond. Please try again.");
    throw new Error("The agent request could not be completed. Please try again.");
  } finally {
    window.clearTimeout(timeoutId);
  }
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 429) throw new Error(payload.detail || "Demo capacity is cooling down. Please try again shortly.");
    if (response.status === 503) throw new Error(payload.detail || "The demo is temporarily unavailable. Please try again later.");
    throw new Error(payload.detail || "The agent run failed.");
  }
  try {
    const capacityResponse = await fetch(appUrl("/api/capacity"), { cache: "no-store" });
    if (capacityResponse.ok) state.capacity = await capacityResponse.json();
  } catch (error) {
    // A capacity refresh should not turn a completed agent run into an error.
  }
  return payload;
}

async function runAgent() {
  const prompt = $("#prompt").value.trim();
  if (!prompt) return;
  const generation = interactionGeneration;
  const button = $("#run");
  button.disabled = true;
  button.firstElementChild.textContent = "RUNNING…";
  clearResult();
  $("#badge").textContent = "AGENT RUNNING";
  showPending("The agent is working", "Planning, tool execution, and security checks will appear here when the run completes.");
  try {
    const payload = await requestRun(state.mode, prompt);
    if (generation !== interactionGeneration) return;
    renderResult(payload);
  } catch (error) {
    if (generation !== interactionGeneration) return;
    renderError(error.message);
  } finally {
    if (generation === interactionGeneration) {
      button.disabled = false;
      button.firstElementChild.textContent = "RUN AGENT";
    }
  }
}

async function compareModes() {
  const prompt = $("#prompt").value.trim();
  if (!prompt) return;
  const generation = interactionGeneration;
  const button = $("#compare");
  button.disabled = true;
  button.textContent = "COMPARING…";
  clearResult();
  try {
    const modes = ["vulnerable", "prompt_only", "hardened"];
    const results = [];
    $("#empty").classList.add("hidden");
    $("#comparison").classList.remove("hidden");
    $("#badge").textContent = "COMPARISON RUNNING";
    $("#comparison").innerHTML = modes.map((mode, index) => `
      <article class="comparison-card ${escapeHtml(mode)}" data-comparison-mode="${escapeHtml(mode)}">
        <div class="comparison-card-top">
          <small>${escapeHtml(mode.replace("_", "-"))}</small>
          <span class="verdict-tag">${index === 0 ? "RUNNING" : "QUEUED"}</span>
        </div>
        <p>${index === 0 ? "Planning and executing this posture…" : "Waiting for the previous posture to finish."}</p>
      </article>`).join("");
    for (let index = 0; index < modes.length; index += 1) {
      const mode = modes[index];
      if (generation !== interactionGeneration) return;
      const card = document.querySelector(`[data-comparison-mode="${mode}"]`);
      if (!card) return;
      card.className = `comparison-card ${escapeHtml(mode)} running`;
      card.innerHTML = `
        <div class="comparison-card-top">
          <small>${escapeHtml(mode.replace("_", "-"))}</small>
          <span class="verdict-tag">RUNNING</span>
        </div>
        <p>Planning, executing, and checking this posture…</p>`;
      const result = await requestRun(mode, prompt);
      if (generation !== interactionGeneration) return;
      results.push(result);
      card.className = `comparison-card ${escapeHtml(mode)} ${escapeHtml(result.verdict)}`;
      card.innerHTML = `
        <div class="comparison-card-top">
          <small>${escapeHtml(result.mode.replace("_", "-"))}</small>
          <span class="verdict-tag">${escapeHtml(result.verdict)}</span>
        </div>
        <p>${escapeHtml(result.summary)}</p>
        <div class="comparison-trace">${result.trace.slice(-3).map((event) => `<span class="trace-chip ${escapeHtml(event.status)}">${escapeHtml(event.stage)}</span>`).join("")}</div>
        <pre>${escapeHtml(result.response)}</pre>`;
      const next = document.querySelector(`[data-comparison-mode="${modes[index + 1]}"]`);
      if (next) {
        next.className = `comparison-card ${escapeHtml(modes[index + 1])} running`;
        next.innerHTML = `
          <div class="comparison-card-top">
            <small>${escapeHtml(modes[index + 1].replace("_", "-"))}</small>
            <span class="verdict-tag">RUNNING</span>
          </div>
          <p>Planning and executing this posture…</p>`;
      }
    }
    currentComparisonResults = results;
    currentRunResult = null;
    $("#badge").textContent = "THREE-POSTURE COMPARISON";
  } catch (error) {
    if (generation === interactionGeneration) {
      renderError(error.message);
    }
  }
  finally {
    if (generation === interactionGeneration) {
      button.disabled = false;
      button.textContent = "COMPARE MODES";
    }
  }
}

function renderResult(result) {
  currentRunResult = result;
  currentComparisonResults = null;
  $("#empty").classList.add("hidden");
  $("#result").classList.remove("hidden");
  $("#trace-section").classList.remove("hidden");
  $("#badge").textContent = result.badge;
  $("#verdict").textContent = result.verdict;
  $("#response").textContent = result.response;
  $("#result-summary").textContent = result.summary;
  const safe = ["allowed", "contained", "refused"].includes(result.verdict);
  $("#verdict-dot").className = safe ? "safe" : "danger";
  $("#response").className = safe ? "safe-border" : "danger-border";
  $("#trace").classList.toggle("multi-agent-trace", result.scenario_id === "multi-agent-confused-deputy");
  $("#trace").style.setProperty("--trace-count", result.trace.length);
  $("#trace").innerHTML = result.trace.map((event, index) => `
    <article class="trace-item ${event.status}">
      <div class="trace-item-top">
        <span class="trace-step-num">${String(index + 1).padStart(2, "0")}</span>
        <small>${escapeHtml(event.stage)}</small>
        <span class="trace-arrow">→</span>
      </div>
      <h3>${escapeHtml(event.title)}</h3>
      <p>${escapeHtml(event.detail)}</p>
    </article>`).join("");
  renderChips("#controls", result.controls, "No deterministic control");
  renderChips("#evidence", result.evidence, "No evidence");
  $("#artifacts").innerHTML = result.artifacts.map((name) => `<a href="${appUrl(`/api/runs/${encodeURIComponent(result.run_id)}/${encodeURIComponent(name)}`)}" target="_blank" rel="noreferrer">${escapeHtml(name)} ↗</a>`).join("");
}

function renderChips(selector, values, empty) {
  $(selector).innerHTML = (values.length ? values : [empty]).map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("");
}

function renderError(message) {
  $("#empty").classList.add("hidden");
  $("#result").classList.remove("hidden");
  $("#badge").textContent = "RUN FAILED";
  $("#verdict").textContent = "error";
  $("#response").textContent = message;
  $("#result-summary").textContent = "No scripted fallback was used. Fix the model or database error and run again.";
}

document.addEventListener("DOMContentLoaded", () => {
  init().catch((error) => renderError(error.message));
  document.querySelectorAll(".mode").forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
  document.querySelectorAll(".preset").forEach((button) => button.addEventListener("click", () => setPreset(button.dataset.preset)));
  $("#prompt").addEventListener("input", markCustom);
  $("#run").addEventListener("click", runAgent);
  $("#compare").addEventListener("click", compareModes);
  $("#upload-invoice").addEventListener("click", uploadInvoice);
  $("#reset-scenario").addEventListener("click", resetScenario);
  $("#reset-session").addEventListener("click", resetSession);
  document.querySelectorAll("[data-invoice-fixture]").forEach((button) => button.addEventListener("click", () => loadInvoiceFixture(button.dataset.invoiceFixture).catch((error) => { $("#upload-status").textContent = error.message; })));
  document.querySelectorAll("[data-dependency-state]").forEach((button) => button.addEventListener("click", () => setDependencyState(button.dataset.dependencyState)));
  $("#scenario-grid").addEventListener("click", (event) => {
    const tile = event.target.closest("[data-scenario-id]");
    if (!tile) return;
    $("#scenario-select").value = tile.dataset.scenarioId;
    switchScenario().catch((error) => renderError(error.message));
  });
  $("#scenario-index-toggle").addEventListener("click", showScenarioIndex);
  const customTrigger = $("#scenario-select-trigger");
  const customMenu = $("#scenario-select-menu");
  const customContainer = $("#custom-scenario-select");

  if (customTrigger && customMenu && customContainer) {
    customTrigger.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleCustomSelect();
    });

    customMenu.addEventListener("click", (event) => {
      const option = event.target.closest(".custom-select-option");
      if (!option) return;
      const val = option.dataset.value;
      toggleCustomSelect(false);
      customTrigger.focus();
      if (!val) {
        showScenarioIndex();
      } else if (val !== $("#scenario-select").value || !document.body.classList.contains("scenario-focused")) {
        $("#scenario-select").value = val;
        switchScenario().catch((error) => renderError(error.message));
        syncCustomScenarioSelect();
      }
    });

    document.addEventListener("click", (event) => {
      if (!event.target.closest("#custom-scenario-select")) {
        toggleCustomSelect(false);
      }
    });

    customContainer.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        toggleCustomSelect(false);
        customTrigger.focus();
        return;
      }
      const isMenuOpen = !customMenu.classList.contains("hidden");
      if (!isMenuOpen) {
        if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggleCustomSelect(true);
        }
        return;
      }
      const options = Array.from(customMenu.querySelectorAll(".custom-select-option"));
      const currentIndex = options.indexOf(document.activeElement);
      if (event.key === "ArrowDown") {
        event.preventDefault();
        const next = (currentIndex + 1) % options.length;
        options[next].focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        const prev = (currentIndex - 1 + options.length) % options.length;
        options[prev].focus();
      } else if (event.key === "Tab") {
        toggleCustomSelect(false);
      }
    });
  }

  $("#prompt").addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") runAgent();
  });

  $("#scenario-select").addEventListener("change", () => {
    syncCustomScenarioSelect();
    switchScenario().catch((error) => renderError(error.message));
  });
});
