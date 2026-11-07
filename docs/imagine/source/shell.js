// Shared shell for the "Quiet workbench" concept screens: theme, icon sprite,
// sidebar and concept label. Theme comes from ?theme=light|dark (dark default).
(function () {
  const theme = new URLSearchParams(location.search).get("theme") === "light" ? "light" : "dark";
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.style.colorScheme = theme;
  window.QUIET_THEME = theme;

  const P = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20h14V9.5"/><path d="M10 20v-5h4v5"/>',
    runs: '<circle cx="12" cy="12" r="9"/><path d="m10 8.5 5 3.5-5 3.5z"/>',
    experts: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.3-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18.5 14.8c1.7.8 2.8 2.6 3 5.2"/>',
    workflows: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><path d="M6.5 10v3a3 3 0 0 0 3 3H14"/>',
    approvals: '<path d="M12 3 4.5 6v5.5c0 4.6 3.1 8.2 7.5 9.5 4.4-1.3 7.5-4.9 7.5-9.5V6z"/><path d="m8.8 12 2.2 2.2 4.4-4.4"/>',
    files: '<path d="M3.5 6.5A1.5 1.5 0 0 1 5 5h4.5l2 2.5H19a1.5 1.5 0 0 1 1.5 1.5v9A1.5 1.5 0 0 1 19 19.5H5A1.5 1.5 0 0 1 3.5 18z"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    compose: '<path d="M12 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6"/><path d="M17.6 3.4a2 2 0 0 1 2.9 2.9L12.5 14.3 9 15l.7-3.5z"/>',
    panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
    clip: '<path d="m20 11.5-8.1 8.1a5 5 0 0 1-7.1-7.1l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4L15 7"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    right: '<path d="m9 6 6 6-6 6"/>',
    lock: '<rect x="5" y="11" width="14" height="9.5" rx="2"/><path d="M8 11V7.5a4 4 0 0 1 8 0V11"/>',
    pause: '<path d="M9 5v14M15 5v14"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    download: '<path d="M12 4v11M7 10.5l5 5 5-5M5 20h14"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    expand: '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    checkc: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3M14.5 8.5l2 2"/>',
    eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    alert: '<path d="M10.3 4.2 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4M12 17h.01"/>',
    shield: '<path d="M12 3 4.5 6v5.5c0 4.6 3.1 8.2 7.5 9.5 4.4-1.3 7.5-4.9 7.5-9.5V6z"/>',
    spark: '<path d="M12 3.5 13.7 9a2 2 0 0 0 1.3 1.3l5.5 1.7-5.5 1.7a2 2 0 0 0-1.3 1.3L12 20.5 10.3 15A2 2 0 0 0 9 13.7L3.5 12 9 10.3A2 2 0 0 0 10.3 9z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9.5 9.5h5v5h-5zM9 2.5V6M15 2.5V6M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/>',
    wallet: '<path d="M19 7V5.5A1.5 1.5 0 0 0 17.5 4H5a2 2 0 0 0 0 4h14a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6"/><path d="M16.5 14h.01"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>',
    play: '<path d="m8 5 11 7-11 7z"/>',
    gate: '<path d="M12 3 4.5 6v5.5c0 4.6 3.1 8.2 7.5 9.5 4.4-1.3 7.5-4.9 7.5-9.5V6z"/><path d="M12 9v4M12 16h.01"/>',
    pen: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    list: '<path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01"/>',
    bolt: '<path d="M13 2.5 4.5 13.5H12l-1 8 8.5-11H12z"/>',
    laptop: '<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M2 19.5h20"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16M20 20v-4h-4"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    palette: '<path d="M12 3a9 9 0 1 0 0 18c1.1 0 1.8-.8 1.8-1.8 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.2 0-1 .8-1.8 1.8-1.8h2.1A4.3 4.3 0 0 0 21 10.7C21 6.4 17 3 12 3z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10.5" cy="7" r="1"/><circle cx="15.5" cy="7.5" r="1"/>',
    db: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.5"/><path d="M4.5 5.5v13c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-13M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5"/>',
  };
  window.icon = (name, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name] || ""}</svg>`;

  function expand(root) {
    root.querySelectorAll("[data-i]").forEach((el) => {
      el.outerHTML = icon(el.dataset.i, el.className || "");
    });
  }

  const NAV = [
    ["home", "Home"], ["runs", "Runs"], ["experts", "Experts"],
    ["workflows", "Workflows"], ["approvals", "Approvals"], ["files", "Files"],
  ];
  const RECENT = [
    ["live", "Tallyboard vs Plainview", "run"],
    ["ok", "Q3 vendor shortlist"],
    ["ok", "Summarize /research/interviews"],
    ["wait", "Release notes draft"],
    ["idle", "Weekly competitor brief"],
  ];

  function sidebar(el) {
    const active = el.dataset.active;
    const current = el.dataset.current;
    el.classList.add("sidebar");
    el.innerHTML = `
      <div class="brand"><span class="mark">${icon("bolt")}</span><b>Autobots</b><span class="spacer"></span>${icon("panel")}</div>
      <div class="newrun">${icon("compose")}New run<kbd>⌘ N</kbd></div>
      ${NAV.map(([k, label]) => `<div class="nav ${k === active ? "active" : ""}">${icon(k)}${label}${k === "approvals" ? '<span class="count">1</span>' : ""}</div>`).join("")}
      <div class="side-label">Recent</div>
      ${RECENT.map(([d, t, key]) => `<div class="recent ${key && key === current ? "current" : ""}"><i class="dot ${d}"></i><span>${t}</span></div>`).join("")}
      <div class="side-foot"><div class="avatar">JO</div><div class="acct">Personal<small>${icon("laptop", "sm")}This Mac · local</small></div>${icon("settings")}</div>`;
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("aside[data-active]").forEach(sidebar);
    expand(document);
    if (!document.body.dataset.noTag) {
      const tag = document.createElement("div");
      tag.className = "concept";
      tag.textContent = "Concept · sample data";
      document.body.appendChild(tag);
    }
    document.querySelectorAll("iframe[data-src]").forEach((f) => { f.src = `${f.dataset.src}?theme=${theme}&embed=1`; });
    if (new URLSearchParams(location.search).get("embed")) document.querySelector(".concept")?.remove();
  });
})();
