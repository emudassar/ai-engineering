/* =====================================================================
   site.js - shared header, footer and small interactions for every page.

   Each page has <div id="site-header"></div> and <div id="site-footer"></div>.
   This file fills them, so the navigation lives in ONE place.
   Styling is Tailwind utility classes (see tailwind/input.css).
   ===================================================================== */

// ---------- Edit these to make the site yours ----------
const SITE = {
  name: "Receipt Extractor",
  contactEmail: "hello@example.com", // TODO: put your real email here
  tagline: "Turn receipt PDFs and photos into a clean, ready-to-share expense report in seconds.",
};

const NAV = [
  { href: "/#features", label: "Features" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#use-cases", label: "Use cases" },
  { href: "/#developers", label: "API" },
  { href: "/#faq", label: "FAQ" },
  { href: "/contact/", label: "Contact" },
];

const TICKER = ["No signup", "PDFs + phone photos", "Missing fields flagged, never guessed", "Files never stored"];

// A torn receipt with a ledger-green body and a red "stamp" dot
const LOGO = `
  <svg class="h-9 w-8 shrink-0" viewBox="0 0 34 38" aria-hidden="true">
    <path d="M4 2h26v34l-4.3-3-4.4 3-4.3-3-4.3 3-4.4-3L4 36z" fill="#1f4d3a" stroke="#1b1a17" stroke-width="2" stroke-linejoin="round"/>
    <path d="M10 11h14M10 17h14M10 23h8" stroke="#f4efe4" stroke-width="2.2" stroke-linecap="round"/>
    <circle cx="26" cy="27" r="5" fill="#d9481c" stroke="#1b1a17" stroke-width="2"/>
  </svg>`;

function renderHeader() {
  const slot = document.getElementById("site-header");
  if (!slot) return;
  const path = location.pathname;
  const links = NAV.map(({ href, label }) => {
    const active = !href.includes("#") && path.startsWith(href)
      ? " text-ink underline decoration-stamp decoration-2 underline-offset-[6px]"
      : "";
    return `<li><a href="${href}" class="block rounded px-3 py-2 text-[15px] font-medium text-body hover:bg-paper-2 hover:text-ink max-lg:rounded-none max-lg:border-b max-lg:border-dashed max-lg:border-line max-lg:px-0 max-lg:py-3${active}">${label}</a></li>`;
  }).join("");

  slot.outerHTML = `
    <div class="overflow-hidden bg-ledger font-mono text-[12.5px] tracking-wide text-[#e7efe6]" aria-hidden="true">
      <div class="mx-auto flex max-w-[1200px] justify-center gap-7 px-6 py-2 whitespace-nowrap max-md:justify-start">
        ${TICKER.map((t) => `<span><span class="text-mustard">✳</span> ${t}</span>`).join("")}
      </div>
    </div>
    <header id="top" class="site-header sticky top-0 z-50 border-b-2 border-ink bg-paper transition-shadow">
      <nav class="relative mx-auto flex h-[72px] max-w-[1200px] items-center gap-7 px-6" aria-label="Main">
        <a class="flex items-center gap-2.5 font-serif text-[22px] font-semibold tracking-tight text-ink no-underline" href="/">${LOGO}<span>${SITE.name}</span></a>
        <div id="nav-menu" class="ml-auto flex items-center gap-6 max-lg:hidden max-lg:absolute max-lg:inset-x-0 max-lg:top-full max-lg:flex-col max-lg:items-stretch max-lg:gap-4 max-lg:border-b-2 max-lg:border-ink max-lg:bg-paper max-lg:px-6 max-lg:pt-4 max-lg:pb-6">
          <ul class="flex gap-0.5 max-lg:flex-col">${links}</ul>
          <div class="flex gap-2.5">
            <a class="btn px-4 py-2.5 text-sm max-lg:flex-1" href="/contact/">Book a demo</a>
            <a class="btn btn-ink px-4 py-2.5 text-sm max-lg:flex-1" href="/app/">Try it free</a>
          </div>
        </div>
        <button id="nav-toggle" class="ml-auto hidden h-10 w-11 cursor-pointer flex-col justify-center gap-[5px] rounded-md border-2 border-ink bg-card px-2.5 max-lg:flex" aria-label="Open menu" aria-expanded="false">
          <span class="block h-0.5 bg-ink"></span><span class="block h-0.5 bg-ink"></span><span class="block h-0.5 bg-ink"></span>
        </button>
      </nav>
    </header>`;

  const header = document.querySelector(".site-header");
  const menu = document.getElementById("nav-menu");
  const toggle = document.getElementById("nav-toggle");
  const setOpen = (open) => {
    menu.classList.toggle("max-lg:hidden", !open);
    menu.classList.toggle("max-lg:flex", open);
    toggle.setAttribute("aria-expanded", String(open));
  };
  toggle.addEventListener("click", () => setOpen(toggle.getAttribute("aria-expanded") !== "true"));
  menu.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => setOpen(false)));

  const onScroll = () => header.classList.toggle("shadow-[0_10px_24px_-18px_rgb(27_26_23/.45)]", window.scrollY > 8);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

function renderFooter() {
  const slot = document.getElementById("site-footer");
  if (!slot) return;
  const col = (title, items) => `
    <div>
      <h4 class="mb-4 font-mono text-xs font-medium tracking-[.1em] text-mustard uppercase">${title}</h4>
      <ul class="space-y-2.5">${items.map(([href, label, extra = ""]) =>
        `<li><a class="text-[#d7d1c3] no-underline hover:text-mustard" href="${href}"${extra}>${label}</a></li>`).join("")}</ul>
    </div>`;

  slot.outerHTML = `
    <footer class="overflow-hidden bg-ink pt-20 text-[#a8a191]">
      <div class="mx-auto max-w-[1200px] px-6">
        <div class="grid gap-10 border-b border-[#3a372f] pb-12 md:grid-cols-2 lg:grid-cols-[1.6fr_1fr_1fr_1fr]">
          <div>
            <a class="mb-4 flex items-center gap-2.5 font-serif text-[22px] font-semibold text-paper no-underline" href="/">${LOGO}<span>${SITE.name}</span></a>
            <p class="mb-5 max-w-[340px] text-[15px]">${SITE.tagline}</p>
            <span class="inline-flex items-center gap-2 rounded-[3px] border border-dashed border-[#5a564c] px-3 py-2 font-mono text-[12.5px]">
              <i class="size-2 rounded-full bg-[#6fcf97]"></i> Processed in memory, never stored
            </span>
          </div>
          ${col("Product", [["/app/", "Open the app"], ["/#features", "Features"], ["/#developers", "API"]])}
          ${col("Resources", [["/#how-it-works", "How it works"], ["/#use-cases", "Use cases"], ["/#faq", "FAQ"], ["/docs", "API reference", ' rel="nofollow"']])}
          ${col("Company", [["/contact/", "Contact"], ["/privacy/", "Privacy policy"], ["/terms/", "Terms of service"]])}
        </div>
        <div class="flex flex-wrap justify-between gap-5 py-5 font-mono text-[12.5px]">
          <span>© ${new Date().getFullYear()} ${SITE.name}. All rights reserved.</span>
          <span>Built with FastAPI, Pydantic &amp; Groq</span>
        </div>
        <div class="mt-2.5 -mb-[.12em] font-serif text-[clamp(64px,15vw,210px)] leading-[.8] font-medium tracking-[-.05em] whitespace-nowrap text-[#26241f] select-none" aria-hidden="true">Receipts<em class="text-[#3a2a20]">.</em></div>
      </div>
    </footer>`;
}

// ---------- Fade sections in as they scroll into view ----------
function setupReveal() {
  const items = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("in"));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
        observer.unobserve(entry.target);
      }
    }),
    { threshold: 0.12 },
  );
  items.forEach((el) => observer.observe(el));
}

// ---------- Contact form: opens the visitor's email app, pre-filled ----------
function setupContactForm() {
  document.querySelectorAll("[data-contact-email]").forEach((node) => {
    node.textContent = SITE.contactEmail;
    if (node.tagName === "A") node.href = `mailto:${SITE.contactEmail}`;
  });

  const form = document.getElementById("contact-form");
  if (!form) return;

  // ?topic=demo on the URL pre-selects the topic
  const topic = new URLSearchParams(location.search).get("topic");
  if (topic && form.topic.querySelector(`option[value="${CSS.escape(topic)}"]`)) form.topic.value = topic;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const data = new FormData(form);
    const subject = `[${data.get("topic")}] Message from ${data.get("name")}`;
    const body =
      `${data.get("message")}\n\n---\nName: ${data.get("name")}\nEmail: ${data.get("email")}` +
      (data.get("company") ? `\nCompany: ${data.get("company")}` : "");
    location.href = `mailto:${SITE.contactEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    document.getElementById("form-success").hidden = false;
  });
}

renderHeader();
document.addEventListener("DOMContentLoaded", () => {
  renderFooter();
  setupReveal();
  setupContactForm();
});
