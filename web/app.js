const runButton = document.querySelector("#run-demo");
const emptyState = document.querySelector("#empty-state");
const loadingState = document.querySelector("#loading-state");
const errorState = document.querySelector("#error-state");
const resultState = document.querySelector("#result-state");
const errorMessage = document.querySelector("#error-message");
const steps = [...document.querySelectorAll("#steps li")];

const formatNumber = (value, digits = 2) =>
  Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });

const setState = (state) => {
  emptyState.classList.toggle("hidden", state !== "empty");
  loadingState.classList.toggle("hidden", state !== "loading");
  errorState.classList.toggle("hidden", state !== "error");
  resultState.classList.toggle("hidden", state !== "result");
  runButton.disabled = state === "loading";
};

const setStepProgress = (mode) => {
  steps.forEach((step, index) => {
    step.classList.toggle("active", mode === "loading" && index === 0);
    step.classList.toggle("done", mode === "done");
  });
};

const item = (label, title, detail) => `
  <article class="item">
    <span>${label}</span>
    <strong>${title}</strong>
    <p>${detail}</p>
  </article>
`;

const decision = (record, index) => `
  <article class="decision">
    <header>
      <strong>${index + 1}. ${record.agent_ens}</strong>
      <code>${record.action_type}</code>
    </header>
    <p>${record.action_taken}</p>
    <p>${record.result_summary}</p>
  </article>
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
        `$${formatNumber(price.price_usd, 4)}`,
        `Feed ${price.feed_id.slice(0, 18)}... ${price.is_stale ? "fixture fallback" : "live read"}`,
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
  } catch (error) {
    errorMessage.textContent = error instanceof Error ? error.message : String(error);
    setStepProgress("empty");
    setState("error");
  }
});
