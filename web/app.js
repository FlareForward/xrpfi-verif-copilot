const runButton = document.querySelector("#run-demo");
const emptyState = document.querySelector("#empty-state");
const loadingState = document.querySelector("#loading-state");
const errorState = document.querySelector("#error-state");
const resultState = document.querySelector("#result-state");
const errorMessage = document.querySelector("#error-message");
const steps = [...document.querySelectorAll("#steps li")];
const flowNodes = [...document.querySelectorAll(".flow-node")];
const tickerFlr = document.querySelector("#ticker-flr");
const tickerXrp = document.querySelector("#ticker-xrp");
const tickerStatus = document.querySelector("#ticker-status");

const escapeHtml = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const formatNumber = (value, digits = 2) =>
  Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });

const formatUsd = (value, digits = 2) => `$${formatNumber(value, digits)}`;

const formatTimestamp = (timestamp) => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "timestamp unavailable";
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const setState = (state) => {
  emptyState.classList.toggle("hidden", state !== "empty");
  loadingState.classList.toggle("hidden", state !== "loading");
  errorState.classList.toggle("hidden", state !== "error");
  resultState.classList.toggle("hidden", state !== "result");
  runButton.disabled = state === "loading";
  document.body.classList.toggle("is-running", state === "loading");
};

const setStepProgress = (mode) => {
  steps.forEach((step, index) => {
    step.classList.toggle("active", mode === "loading" && index === 0);
    step.classList.toggle("done", mode === "done");
  });
  flowNodes.forEach((node, index) => {
    node.classList.toggle("active", mode === "loading" ? index === 0 : index === 0);
    node.classList.toggle("done", mode === "done");
  });
};

const proofBadge = (record) => {
  const explorer = record.zero_g?.inft_explorer_url;
  if (explorer) {
    return `<a class="badge-link badge-link-success" href="${escapeHtml(explorer)}" target="_blank" rel="noreferrer">iNFT Token ${escapeHtml(record.zero_g.inft_token_id || "1")} ↗</a>`;
  }
  if (record.zero_g?.storage_tx_hash) {
    return `<span class="badge-link badge-link-muted">0G ${escapeHtml(record.zero_g.storage_tx_hash.slice(0, 10))}...</span>`;
  }
  return `<span class="badge-link badge-link-muted">Storage pending</span>`;
};

const priceTags = (prices = []) =>
  prices
    .map(
      (price) =>
        `<span class="price-tag">${escapeHtml(price.feed_name)} ${escapeHtml(formatUsd(price.price_usd, 4))}</span>`,
    )
    .join("");

const item = (label, title, detail) => `
  <article class="item">
    <span>${escapeHtml(label)}</span>
    <strong>${escapeHtml(title)}</strong>
    <p>${escapeHtml(detail)}</p>
  </article>
`;

const decision = (record, index) => `
  <details class="decision"${index === 0 ? " open" : ""}>
    <summary>
      <span>
        <strong>${index + 1}. ${escapeHtml(record.agent_ens)}</strong>
        <small>${escapeHtml(record.action_taken)}</small>
      </span>
      <code>${escapeHtml(record.action_type)}</code>
    </summary>
    <div>
      <div class="decision-meta">
        <span class="agent-pill">${escapeHtml(record.agent_ens)}</span>
        ${priceTags(record.ftso_prices)}
        ${proofBadge(record)}
      </div>
      <p class="reasoning">${escapeHtml(record.reasoning)}</p>
      <p>${escapeHtml(record.result_summary)}</p>
      <dl>
        <div>
          <dt>Input</dt>
          <dd>${escapeHtml(record.input_summary || "n/a")}</dd>
        </div>
        <div>
          <dt>Timestamp</dt>
          <dd>${escapeHtml(formatTimestamp(record.timestamp))}</dd>
        </div>
      </dl>
    </div>
  </details>
`;

const renderResult = (result) => {
  document.querySelector("#xrp-amount").textContent = `${formatNumber(result.xrp_amount)} XRP`;
  document.querySelector("#fxrp-amount").textContent = `${formatNumber(result.fxrp_minted)} FXRP`;
  document.querySelector("#decision-count").textContent = result.decisions.length;

  document.querySelector("#agents").innerHTML = result.agents
    .map((agent) => item(agent.ens, agent.address, "Resolved identity used by the agent flow."))
    .join("");

  document.querySelector("#prices").innerHTML = result.prices
    .map((price) =>
      item(
        price.feed_name,
        formatUsd(price.price_usd, 4),
        `Feed ${price.feed_id.slice(0, 18)}... ${price.is_stale ? "cached fallback" : "live read"}`,
      ),
    )
    .join("");

  document.querySelector("#decisions").innerHTML = result.decisions
    .map((record, index) => decision(record, index))
    .join("");

  const proofUrl = result.inft_url || "#";
  document.querySelector("#proof-url").textContent = proofUrl;
  document.querySelector("#proof-link").href = proofUrl;
};

const refreshTicker = async () => {
  try {
    const response = await fetch("/prices", { cache: "no-store" });
    const prices = await response.json();
    if (!response.ok) {
      throw new Error("Price endpoint unavailable.");
    }

    tickerFlr.textContent = formatUsd(prices.flr_usd, 4);
    tickerXrp.textContent = formatUsd(prices.xrp_usd, 2);
    tickerStatus.textContent = `${prices.is_stale ? "Cached" : "Live"} FTSO snapshot · ${formatTimestamp(
      prices.timestamp,
    )}`;
    tickerStatus.classList.toggle("stale", Boolean(prices.is_stale));
    tickerStatus.classList.add("updated");
    window.setTimeout(() => tickerStatus.classList.remove("updated"), 1000);
  } catch (error) {
    tickerStatus.textContent = "Price ticker offline";
    tickerStatus.classList.add("stale");
  }
};

runButton.addEventListener("click", async () => {
  setStepProgress("loading");
  setState("loading");

  try {
    const response = await fetch("/api/run", { method: "POST" });
    const payload = await response.json();

    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || "The demo server returned an error.");
    }

    renderResult(payload.result);
    setStepProgress("done");
    setState("result");
    refreshTicker();
  } catch (error) {
    errorMessage.textContent = error instanceof Error ? error.message : String(error);
    setStepProgress("empty");
    setState("error");
  }
});

refreshTicker();
setInterval(refreshTicker, 30000);
