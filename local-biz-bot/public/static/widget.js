/*
 * widget.js - the chat bubble a business pastes into its website:
 *
 *   <script src="https://YOUR-BACKEND/static/widget.js" data-site="SITE_ID" defer></script>
 *
 * Optional attributes: data-title, data-greeting, data-lead-text, data-color.
 * The page can also open the chat or ask a question with:
 *   window.dispatchEvent(new CustomEvent("lbb:open"))
 *   window.dispatchEvent(new CustomEvent("lbb:ask", { detail: "Are you open now?" }))
 *
 * Plain JavaScript, no libraries. Everything lives inside a Shadow DOM so the
 * website's CSS cannot change how the chat looks (and our CSS cannot break the site).
 */
(function () {
  // ---------------- Settings from the <script> tag ----------------
  const script = document.currentScript;
  const SITE_ID = script.dataset.site;
  const API = new URL(script.src).origin; // the backend is wherever this file came from
  const TITLE = script.dataset.title || "Ask us anything";
  const GREETING = script.dataset.greeting || "Hi! How can we help you today?";
  const LEAD_TEXT = script.dataset.leadText || "Want the owner to call you back?";
  // Only accept a plain hex color, because it goes into the CSS below.
  const COLOR = /^#[0-9a-f]{3,8}$/i.test(script.dataset.color || "") ? script.dataset.color : "#2563eb";

  let history = [];      // last few messages, sent with each question
  let lastQuestion = ""; // remembered so a lead knows what the visitor asked

  // ---------------- Build the UI inside a Shadow DOM ----------------
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: "open" });

  root.innerHTML = `
    <style>
      * { box-sizing: border-box; font-family: system-ui, sans-serif; font-size: 14px; }
      [hidden] { display: none !important; }
      .bubble { position: fixed; right: 20px; bottom: 20px; width: 56px; height: 56px; border-radius: 50%;
                border: none; background: ${COLOR}; color: #fff; font-size: 24px; cursor: pointer;
                box-shadow: 0 4px 12px rgba(0,0,0,.25); z-index: 99999; }
      .panel { position: fixed; right: 20px; bottom: 86px; width: 340px; max-width: calc(100vw - 40px);
               height: 460px; max-height: calc(100vh - 110px); background: #fff; color: #111;
               border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,.25); display: none;
               flex-direction: column; overflow: hidden; z-index: 99999; }
      .panel.open { display: flex; }
      .header { background: ${COLOR}; color: #fff; padding: 12px 14px; font-weight: 600; }
      .messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
      .msg { padding: 8px 11px; border-radius: 10px; max-width: 85%; line-height: 1.4; white-space: pre-wrap; }
      .user { align-self: flex-end; background: ${COLOR}; color: #fff; }
      .bot { align-self: flex-start; background: #f1f5f9; }
      form { display: flex; gap: 6px; padding: 10px; border-top: 1px solid #e5e7eb; }
      .lead { flex-direction: column; background: #f8fafc; }
      input { flex: 1; padding: 8px; border: 1px solid #cbd5e1; border-radius: 8px; }
      button.send { padding: 8px 12px; border: none; border-radius: 8px; background: ${COLOR}; color: #fff; cursor: pointer; }
    </style>
    <button class="bubble" aria-label="Open chat">💬</button>
    <div class="panel">
      <div class="header"></div>
      <div class="messages"></div>
      <form class="lead" hidden>
        <div class="lead-text"></div>
        <input name="name" placeholder="Your name" required maxlength="100">
        <input name="phone" placeholder="Your phone or email" required minlength="5" maxlength="100">
        <button class="send">Request a call back</button>
      </form>
      <form class="ask">
        <input name="q" placeholder="Type your question..." required maxlength="500" autocomplete="off">
        <button class="send">Send</button>
      </form>
    </div>`;

  const panel = root.querySelector(".panel");
  const messages = root.querySelector(".messages");
  const askForm = root.querySelector(".ask");
  const leadForm = root.querySelector(".lead");
  // Texts from the script tag go in with textContent, so they can't inject HTML either.
  root.querySelector(".header").textContent = TITLE;
  root.querySelector(".lead-text").textContent = LEAD_TEXT;

  // ---------------- Helpers ----------------
  // textContent (not innerHTML) so replies can never inject HTML into the page.
  function addMessage(text, who) {
    const div = document.createElement("div");
    div.className = "msg " + who;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  async function post(path, body) {
    const resp = await fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ site_id: SITE_ID, ...body }),
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    return resp.json();
  }

  // ---------------- Open / close ----------------
  function openPanel() {
    panel.classList.add("open");
    if (!messages.children.length) addMessage(GREETING, "bot");
  }

  root.querySelector(".bubble").addEventListener("click", () => {
    if (panel.classList.contains("open")) panel.classList.remove("open");
    else openPanel();
  });

  // Let the host page open the chat, or open it and ask a question.
  window.addEventListener("lbb:open", openPanel);
  window.addEventListener("lbb:ask", (e) => {
    openPanel();
    askForm.q.value = String(e.detail || "").slice(0, 500);
    askForm.requestSubmit();
  });

  // ---------------- Ask a question ----------------
  askForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = askForm.q.value.trim();
    if (!question) return;
    askForm.q.value = "";
    lastQuestion = question;
    addMessage(question, "user");
    const thinking = addMessage("...", "bot");

    try {
      const reply = await post("/chat", { message: question, history });
      thinking.textContent = reply.answer;
      history = [...history, { role: "user", content: question },
                 { role: "assistant", content: reply.answer }].slice(-6);
      leadForm.hidden = !reply.handoff; // bot couldn't answer -> offer a call back
    } catch (err) {
      thinking.textContent = "Sorry, something went wrong. Please try again.";
    }
  });

  // ---------------- Request a call back ----------------
  leadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await post("/lead", { name: leadForm.name.value, phone: leadForm.phone.value, question: lastQuestion });
      leadForm.hidden = true;
      leadForm.reset();
      addMessage("Thanks! We'll get back to you soon.", "bot");
    } catch (err) {
      addMessage("Sorry, we couldn't save that. Please call us directly.", "bot");
    }
  });
})();
