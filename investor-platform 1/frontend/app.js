const API_BASE = "http://localhost:8000/api";

const reportSelect = document.getElementById("report-select");
const kpiEmpty = document.getElementById("kpi-empty");
const kpiLedger = document.getElementById("kpi-ledger");
const riskList = document.getElementById("risk-list");
const growthList = document.getElementById("growth-list");
const fileInput = document.getElementById("file-input");
const uploadLabel = document.getElementById("upload-label");
const uploadStatus = document.getElementById("upload-status");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

function formatCurrency(value) {
  if (value === null || value === undefined) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  return `${sign}$${abs.toLocaleString()}`;
}

async function loadReports() {
  const res = await fetch(`${API_BASE}/reports`);
  const reports = await res.json();

  reportSelect.innerHTML = "";
  if (reports.length === 0) {
    reportSelect.innerHTML = '<option value="">No reports yet</option>';
    reportSelect.disabled = true;
    return;
  }

  reportSelect.disabled = false;
  for (const r of reports) {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = r.filename;
    reportSelect.appendChild(opt);
  }
  loadKpis(reports[0].id);
}

async function loadKpis(reportId) {
  if (!reportId) {
    kpiEmpty.hidden = false;
    kpiLedger.hidden = true;
    return;
  }

  const res = await fetch(`${API_BASE}/reports/${reportId}/kpis`);
  if (!res.ok) {
    kpiEmpty.hidden = false;
    kpiLedger.hidden = true;
    return;
  }
  const kpis = await res.json();

  kpiEmpty.hidden = true;
  kpiLedger.hidden = false;

  const moneyFields = [
    "revenue", "net_income", "operating_income",
    "cash_flow_from_operations", "total_assets", "total_liabilities",
  ];
  for (const key of moneyFields) {
    const row = kpiLedger.querySelector(`[data-key="${key}"] .ledger-value`);
    if (row) row.textContent = formatCurrency(kpis[key]);
  }

  riskList.innerHTML = "";
  for (const item of kpis.top_risk_factors || []) {
    const li = document.createElement("li");
    li.textContent = item;
    riskList.appendChild(li);
  }

  growthList.innerHTML = "";
  for (const item of kpis.top_growth_drivers || []) {
    const li = document.createElement("li");
    li.textContent = item;
    growthList.appendChild(li);
  }
}

reportSelect.addEventListener("change", (e) => loadKpis(e.target.value));

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  uploadLabel.textContent = "Processing…";
  uploadStatus.hidden = false;
  uploadStatus.className = "upload-status";
  uploadStatus.textContent = `Ingesting ${file.name} — converting, chunking, embedding, extracting KPIs. This can take a minute.`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/reports`, { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Upload failed");
    }
    const data = await res.json();
    uploadStatus.className = "upload-status success";
    uploadStatus.textContent = `Done — report #${data.report_id} ingested and KPIs extracted.`;
    await loadReports();
    reportSelect.value = data.report_id;
    loadKpis(data.report_id);
  } catch (err) {
    uploadStatus.className = "upload-status error";
    uploadStatus.textContent = `Failed to ingest ${file.name}: ${err.message}`;
  } finally {
    uploadLabel.textContent = "Upload 10-K";
    fileInput.value = "";
  }
});

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;

  const emptyNotice = chatLog.querySelector(".chat-empty");
  if (emptyNotice) emptyNotice.remove();

  const qEl = document.createElement("div");
  qEl.className = "chat-msg question";
  qEl.textContent = question;
  chatLog.appendChild(qEl);

  const pendingEl = document.createElement("div");
  pendingEl.className = "chat-msg pending";
  pendingEl.textContent = "Reading the filing…";
  chatLog.appendChild(pendingEl);
  chatLog.scrollTop = chatLog.scrollHeight;

  chatInput.value = "";
  chatInput.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    pendingEl.className = "chat-msg answer";
    pendingEl.textContent = data.answer;
  } catch (err) {
    pendingEl.className = "chat-msg answer";
    pendingEl.textContent = "Something went wrong reaching the API.";
  } finally {
    chatInput.disabled = false;
    chatInput.focus();
    chatLog.scrollTop = chatLog.scrollHeight;
  }
});

loadReports();
