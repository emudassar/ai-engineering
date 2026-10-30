/*
 * site.js - small helpers for the marketing site (no libraries):
 *   - mobile menu, active nav link, footer year
 *   - scroll-reveal animations
 *   - loads our own chat widget, so this site is the live demo
 *   - "try asking" chips that send a question into the widget
 *   - the contact form, saved as a lead in the owner dashboard
 */
(function () {
  // Same rule as make_site_id() in app/onboard.py: "www.my-site.com:8000" -> "my-site-com-8000".
  // Computing it here means the same HTML works on localhost and on the live domain.
  const SITE_ID = location.host.replace(/^www\./, "").replace(/[.:]/g, "-");

  // ---------------- Header ----------------
  const header = document.querySelector(".site-header");
  const menuBtn = document.querySelector(".menu-btn");
  if (menuBtn) {
    menuBtn.addEventListener("click", () => {
      const open = header.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", String(open));
    });
  }

  const page = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".main-nav a").forEach((a) => {
    if (a.getAttribute("href").replace("/", "") === page) a.classList.add("active");
  });

  document.querySelectorAll("[data-year]").forEach((el) => (el.textContent = new Date().getFullYear()));

  // ---------------- Scroll reveal ----------------
  const revealed = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealed.forEach((el) => observer.observe(el));
  } else {
    revealed.forEach((el) => el.classList.add("in"));
  }

  // ---------------- Our own chat widget ----------------
  const widget = document.createElement("script");
  widget.src = "/static/widget.js";
  widget.defer = true;
  Object.assign(widget.dataset, {
    site: SITE_ID,
    title: "Local Biz Bot assistant",
    greeting: "Hi! I'm the Local Biz Bot assistant, running on this very site. Ask me how it works, what it can answer, or how to install it.",
    leadText: "Want us to get back to you?",
  });
  document.body.appendChild(widget);

  // Buttons like <button data-ask="How do I install it?"> open the widget and ask that question.
  document.querySelectorAll("[data-ask]").forEach((btn) => {
    btn.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("lbb:ask", { detail: btn.dataset.ask }));
    });
  });
  document.querySelectorAll("[data-open-chat]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("lbb:open"));
    });
  });

  // ---------------- Contact form -> POST /lead ----------------
  const form = document.getElementById("contact-form");
  if (form) {
    const status = document.getElementById("form-status");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const button = form.querySelector("button");
      button.disabled = true;
      button.textContent = "Sending...";
      const data = new FormData(form);
      const question = `[${data.get("topic")}] ${data.get("business") ? data.get("business") + ": " : ""}${data.get("message")}`;

      try {
        const resp = await fetch("/lead", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ site_id: SITE_ID, name: data.get("name"), phone: data.get("contact"),
                                 question: question.slice(0, 500) }),
        });
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        form.reset();
        status.className = "notice ok";
        status.textContent = "Thanks! Your message is in. We'll reply within one business day.";
      } catch (err) {
        status.className = "notice err";
        status.textContent = "Sorry, that didn't go through. Please try again in a minute, or ask the chat assistant.";
      }
      status.hidden = false;
      button.disabled = false;
      button.textContent = "Send message";
    });
  }
})();
