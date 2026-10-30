/* =====================================================================
   app.js - everything the web page does

   Flow:
     1. User picks / drops files  -> they go into the "queue"
     2. "Extract" sends the files ONE BY ONE to POST /extract
        (so we can show live progress and one slow file does not block the rest)
     3. Each result appears in the table as soon as it arrives
     4. Download buttons send the rows to /export/xlsx or /export/csv
        (the server just builds the file, the AI is NOT called again)
   ===================================================================== */

// ---------- Settings (updated from the server's /settings on page load) ----------
let settings = {
  max_file_size_mb: 4,
  max_files: 20,
  allowed_extensions: [".pdf", ".png", ".jpg", ".jpeg", ".webp"],
};

// ---------- App state ----------
let queue = [];         // File objects waiting to be extracted
let rows = [];          // one object per receipt: the server's row, or a placeholder while waiting
let activeFilter = "all";
let isRunning = false;

// ---------- Shortcuts to page elements ----------
const $ = (id) => document.getElementById(id);
const fileInput = $("file-input");
const dropzone = $("dropzone");

// =====================================================================
// Small helpers
// =====================================================================
function getExtension(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatMoney(value) {
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(isoDate) {
  // "2026-10-20" -> "20 Oct 2026". Built from parts so the time zone can not shift the day.
  const [year, month, day] = isoDate.split("-").map(Number);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${String(day).padStart(2, "0")} ${months[month - 1]} ${year}`;
}

// Create an element with a class and text. Using textContent (never innerHTML
// with data) means a vendor name can never inject HTML into the page.
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function showToast(message, type = "") {
  const toast = el("div", `toast ${type}`, message);
  $("toasts").appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

function saveBlob(blob, filename) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

// =====================================================================
// 1. Server status + settings
// =====================================================================
async function loadServerInfo() {
  const pill = $("server-status");
  const label = pill.querySelector(".label");
  try {
    const [health, serverSettings] = await Promise.all([
      fetch("/health").then((r) => r.json()),
      fetch("/settings").then((r) => r.json()),
    ]);
    settings = serverSettings;
    $("dropzone-hint").textContent =
      `${settings.allowed_extensions.map((e) => e.slice(1).toUpperCase()).join(", ")}` +
      `  ·  up to ${settings.max_file_size_mb} MB each  ·  max ${settings.max_files} files`;
    fileInput.accept = settings.allowed_extensions.join(",");

    if (health.api_key_set) {
      pill.className = "status-pill status-ok";
      label.textContent = "AI connected";
    } else {
      pill.className = "status-pill status-bad";
      label.textContent = "API key missing";
      showToast("GROQ_API_KEY is missing on the server. Add it to .env (local) or Vercel environment variables.", "error");
    }
  } catch {
    pill.className = "status-pill status-bad";
    label.textContent = "Server offline";
  }
}

// =====================================================================
// 2. Adding files to the queue (browse or drag & drop)
// =====================================================================
function addFiles(fileList) {
  const problems = [];

  for (const file of fileList) {
    const extension = getExtension(file.name);
    if (!settings.allowed_extensions.includes(extension)) {
      problems.push(`${file.name}: unsupported type`);
    } else if (file.size === 0) {
      problems.push(`${file.name}: empty file`);
    } else if (file.size > settings.max_file_size_mb * 1024 * 1024) {
      problems.push(`${file.name}: larger than ${settings.max_file_size_mb} MB`);
    } else if (queue.some((f) => f.name === file.name && f.size === file.size)) {
      problems.push(`${file.name}: already added`);
    } else if (queue.length >= settings.max_files) {
      problems.push(`Only ${settings.max_files} files at a time`);
      break;
    } else {
      queue.push(file);
    }
  }

  if (problems.length) showToast(problems.slice(0, 3).join(" · "), "error");
  renderQueue();
}

function renderQueue() {
  const list = $("queue");
  list.replaceChildren();

  queue.forEach((file, index) => {
    const item = el("li");
    const isPdf = getExtension(file.name) === ".pdf";
    item.append(
      el("span", `file-type ${isPdf ? "pdf" : "img"}`, isPdf ? "PDF" : "IMG"),
      el("span", "file-name", file.name),
      el("span", "file-size", formatSize(file.size)),
    );
    if (!isRunning) {
      const remove = el("button", "remove", "×");
      remove.title = "Remove";
      remove.addEventListener("click", () => {
        queue.splice(index, 1);
        renderQueue();
      });
      item.appendChild(remove);
    }
    list.appendChild(item);
  });

  const count = queue.length;
  $("queue-summary").textContent = count
    ? `${count} file${count > 1 ? "s" : ""} ready to extract`
    : "No files selected yet";
  $("extract-btn").textContent = count > 1 ? `Extract ${count} receipts` : "Extract receipt";
  if (!count) $("extract-btn").textContent = "Extract receipts";
  $("extract-btn").disabled = !count || isRunning;
  $("clear-btn").disabled = !count || isRunning;
}

fileInput.addEventListener("change", () => {
  addFiles(fileInput.files);
  fileInput.value = ""; // lets the user pick the same file again later
});

["dragenter", "dragover"].forEach((type) =>
  dropzone.addEventListener(type, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  }),
);
["dragleave", "drop"].forEach((type) =>
  dropzone.addEventListener(type, (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
  }),
);
dropzone.addEventListener("drop", (event) => {
  if (!isRunning) addFiles(event.dataTransfer.files);
});

$("clear-btn").addEventListener("click", () => {
  queue = [];
  renderQueue();
});

// =====================================================================
// 3. Extracting: one request per file, results appear live
// =====================================================================
async function extractOne(file) {
  const formData = new FormData();
  formData.append("files", file);
  try {
    const response = await fetch("/extract", { method: "POST", body: formData });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof body.detail === "string" ? body.detail : "The server could not process this file.";
      return { file: file.name, status: "error", notes: detail };
    }
    return body.rows[0];
  } catch {
    return { file: file.name, status: "error", notes: "Could not reach the server. Is it still running?" };
  }
}

function setProgress(done, total, label) {
  $("progress-label").textContent = label;
  $("progress-count").textContent = `${done} / ${total}`;
  $("progress-bar").style.width = `${total ? (done / total) * 100 : 0}%`;
}

function setRunning(running) {
  isRunning = running;
  dropzone.classList.toggle("disabled", running);
  $("progress").hidden = !running;
  $("restart-btn").disabled = running;
  renderQueue();
  updateDownloadButtons();
}

$("extract-btn").addEventListener("click", async () => {
  if (!queue.length || isRunning) return;

  const files = [...queue];
  // Placeholder rows: "Waiting" until it is that file's turn
  const startIndex = rows.length;
  files.forEach((file) => rows.push({ file: file.name, status: "pending" }));
  $("results").hidden = false;
  setRunning(true);
  renderResults();

  for (let i = 0; i < files.length; i++) {
    rows[startIndex + i] = { file: files[i].name, status: "processing" };
    setProgress(i, files.length, `Reading ${files[i].name}…`);
    renderResults();

    rows[startIndex + i] = await extractOne(files[i]);
    renderResults();
  }

  setProgress(files.length, files.length, "Done");
  queue = [];
  setRunning(false);

  const batch = rows.slice(startIndex);
  const ready = batch.filter((r) => r.status === "ok").length;
  const review = batch.filter((r) => r.status === "needs_review").length;
  const failed = batch.filter((r) => r.status === "error").length;
  showToast(`Done: ${ready} ready, ${review} need review, ${failed} failed`, failed ? "" : "success");
});

// =====================================================================
// 4. Showing results: KPI cards, tabs, table
// =====================================================================
function finishedRows() {
  return rows.filter((r) => r.status !== "pending" && r.status !== "processing");
}

function renderKpis() {
  const done = finishedRows();
  const count = (status) => done.filter((r) => r.status === status).length;

  $("kpi-total").textContent = done.length;
  $("kpi-ok").textContent = count("ok");
  $("kpi-review").textContent = count("needs_review");
  $("kpi-error").textContent = count("error");

  // Total spent in the main currency (we never add different currencies together)
  const totals = {};
  for (const row of done) {
    if (row.status === "error" || row.amount == null) continue;
    const currency = row.currency || "Unknown";
    totals[currency] = (totals[currency] || 0) + row.amount;
  }
  const currencies = Object.keys(totals).sort((a, b) => totals[b] - totals[a]);
  if (currencies.length) {
    $("kpi-spent-label").textContent = `Total spent (${currencies[0]})`;
    $("kpi-spent").textContent = formatMoney(totals[currencies[0]]);
    $("kpi-spent").title = currencies.map((c) => `${c} ${formatMoney(totals[c])}`).join("\n");
  } else {
    $("kpi-spent-label").textContent = "Total spent";
    $("kpi-spent").textContent = "–";
  }

  // Tab counters
  const tabCounts = { all: rows.length, ok: count("ok"), needs_review: count("needs_review"), error: count("error") };
  document.querySelectorAll("[data-count]").forEach((node) => {
    node.textContent = tabCounts[node.dataset.count];
  });
}

// One table cell. Empty values show a "missing" tag (or a dash for optional fields).
function valueCell(value, { className = "", optional = false, format = (v) => v } = {}) {
  const cell = el("td", className);
  if (value === null || value === undefined || value === "") {
    cell.appendChild(optional ? el("span", "dash", "—") : el("span", "missing", "missing"));
  } else {
    cell.textContent = format(value);
  }
  return cell;
}

function statusBadge(status) {
  const labels = {
    ok: "✔ Ready",
    needs_review: "⚠ Review",
    error: "✖ Error",
    pending: "Waiting",
    processing: "Reading",
  };
  const badge = el("span", `badge badge-${status}`, labels[status] || status);
  if (status === "processing") badge.prepend(el("span", "spinner"));
  return badge;
}

function buildRow(row) {
  const tr = el("tr", `row-${row.status}`);
  const fileCell = el("td", "cell-file", row.file);
  fileCell.title = row.file;
  tr.appendChild(fileCell);

  // Still waiting / reading: show shimmering placeholders
  if (row.status === "pending" || row.status === "processing") {
    for (let i = 0; i < 5; i++) {
      const cell = el("td", i >= 3 ? "num" : "");
      cell.appendChild(el("span", "skeleton"));
      tr.appendChild(cell);
    }
    const statusCell = el("td");
    statusCell.appendChild(statusBadge(row.status));
    tr.append(statusCell, el("td"));
    return tr;
  }

  // Failed file: only the reason matters
  if (row.status === "error") {
    for (let i = 0; i < 5; i++) {
      const cell = el("td", i >= 3 ? "num" : "");
      cell.appendChild(el("span", "dash", "—"));
      tr.appendChild(cell);
    }
  } else {
    tr.appendChild(valueCell(row.date, { format: formatDate }));
    tr.appendChild(valueCell(row.vendor, { className: "cell-vendor" }));

    const categoryCell = el("td");
    if (row.category) {
      const slug = row.category.toLowerCase().replace(/\s+/g, "-");
      categoryCell.appendChild(el("span", `chip cat-${slug}`, row.category));
    } else {
      categoryCell.appendChild(el("span", "missing", "missing"));
    }
    tr.appendChild(categoryCell);

    const amountCell = valueCell(row.amount, { className: "num cell-amount", format: formatMoney });
    if (row.amount != null) amountCell.prepend(el("span", "currency", row.currency || "???"));
    tr.appendChild(amountCell);
    tr.appendChild(valueCell(row.tax, { className: "num", optional: true, format: formatMoney }));
  }

  const statusCell = el("td");
  statusCell.appendChild(statusBadge(row.status));
  tr.append(statusCell, el("td", "cell-notes", row.notes || ""));
  return tr;
}

function renderResults() {
  renderKpis();
  const visible = rows.filter((row) => activeFilter === "all" || row.status === activeFilter);
  $("rows").replaceChildren(...visible.map(buildRow));
  $("empty-filter").hidden = visible.length > 0;
  updateDownloadButtons();
}

$("tabs").addEventListener("click", (event) => {
  const tab = event.target.closest(".tab");
  if (!tab) return;
  activeFilter = tab.dataset.filter;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
  renderResults();
});

// =====================================================================
// 5. Downloads (the server builds the file from rows we already have)
// =====================================================================
function updateDownloadButtons() {
  const canDownload = !isRunning && finishedRows().length > 0;
  $("xlsx-btn").disabled = !canDownload;
  $("csv-btn").disabled = !canDownload;
}

async function download(format, filename, button) {
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = "Preparing…";
  try {
    const response = await fetch(`/export/${format}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: finishedRows() }),
    });
    if (!response.ok) throw new Error();
    saveBlob(await response.blob(), filename);
  } catch {
    showToast("Could not create the file. Please try again.", "error");
  } finally {
    button.innerHTML = original;
    updateDownloadButtons();
  }
}

$("xlsx-btn").addEventListener("click", (e) => download("xlsx", "expense-report.xlsx", e.currentTarget));
$("csv-btn").addEventListener("click", (e) => download("csv", "expenses.csv", e.currentTarget));

// =====================================================================
// 6. Start over
// =====================================================================
$("restart-btn").addEventListener("click", () => {
  rows = [];
  queue = [];
  activeFilter = "all";
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.filter === "all"));
  $("results").hidden = true;
  renderQueue();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// ---------- Start ----------
loadServerInfo();
renderQueue();
