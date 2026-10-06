"use strict";
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
async function api(path, opt = {}) {
  const r = await fetch(path, { ...opt, headers: { "content-type": "application/json", ...(opt.headers || {}) } });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
}
function copyBtn(text) {
  const b = document.createElement("button"); b.className = "copy"; b.type = "button"; b.textContent = "Copy";
  b.onclick = () => navigator.clipboard.writeText(text).then(() => { b.textContent = "Copied"; setTimeout(() => b.textContent = "Copy", 1400); });
  return b;
}
api("/api/health").then(h => { const n = $("net"); if (n) n.textContent = h.network === "main" ? "Mainnet" : "Testnet"; }).catch(() => {});
