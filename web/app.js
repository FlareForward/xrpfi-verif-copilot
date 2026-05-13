const runButton = document.querySelector("#run-demo");
const emptyState = document.querySelector("#empty-state");
const loadingState = document.querySelector("#loading-state");
const errorState = document.querySelector("#error-state");
const resultState = document.querySelector("#result-state");
const errorMessage = document.querySelector("#error-message");
const steps = [...document.querySelectorAll("#steps li")];
const flowSteps = [...document.querySelectorAll("#flow-steps li")];
const flowNodes = [...document.querySelectorAll(".flow-node")];
const stepStatus = document.querySelector("#step-status");
const tickerFlr = document.querySelector("#ticker-flr");
const tickerXrp = document.querySelector("#ticker-xrp");
const tickerStatus = document.querySelector("#ticker-status");
const gallery = document.querySelector("#gallery");
const galleryCount = document.querySelector("#gallery-count");
const galleryRefresh = document.querySelector("#gallery-refresh");
let eventSource = null;

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

const ZERO_G_INFT_URL =
  "https://chainscan.0g.ai/tx/0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd";

const formatTimestamp = (timestamp) => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "timestamp unavailable";
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const formatSessionTimestamp = (timestamp) => {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "timestamp unavailable";
  }
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const truncateHash = (value) => {
  if (!value) {
    return "unavailable";
  }
  const text = String(value);
  if (text.length <= 18) {
    return text;
  }
  return `${text.slice(0, 10)}...${text.slice(-6)}`;
};

const formatDuration = (seconds) => {
  const numericSeconds = Number(seconds);
  if (!Number.isFinite(numericSeconds) || numericSeconds < 0) {
    return "Duration pending";
  }
  if (numericSeconds < 60) {
    return `${Math.round(numericSeconds)}s`;
  }
  const minutes = Math.floor(numericSeconds / 60);
  const remainder = Math.round(numericSeconds % 60);
  return `${minutes}m ${remainder}s`;
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
  flowSteps.forEach((step, index) => {
    step.classList.toggle("active", mode === "loading" && index === 0);
    step.classList.toggle("done", mode === "done");
  });
  flowNodes.forEach((node, index) => {
    node.classList.toggle("active", mode === "loading" ? index === 0 : index === 0);
    node.classList.toggle("done", mode === "done");
  });
};

const resetLiveSteps = () => {
  stepStatus.textContent = "Waiting";
  steps.forEach((step) => {
    step.classList.remove("active", "done", "warn");
    step.querySelector("p").textContent = "Waiting";
  });
  flowSteps.forEach((step) => {
    step.classList.remove("active", "done", "warn");
  });
};

const renderStep = (stepNumber, label, value, status) => {
  const step = steps.find((item) => item.dataset.step === String(stepNumber));
  const flowStep = flowSteps.find((item) => item.dataset.step === String(stepNumber));
  if (!step) {
    return;
  }

  step.classList.remove("active");
  step.classList.add(status === "warn" ? "warn" : "done");
  step.querySelector("strong").textContent = label;
  step.querySelector("p").textContent = value;
  stepStatus.textContent = `Step ${stepNumber}/10`;

  if (flowStep) {
    flowStep.classList.remove("active");
    flowStep.classList.add(status === "warn" ? "warn" : "done");
  }

  const nextStep = steps.find((item) => item.dataset.step === String(Number(stepNumber) + 1));
  const nextFlowStep = flowSteps.find(
    (item) => item.dataset.step === String(Number(stepNumber) + 1),
  );
  if (nextStep) {
    nextStep.classList.add("active");
  }
  if (nextFlowStep) {
    nextFlowStep.classList.add("active");
  }
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

const statusBadge = (status, label = status) =>
  `<span class="status-badge status-${escapeHtml(status.toLowerCase())}">${escapeHtml(label)}</span>`;

const receiptRow = (label, value, status, statusLabel = status) => `
  <div class="receipt-row">
    <dt>${escapeHtml(label)}</dt>
    <dd>
      <span>${escapeHtml(value || "Unavailable")}</span>
      ${statusBadge(status, statusLabel)}
    </dd>
  </div>
`;

const receiptTimestamp = (result, record) =>
  result.session?.timestamp || record.timestamp || new Date().toISOString();

const receiptId = (result, index) => {
  const sessionId = result.session?.session_id || "session pending";
  return `${sessionId}${result.decisions.length > 1 ? `-${index + 1}` : ""}`;
};

const agentRole = (agentEns = "") =>
  agentEns.includes("yield-router") ? "yield-router.eth" : "mint-helper.eth";

const inputRows = (record) => {
  const rows = (record.ftso_prices || []).map((price) =>
    receiptRow(
      price.feed_name,
      `${formatUsd(price.price_usd, 4)} · feed ${truncateHash(price.feed_id)}`,
      price.is_stale ? "FIXTURE" : "LIVE",
      price.is_stale ? "FIXTURE" : "LIVE",
    ),
  );

  if (record.fdc_proof) {
    rows.push(
      receiptRow(
        "FDC proof",
        record.fdc_proof.proof_hash,
        record.fdc_proof.verified ? "LIVE" : "FIXTURE",
        record.fdc_proof.verified ? "LIVE" : "FIXTURE",
      ),
    );
  }

  if (record.action_type === "route") {
    rows.push(receiptRow("Uniswap quote", "WETH/USDC quote fixture", "FIXTURE"));
  }

  return rows.join("");
};

const proofRows = (record) => {
  const rows = [
    receiptRow("Agent identity", agentRole(record.agent_ens), "FIXTURE"),
    receiptRow("FAssets mint", "Stub transaction parameters; no broadcast", "FIXTURE"),
    receiptRow("Gensyn AXL", "Local AXL-compatible handoff", "FIXTURE"),
    receiptRow("0G storage", "Upload planned; local SHA-256 fallback", "PLANNED"),
  ];

  const inftUrl = record.zero_g?.inft_explorer_url || ZERO_G_INFT_URL;
  rows.push(
    `
      <div class="receipt-row">
        <dt>0G iNFT</dt>
        <dd>
          <a href="${escapeHtml(inftUrl)}" target="_blank" rel="noreferrer">
            token=${escapeHtml(record.zero_g?.inft_token_id || "1")}
          </a>
          ${statusBadge("LIVE")}
        </dd>
      </div>
    `,
  );

  return rows.join("");
};

const receiptCard = (result, record, index) => `
  <article class="receipt-card">
    <header class="receipt-card-header">
      <div>
        <span>Receipt ID</span>
        <strong>${escapeHtml(receiptId(result, index))}</strong>
      </div>
      <time datetime="${escapeHtml(receiptTimestamp(result, record))}">
        ${escapeHtml(formatSessionTimestamp(receiptTimestamp(result, record)))}
      </time>
    </header>

    <section class="receipt-block">
      <h3>Agent</h3>
      <p>${escapeHtml(agentRole(record.agent_ens))}</p>
    </section>

    <section class="receipt-block">
      <h3>Data Inputs Used</h3>
      <dl>${inputRows(record)}</dl>
    </section>

    <section class="receipt-block">
      <h3>Decision Taken</h3>
      <p>${escapeHtml(record.action_taken || record.result_summary || "Decision unavailable")}</p>
      <small>${escapeHtml(record.reasoning || "No reasoning supplied.")}</small>
    </section>

    <section class="receipt-block">
      <h3>Proof Status</h3>
      <dl>${proofRows(record)}</dl>
    </section>
  </article>
`;

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

const galleryProof = (session) => {
  if (session.storage_is_real && session.inft_token_id && session.inft_explorer_url) {
    return `<a class="gallery-proof-link" href="${escapeHtml(session.inft_explorer_url)}" target="_blank" rel="noreferrer">iNFT Token ${escapeHtml(session.inft_token_id)} ↗</a>`;
  }
  if (session.storage_is_real && session.inft_token_id) {
    return `<span class="gallery-proof-link">iNFT Token ${escapeHtml(session.inft_token_id)}</span>`;
  }
  return `<span class="gallery-fallback">⚠ storage fallback</span>`;
};

const galleryCard = (session) => {
  const completed = Number.isFinite(Number(session.steps_completed))
    ? Number(session.steps_completed)
    : 0;
  const total = Number.isFinite(Number(session.steps_total)) ? Number(session.steps_total) : 10;
  const hash = session.storage_tx_hash || "";
  const sessionId = session.session_id || "session unavailable";
  return `
    <article class="gallery-card">
      <div class="gallery-card-top">
        <div>
          <time datetime="${escapeHtml(session.timestamp || "")}">${escapeHtml(
            formatSessionTimestamp(session.timestamp),
          )}</time>
          <small>${escapeHtml(sessionId)}</small>
        </div>
        <span class="gallery-steps">${escapeHtml(completed)}/${escapeHtml(total)} steps</span>
      </div>
      <div class="gallery-proof">
        ${galleryProof(session)}
      </div>
      <div class="gallery-duration">
        <span>Duration</span>
        <strong>${escapeHtml(formatDuration(session.duration_seconds))}</strong>
      </div>
      <div class="gallery-hash">
        <span>Storage tx</span>
        <button type="button" data-copy-hash="${escapeHtml(hash)}" ${
          hash ? "" : "disabled"
        }>${escapeHtml(truncateHash(hash))}</button>
      </div>
    </article>
  `;
};

const sortGallerySessions = (sessions) =>
  [...sessions]
    .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime())
    .slice(0, 10);

const renderResult = (result) => {
  document.querySelector("#xrp-amount").textContent = `${formatNumber(result.xrp_amount)} XRP`;
  document.querySelector("#fxrp-amount").textContent = `${formatNumber(result.fxrp_minted)} FXRP`;
  document.querySelector("#decision-count").textContent = result.decisions.length;
  document.querySelector("#receipt-id").textContent =
    result.session?.session_id || "session unavailable";
  document.querySelector("#receipts").innerHTML = result.decisions
    .map((record, index) => receiptCard(result, record, index))
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

const renderGalleryEmpty = () => {
  galleryCount.textContent = "0 saved";
  gallery.innerHTML = `
    <article class="gallery-card gallery-empty">
      <p>No sessions yet — run the judge demo to generate your first iNFT</p>
    </article>
  `;
};

const renderGalleryError = () => {
  galleryCount.textContent = "Unavailable";
  gallery.innerHTML = `
    <article class="gallery-card gallery-error">
      <p>Gallery unavailable</p>
      <button type="button" data-gallery-retry>Retry</button>
    </article>
  `;
};

const loadGallery = async () => {
  galleryRefresh.disabled = true;
  galleryCount.textContent = "Refreshing";
  try {
    const response = await fetch("/gallery", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok || !Array.isArray(payload)) {
      throw new Error("Gallery unavailable.");
    }

    const sessions = sortGallerySessions(payload);
    if (!sessions.length) {
      renderGalleryEmpty();
      return;
    }

    galleryCount.textContent = `${sessions.length} saved`;
    gallery.innerHTML = sessions.map((session) => galleryCard(session)).join("");
  } catch (error) {
    renderGalleryError();
  } finally {
    galleryRefresh.disabled = false;
  }
};

const openDemoStream = () => {
  if (eventSource) {
    eventSource.close();
  }

  eventSource = new EventSource("/stream");
  eventSource.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.step === "done") {
      eventSource.close();
      eventSource = null;
      renderResult(event.result);
      setStepProgress("done");
      stepStatus.textContent = "Complete";
      setState("result");
      refreshTicker();
      loadGallery();
      return;
    }
    if (event.step === "error") {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      errorMessage.textContent = event.error || "The streaming demo failed.";
      setStepProgress("empty");
      setState("error");
      return;
    }
    renderStep(event.step, event.label, event.value, event.status);
  };
  eventSource.onerror = () => {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    errorMessage.textContent = "Live stream disconnected.";
    setStepProgress("empty");
    setState("error");
  };
};

runButton.addEventListener("click", async () => {
  resetLiveSteps();
  setStepProgress("loading");
  setState("loading");

  try {
    const response = await fetch("/api/run", { method: "POST" });
    const payload = await response.json();

    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || "The demo server returned an error.");
    }

    stepStatus.textContent = "Streaming";
    openDemoStream();
  } catch (error) {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    errorMessage.textContent = error instanceof Error ? error.message : String(error);
    setStepProgress("empty");
    setState("error");
  }
});

galleryRefresh.addEventListener("click", () => {
  loadGallery();
});

gallery.addEventListener("click", async (event) => {
  const retryButton = event.target.closest("[data-gallery-retry]");
  if (retryButton) {
    loadGallery();
    return;
  }

  const copyButton = event.target.closest("[data-copy-hash]");
  if (!copyButton || !copyButton.dataset.copyHash) {
    return;
  }

  try {
    await navigator.clipboard.writeText(copyButton.dataset.copyHash);
    copyButton.textContent = "Copied";
    window.setTimeout(() => {
      copyButton.textContent = truncateHash(copyButton.dataset.copyHash);
    }, 1200);
  } catch (error) {
    copyButton.textContent = "Copy failed";
    window.setTimeout(() => {
      copyButton.textContent = truncateHash(copyButton.dataset.copyHash);
    }, 1200);
  }
});

resetLiveSteps();
refreshTicker();
loadGallery();
setInterval(refreshTicker, 30000);
