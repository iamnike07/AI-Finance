const API_BASE = "/api";

const reportSelect = document.getElementById("report-select");
const chatCompanySelect = document.getElementById("chat-company-select");
const kpiGrid = document.getElementById("kpi-grid");
const qualEmpty = document.getElementById("qual-empty");
const qualColumns = document.getElementById("qual-columns");
const companyNameEl = document.getElementById("company-name");
const companyFyEl = document.getElementById("company-fy");
const riskList = document.getElementById("risk-list");
const growthList = document.getElementById("growth-list");
const fileInput = document.getElementById("file-input");
const uploadLabel = document.getElementById("upload-label");
const uploadStatus = document.getElementById("upload-status");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const newChatBtn = document.getElementById("new-chat-btn");
const chartSection = document.getElementById("chart-section");
const chartCompanyLabel = document.getElementById("chart-company-label");

let previousInteractionId = null;
let reportsCache = [];
let kpiChart = null;
let currentChartType = "bar";

/* ========== FORMATTING HELPERS ========== */

function formatCurrency(value) {
  if (value === null || value === undefined) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toLocaleString()}`;
}

function initials(name) {
  if (!name) return "--";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function displayLabel(report) {
  return report.company_name || report.filename.replace(/\.pdf$/i, "");
}

function sourceLabel(report) {
  const name = displayLabel(report);
  return report.fiscal_year ? `${name} (${report.fiscal_year})` : name;
}

/* ========== ANIMATED NUMBER COUNTER ========== */

function animateValue(el, endValue, duration = 1200) {
  const formatted = formatCurrency(endValue);
  if (endValue === null || endValue === undefined) {
    el.textContent = "—";
    return;
  }
  const startTime = performance.now();

  function tick(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = endValue * eased;
    el.textContent = formatCurrency(current);
    if (progress < 1) requestAnimationFrame(tick);
    else el.textContent = formatted;
  }

  el.classList.remove("shimmer");
  requestAnimationFrame(tick);
}

/* ========== MARKDOWN RENDERER ========== */

function renderMarkdown(text) {
  if (!text) return "";
  let html = text
    // Escape HTML
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // Code blocks (```)
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
      `<pre><code>${code.trim()}</code></pre>`)
    // Inline code
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    // Bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Italic
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Unordered lists
    .replace(/^[\-\*]\s+(.+)$/gm, "<li>$1</li>")
    // Ordered lists
    .replace(/^\d+\.\s+(.+)$/gm, "<li>$1</li>");

  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li>.*?<\/li>\s*)+)/g, "<ul>$1</ul>");

  // Paragraphs: split on double newlines
  html = html
    .split(/\n\n+/)
    .map(block => {
      block = block.trim();
      if (!block) return "";
      if (block.startsWith("<pre>") || block.startsWith("<ul>") || block.startsWith("<ol>")) return block;
      return `<p>${block.replace(/\n/g, "<br>")}</p>`;
    })
    .join("");

  return html;
}

/* ========== CHART.JS INTEGRATION ========== */

const CHART_COLORS = [
  "rgba(77, 141, 255, 0.8)",   // blue
  "rgba(62, 207, 142, 0.8)",   // green
  "rgba(224, 168, 60, 0.8)",   // gold
  "rgba(164, 139, 250, 0.8)",  // purple
  "rgba(63, 201, 192, 0.8)",   // teal
  "rgba(240, 100, 95, 0.8)",   // red
];

const CHART_BORDERS = [
  "rgba(77, 141, 255, 1)",
  "rgba(62, 207, 142, 1)",
  "rgba(224, 168, 60, 1)",
  "rgba(164, 139, 250, 1)",
  "rgba(63, 201, 192, 1)",
  "rgba(240, 100, 95, 1)",
];

const KPI_LABELS = ["Revenue", "Net Income", "Op. Income", "Op. Cash Flow", "Total Assets", "Total Liabilities"];
const KPI_KEYS = ["revenue", "net_income", "operating_income", "cash_flow_from_operations", "total_assets", "total_liabilities"];

function buildChartConfig(type, data, label) {
  const values = KPI_KEYS.map(k => {
    const v = data[k];
    return v !== null && v !== undefined ? v / 1e9 : 0;
  });

  const common = {
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "rgba(13, 17, 23, 0.95)",
        titleColor: "#e8ecf1",
        bodyColor: "#8b93a1",
        borderColor: "rgba(77, 141, 255, 0.3)",
        borderWidth: 1,
        cornerRadius: 8,
        padding: 12,
        callbacks: {
          label: ctx => `$${ctx.raw.toFixed(2)}B`,
        },
      },
    },
    animation: {
      duration: 1000,
      easing: "easeOutQuart",
    },
    responsive: true,
    maintainAspectRatio: false,
  };

  if (type === "bar") {
    return {
      type: "bar",
      data: {
        labels: KPI_LABELS,
        datasets: [{
          label: label,
          data: values,
          backgroundColor: CHART_COLORS,
          borderColor: CHART_BORDERS,
          borderWidth: 2,
          borderRadius: 6,
          borderSkipped: false,
        }],
      },
      options: {
        ...common,
        scales: {
          x: {
            grid: { color: "rgba(35, 43, 56, 0.5)", drawBorder: false },
            ticks: { color: "#8b93a1", font: { family: "Inter", size: 11 } },
          },
          y: {
            grid: { color: "rgba(35, 43, 56, 0.5)", drawBorder: false },
            ticks: {
              color: "#8b93a1",
              font: { family: "IBM Plex Mono", size: 11 },
              callback: v => `$${v}B`,
            },
          },
        },
      },
    };
  }

  // Radar
  return {
    type: "radar",
    data: {
      labels: KPI_LABELS,
      datasets: [{
        label: label,
        data: values,
        backgroundColor: "rgba(77, 141, 255, 0.15)",
        borderColor: "rgba(77, 141, 255, 0.8)",
        borderWidth: 2,
        pointBackgroundColor: CHART_BORDERS,
        pointBorderColor: "#0a0e17",
        pointBorderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 8,
      }],
    },
    options: {
      ...common,
      scales: {
        r: {
          grid: { color: "rgba(35, 43, 56, 0.5)" },
          angleLines: { color: "rgba(35, 43, 56, 0.5)" },
          pointLabels: { color: "#8b93a1", font: { family: "Inter", size: 11 } },
          ticks: {
            color: "#565f6e",
            backdropColor: "transparent",
            font: { family: "IBM Plex Mono", size: 9 },
            callback: v => `$${v}B`,
          },
        },
      },
    },
  };
}

let lastKpiData = null;
let lastKpiLabel = "";

function renderChart(kpiData, label) {
  lastKpiData = kpiData;
  lastKpiLabel = label;

  const canvas = document.getElementById("kpi-chart");
  if (!canvas) return;

  chartSection.hidden = false;
  chartCompanyLabel.textContent = label;

  if (kpiChart) kpiChart.destroy();

  const config = buildChartConfig(currentChartType, kpiData, label);
  kpiChart = new Chart(canvas, config);
}

// Chart toggle buttons
document.getElementById("chart-btn-bar").addEventListener("click", () => {
  currentChartType = "bar";
  document.getElementById("chart-btn-bar").classList.add("active");
  document.getElementById("chart-btn-radar").classList.remove("active");
  if (lastKpiData) renderChart(lastKpiData, lastKpiLabel);
});

document.getElementById("chart-btn-radar").addEventListener("click", () => {
  currentChartType = "radar";
  document.getElementById("chart-btn-radar").classList.add("active");
  document.getElementById("chart-btn-bar").classList.remove("active");
  if (lastKpiData) renderChart(lastKpiData, lastKpiLabel);
});

/* ========== REPORTS & KPIs ========== */

async function loadReports() {
  const res = await fetch(`${API_BASE}/reports`);
  const reports = await res.json();
  reportsCache = reports;

  reportSelect.innerHTML = "";
  chatCompanySelect.innerHTML = '<option value="">All Companies</option>';

  if (reports.length === 0) {
    reportSelect.innerHTML = '<option value="">No reports yet</option>';
    reportSelect.disabled = true;
    return;
  }

  reportSelect.disabled = false;
  for (const r of reports) {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = sourceLabel(r);
    reportSelect.appendChild(opt);

    const chatOpt = document.createElement("option");
    chatOpt.value = r.id;
    chatOpt.textContent = displayLabel(r);
    chatCompanySelect.appendChild(chatOpt);
  }
  loadKpis(reports[0].id);
}

async function loadKpis(reportId) {
  if (!reportId) {
    resetKpiCards();
    qualEmpty.hidden = false;
    qualColumns.hidden = true;
    chartSection.hidden = true;
    companyNameEl.textContent = "No report selected";
    companyFyEl.textContent = "Upload a 10-K to get started";
    return;
  }

  // Show shimmer while loading
  kpiGrid.querySelectorAll(".kpi-value").forEach(el => el.classList.add("shimmer"));

  const res = await fetch(`${API_BASE}/reports/${reportId}/kpis`);
  if (!res.ok) {
    resetKpiCards();
    qualEmpty.hidden = false;
    qualColumns.hidden = true;
    chartSection.hidden = true;
    return;
  }
  const kpis = await res.json();
  const report = reportsCache.find((r) => String(r.id) === String(reportId));
  const label = report ? displayLabel(report) : (kpis.company_name || "Report");
  const fy = kpis.fiscal_year || (report && report.fiscal_year) || null;

  companyNameEl.textContent = label;
  companyFyEl.textContent = fy ? `Fiscal Year ${fy}` : "Fiscal year not specified";

  const moneyFields = [
    "revenue", "net_income", "operating_income",
    "cash_flow_from_operations", "total_assets", "total_liabilities",
  ];

  for (const key of moneyFields) {
    const card = kpiGrid.querySelector(`[data-key="${key}"]`);
    if (!card) continue;
    const valueEl = card.querySelector(".kpi-value");
    card.querySelector(".kpi-avatar").textContent = initials(label);
    card.querySelector(".kpi-source-label").textContent = fy ? `${label} (${fy})` : label;
    // Animate the value counter
    animateValue(valueEl, kpis[key]);
  }

  // Render chart
  renderChart(kpis, fy ? `${label} (${fy})` : label);

  qualEmpty.hidden = true;
  qualColumns.hidden = false;

  riskList.innerHTML = "";
  for (const item of kpis.top_risk_factors || []) {
    const li = document.createElement("li");
    li.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg><span></span>';
    li.querySelector("span").textContent = item;
    riskList.appendChild(li);
  }

  growthList.innerHTML = "";
  for (const item of kpis.top_growth_drivers || []) {
    const li = document.createElement("li");
    li.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg><span></span>';
    li.querySelector("span").textContent = item;
    growthList.appendChild(li);
  }
}

function resetKpiCards() {
  kpiGrid.querySelectorAll(".kpi-card").forEach((card) => {
    const valueEl = card.querySelector(".kpi-value");
    valueEl.classList.remove("shimmer");
    valueEl.textContent = "—";
    card.querySelector(".kpi-avatar").textContent = "—";
    card.querySelector(".kpi-source-label").textContent = "No report selected";
  });
}

reportSelect.addEventListener("change", (e) => loadKpis(e.target.value));

/* ========== FILE UPLOAD ========== */

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

/* ========== CHAT ========== */

function appendChatMessage(role, content, isHtml = false) {
  const row = document.createElement("div");
  row.className = `chat-msg-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.innerHTML = role === "user"
    ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
    : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";

  if (isHtml) {
    bubble.innerHTML = content;
  } else {
    bubble.textContent = content;
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatLog.appendChild(row);
  return { row, bubble };
}

function showTypingIndicator() {
  const row = document.createElement("div");
  row.className = "chat-msg-row assistant pending";

  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatLog.appendChild(row);
  chatLog.scrollTop = chatLog.scrollHeight;
  return { row, bubble };
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;

  appendChatMessage("user", question);
  const pending = showTypingIndicator();
  chatLog.scrollTop = chatLog.scrollHeight;

  chatInput.value = "";
  chatInput.disabled = true;

  const reportId = chatCompanySelect.value ? Number(chatCompanySelect.value) : null;

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        previous_interaction_id: previousInteractionId,
        report_id: reportId,
      }),
    });
    const data = await res.json();
    previousInteractionId = data.interaction_id;
    pending.row.classList.remove("pending");
    // Render markdown for assistant response
    pending.bubble.innerHTML = renderMarkdown(data.answer);
  } catch (err) {
    pending.row.classList.remove("pending");
    pending.bubble.textContent = "Something went wrong reaching the API.";
  } finally {
    chatInput.disabled = false;
    chatInput.focus();
    chatLog.scrollTop = chatLog.scrollHeight;
  }
});

newChatBtn.addEventListener("click", () => {
  previousInteractionId = null;
  chatLog.innerHTML = "";
  appendChatMessage("assistant", "New conversation started. Ask me anything about the ingested company reports.");
});

/* ========== INIT ========== */

loadReports();
