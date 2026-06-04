const stateEl = document.querySelector("#state");
const form = document.querySelector("#query-form");
const providerSelect = document.querySelector("#provider");
const snapshotSummary = document.querySelector("#snapshot-summary");
const observationEl = document.querySelector("#input-observation");
const recommendationsEl = document.querySelector("#recommendations");
const alternativesEl = document.querySelector("#alternatives");
const warningsEl = document.querySelector("#warnings");
const provenanceEl = document.querySelector("#provenance");

function text(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function setState(message, tone = "info") {
  stateEl.hidden = !message;
  stateEl.dataset.tone = tone;
  stateEl.textContent = message || "";
}

async function loadMeta() {
  const [providersResponse, metaResponse] = await Promise.all([
    fetch("/api/providers"),
    fetch("/api/meta"),
  ]);
  const providersPayload = await providersResponse.json();
  const metaPayload = await metaResponse.json();

  providerSelect.replaceChildren(
    ...providersPayload.providers.map((provider) => {
      const option = document.createElement("option");
      option.value = provider;
      option.textContent = provider;
      option.selected = provider === providersPayload.default;
      return option;
    }),
  );

  snapshotSummary.textContent = [
    `snapshot ${metaPayload.meta.kg_snapshot_id}`,
    metaPayload.snapshot.source,
    metaPayload.snapshot.path,
  ].join(" · ");
}

function renderKeyValues(target, rows) {
  target.replaceChildren();
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = text(value);
    target.append(dt, dd);
  }
}

function renderResponse(payload) {
  const response = payload.response;
  const observation = response.input_observations[0] || null;
  renderKeyValues(observationEl, [
    ["query_text", observation?.query_text],
    ["surface_id", observation?.surface_id],
    ["provider", response.provider],
    ["query_mode", observation?.query_mode || payload.request.query_mode],
    ["total", observation?.total],
    ["status", observation?.status],
    ["recall_bucket", observation?.recall_bucket],
    ["observed_at", observation?.observed_at],
    ["observation_id", observation?.observation_id],
    ["evidence_ref", observation?.evidence_ref],
  ]);

  recommendationsEl.replaceChildren(
    ...response.recommendations.map((recommendation) => {
      const row = document.createElement("p");
      row.innerHTML = `<span class="pill">${recommendation.action}</span> ${text(recommendation.query_text)} → ${text(recommendation.recommended_query_text)} · ${text(recommendation.reason_code)} · ${text(recommendation.reason)}`;
      return row;
    }),
  );

  alternativesEl.replaceChildren(
    ...response.alternatives.map((alternative) => {
      const observationRow = alternative.observation || {};
      const tr = document.createElement("tr");
      for (const value of [
        alternative.query_text,
        alternative.relation_type,
        alternative.confidence,
        alternative.source_concept_id,
        alternative.source_surface_id,
        alternative.target_surface_id,
        observationRow.total,
        observationRow.status,
        observationRow.recall_bucket,
        observationRow.observed_at,
        alternative.evidence_ref || alternative.evidence_type,
      ]) {
        const td = document.createElement("td");
        td.textContent = text(value);
        tr.append(td);
      }
      return tr;
    }),
  );

  warningsEl.replaceChildren(
    ...response.warnings.map((warning) => {
      const item = document.createElement("p");
      item.textContent = `${warning.code}: ${warning.message}`;
      return item;
    }),
  );
  provenanceEl.textContent = JSON.stringify(response.lineage, null, 2);
}

async function submitQueryRecall(event) {
  event.preventDefault();
  setState("");
  const formData = new FormData(form);
  const payload = {
    query_text: formData.get("query_text"),
    provider: formData.get("provider"),
    query_mode: formData.get("query_mode"),
    max_alternatives: Number(formData.get("max_alternatives") || 10),
  };

  const response = await fetch("/api/query-recall", {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    setState(`${body.error.code}: ${body.error.message}`, "error");
    if (body.error.details && body.error.details.response) {
      renderResponse({
        request: payload,
        response: body.error.details.response,
      });
    }
    return;
  }
  renderResponse(body);
}

form.addEventListener("submit", submitQueryRecall);
loadMeta().catch((error) => {
  setState(`internal_error: ${error.message}`, "error");
});
