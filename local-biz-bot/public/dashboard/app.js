/*
 * app.js - the owner dashboard.
 *
 * Plain JavaScript, no framework. Each "view" is a function that writes HTML
 * into #content. All data comes from the /admin API (app/admin.py).
 */

// ---------------- State ----------------
let adminKey = sessionStorage.getItem("adminKey") || "";
let chatHistory = []; // messages in the "Test your bot" tab

const content = document.getElementById("content");
const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

// ---------------- Helpers ----------------
// Website data is untrusted, so escape it before putting it into HTML.
function esc(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Call the admin API with the admin key. Throws an Error with a readable message.
async function api(path, options = {}) {
  const resp = await fetch("/admin" + path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Admin-Key": adminKey },
  });
  const data = await resp.json().catch(() => ({}));
  if (resp.status === 401) {
    signOut();
    throw new Error("Wrong admin key");
  }
  if (!resp.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong");
  return data;
}

// ---------------- Sign in / out ----------------
async function signIn(key) {
  adminKey = key;
  await api("/sites"); // throws if the key is wrong
  sessionStorage.setItem("adminKey", key);
  document.getElementById("login").hidden = true;
  document.getElementById("app").hidden = false;
  await loadSites();
}

function signOut() {
  adminKey = "";
  sessionStorage.removeItem("adminKey");
  document.getElementById("app").hidden = true;
  document.getElementById("login").hidden = false;
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const error = document.getElementById("login-error");
  error.hidden = true;
  try {
    await signIn(document.getElementById("login-key").value);
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});

document.getElementById("logout-btn").addEventListener("click", signOut);
document.getElementById("add-site-btn").addEventListener("click", showAddSite);

// ---------------- Sidebar: list of websites ----------------
async function loadSites(activeSiteId) {
  const sites = await api("/sites");
  document.getElementById("site-list").innerHTML = sites.length
    ? sites.map((s) => `<a href="#" class="site-link ${s.site_id === activeSiteId ? "active" : ""}"
                          data-site="${esc(s.site_id)}">${esc(s.name)}</a>`).join("")
    : `<p class="muted">No websites yet.</p>`;

  document.querySelectorAll(".site-link").forEach((link) =>
    link.addEventListener("click", (e) => {
      e.preventDefault();
      showSite(link.dataset.site);
    }));

  // First visit: open the first website, or the "add" screen if there are none.
  if (!activeSiteId && !content.innerHTML.trim()) {
    sites.length ? showSite(sites[0].site_id) : showAddSite();
  }
}

// ---------------- View: add a website ----------------
function showAddSite() {
  loadSites(null);
  content.innerHTML = `
    <div class="page-header"><div>
      <h1>Add a website</h1>
      <p class="muted">Paste the business website. We read it and build a chatbot that answers from it.</p>
    </div></div>
    <div class="card">
      <form id="add-form" class="add-form">
        <input name="url" placeholder="https://www.example-plumbing.com" required>
        <button class="btn primary">Build my chatbot</button>
      </form>
      <div id="add-status"></div>
      <ol class="steps">
        <li>We crawl up to 30 pages of the website.</li>
        <li>AI extracts the phone, hours, services, areas and prices.</li>
        <li>You test the bot, then paste one line of code into the website.</li>
      </ol>
    </div>`;

  document.getElementById("add-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = e.target.querySelector("button");
    const status = document.getElementById("add-status");
    button.disabled = true;
    status.innerHTML = `<div class="loading"><div class="spinner"></div>
      <div>Reading the website and extracting business details. This usually takes 20-60 seconds.</div></div>`;
    try {
      const site = await api("/sites", { method: "POST", body: JSON.stringify({ url: e.target.url.value }) });
      showSite(site.site_id);
    } catch (err) {
      status.innerHTML = `<p class="error" style="margin-top:12px">${esc(err.message)}</p>`;
      button.disabled = false;
    }
  });
}

// ---------------- View: one website (header + tabs) ----------------
async function showSite(siteId, tab = "overview") {
  loadSites(siteId);
  content.innerHTML = `<div class="loading"><div class="spinner"></div>Loading...</div>`;
  let site;
  try {
    site = await api("/sites/" + encodeURIComponent(siteId));
  } catch (err) {
    content.innerHTML = `<p class="error">${esc(err.message)}</p>`;
    return;
  }

  const tabs = [["overview", "Overview"], ["test", "Test your bot"], ["install", "Install"],
                ["leads", `Leads <span class="badge">${site.lead_count}</span>`]];

  content.innerHTML = `
    <div class="page-header">
      <div>
        <h1>${esc(site.profile.name || site.site_id)}</h1>
        <a href="${esc(site.origin)}" target="_blank" rel="noopener">${esc(site.origin)}</a>
      </div>
      <button id="refresh-btn" class="btn">↻ Re-read website</button>
    </div>
    <div class="tabs">
      ${tabs.map(([id, label]) => `<button class="tab ${id === tab ? "active" : ""}" data-tab="${id}">${label}</button>`).join("")}
    </div>
    <div id="tab-content"></div>`;

  document.querySelectorAll(".tab").forEach((button) =>
    button.addEventListener("click", () => showSite(siteId, button.dataset.tab)));
  document.getElementById("refresh-btn").addEventListener("click", (e) => refreshSite(site, e.target));

  const tabContent = document.getElementById("tab-content");
  if (tab === "overview") renderOverview(tabContent, site);
  if (tab === "test") renderTestChat(tabContent, site);
  if (tab === "install") renderInstall(tabContent, site);
  if (tab === "leads") renderLeads(tabContent, site);
}

// Crawl the website again to pick up changes.
async function refreshSite(site, button) {
  button.disabled = true;
  button.textContent = "Re-reading... (20-60s)";
  try {
    await api("/sites", { method: "POST", body: JSON.stringify({ url: site.origin }) });
    showSite(site.site_id);
  } catch (err) {
    alert(err.message);
    button.disabled = false;
    button.textContent = "↻ Re-read website";
  }
}

// ---------------- Tab: overview (what the bot knows) ----------------
function renderOverview(el, site) {
  const p = site.profile;
  const missing = `<span class="muted">Not found on website</span>`;
  const hoursByDay = Object.fromEntries(p.hours.map((h) => [h.day.toLowerCase(), h]));

  el.innerHTML = `
    <div class="stats">
      <div class="card"><div class="stat-value">${site.chunk_count}</div><div class="stat-label">Text chunks indexed</div></div>
      <div class="card"><div class="stat-value">${p.services.length}</div><div class="stat-label">Services found</div></div>
      <div class="card"><div class="stat-value">${p.prices.length}</div><div class="stat-label">Prices found</div></div>
      <div class="card"><div class="stat-value">${site.lead_count}</div><div class="stat-label">Call-back leads</div></div>
    </div>

    <div class="grid-2">
      <div class="stack">
        <div class="card">
          <h2>Contact</h2>
          <dl class="facts">
            <dt>Phone</dt><dd>${esc(p.phone) || missing}</dd>
            <dt>Email</dt><dd>${esc(p.email) || missing}</dd>
            <dt>Address</dt><dd>${esc(p.address) || missing}</dd>
            <dt>Time zone</dt><dd>${esc(p.timezone) || missing}</dd>
          </dl>
        </div>
        <div class="card">
          <h2>Opening hours</h2>
          ${p.hours.length ? `<table>${DAYS.map((day) => {
            const h = hoursByDay[day];
            return `<tr><td>${capitalize(day)}</td>
                    <td>${h ? `${esc(h.open)} – ${esc(h.close)}` : `<span class="closed">Closed</span>`}</td></tr>`;
          }).join("")}</table>` : missing}
        </div>
      </div>

      <div class="stack">
        <div class="card">
          <h2>Services</h2>
          ${p.services.length ? `<div class="chips">${p.services.map((s) => `<span class="chip">${esc(s)}</span>`).join("")}</div>` : missing}
        </div>
        <div class="card">
          <h2>Service areas</h2>
          ${p.service_areas.length ? `<div class="chips">${p.service_areas.map((a) => `<span class="chip">${esc(a)}</span>`).join("")}</div>` : missing}
        </div>
        <div class="card">
          <h2>Prices</h2>
          ${p.prices.length ? `<table>
            <tr><th>Item</th><th>Price</th><th>Source</th></tr>
            ${p.prices.map((x) => `<tr><td>${esc(x.item)}</td><td><b>${esc(x.price)}</b></td>
              <td>${x.source_url.startsWith("http") ? `<a href="${esc(x.source_url)}" target="_blank" rel="noopener">page</a>` : ""}</td></tr>`).join("")}
          </table>` : missing}
        </div>
      </div>
    </div>`;
}

// ---------------- Tab: test chat ----------------
function renderTestChat(el, site) {
  chatHistory = [];
  const suggestions = ["What are your hours?", "Are you open right now?", "How much does it cost?", "Do you serve my area?"];

  el.innerHTML = `
    <p class="muted">Ask what a website visitor would ask. These are the same answers the real widget gives.</p>
    <div class="suggestions">${suggestions.map((q) => `<button class="chip">${esc(q)}</button>`).join("")}</div>
    <div class="card chat">
      <div id="chat-messages" class="chat-messages">
        <div class="msg bot">Hi! How can we help you today?</div>
      </div>
      <form id="chat-form" class="chat-form">
        <input name="q" placeholder="Type a question..." required maxlength="500" autocomplete="off">
        <button class="btn primary">Send</button>
      </form>
    </div>`;

  const form = document.getElementById("chat-form");
  const messages = document.getElementById("chat-messages");

  function addMessage(text, who) {
    const div = document.createElement("div");
    div.className = "msg " + who;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  async function ask(question) {
    addMessage(question, "user");
    const reply = addMessage("...", "bot");
    try {
      const data = await api(`/sites/${encodeURIComponent(site.site_id)}/chat`, {
        method: "POST", body: JSON.stringify({ message: question, history: chatHistory }),
      });
      reply.textContent = data.answer;
      if (data.handoff) {
        const note = document.createElement("span");
        note.className = "handoff";
        note.textContent = "↪ Handed off: the visitor now sees the call-back form";
        reply.appendChild(note);
      }
      chatHistory = [...chatHistory, { role: "user", content: question },
                     { role: "assistant", content: data.answer }].slice(-6);
    } catch (err) {
      reply.textContent = "Error: " + err.message;
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const question = form.q.value.trim();
    form.q.value = "";
    if (question) ask(question);
  });
  el.querySelectorAll(".suggestions .chip").forEach((chip) =>
    chip.addEventListener("click", () => ask(chip.textContent)));
}

// ---------------- Tab: install instructions ----------------
function renderInstall(el, site) {
  el.innerHTML = `
    <div class="stack">
      <div class="card">
        <h2>1. Copy this code</h2>
        <pre class="snippet">${esc(site.snippet)}</pre>
        <button id="copy-btn" class="btn primary">Copy code</button>
      </div>
      <div class="card">
        <h2>2. Paste it into the website, just before &lt;/body&gt;</h2>
        <div class="platforms">
          <div><h3>WordPress</h3><p>Install the free "WPCode" plugin → Header &amp; Footer → paste into Footer. With Elementor, you can also use an HTML widget.</p></div>
          <div><h3>Wix</h3><p>Settings → Custom code → Add code → Body - end → All pages.</p></div>
          <div><h3>Squarespace</h3><p>Settings → Advanced → Code injection → Footer.</p></div>
          <div><h3>Shopify</h3><p>Online Store → Themes → Edit code → theme.liquid → paste before &lt;/body&gt;.</p></div>
        </div>
      </div>
      <p class="note">For security, this code only works on <b>${esc(site.origin)}</b>. Copies on other websites are blocked.</p>
    </div>`;

  document.getElementById("copy-btn").addEventListener("click", async (e) => {
    try {
      await navigator.clipboard.writeText(site.snippet);
      e.target.textContent = "Copied ✓";
    } catch {
      e.target.textContent = "Select the code and copy it";
    }
  });
}

// ---------------- Tab: leads ----------------
async function renderLeads(el, site) {
  el.innerHTML = `<div class="loading"><div class="spinner"></div>Loading leads...</div>`;
  const leads = await api(`/sites/${encodeURIComponent(site.site_id)}/leads`);

  if (!leads.length) {
    el.innerHTML = `<div class="card empty"><div class="empty-icon">📭</div>
      <p>No leads yet. When the bot can't answer a question, visitors can ask to be called back. Their requests appear here.</p></div>`;
    return;
  }
  el.innerHTML = `
    <div class="card">
      <table>
        <tr><th>When</th><th>Name</th><th>Phone</th><th>Their question</th></tr>
        ${leads.map((l) => `<tr>
          <td>${esc(new Date(l.created_at).toLocaleString())}</td>
          <td>${esc(l.name)}</td>
          <td><a href="tel:${esc(l.phone)}">${esc(l.phone)}</a></td>
          <td>${esc(l.question) || `<span class="muted">-</span>`}</td></tr>`).join("")}
      </table>
    </div>`;
}

// ---------------- Start ----------------
if (adminKey) {
  signIn(adminKey).catch(signOut);
} else {
  signOut();
}
