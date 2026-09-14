/**
 * Icy Loader by icekiub - frontend
 * Adds an interactive grid gallery to the "IcyImageLoader" and
 * "IcyMultiRefLoader" nodes so you can visually browse media in the ComfyUI
 * `input` and `output` folders. MultiRef also accepts files dragged straight
 * onto the node.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const LIST_ROUTE = "/icy_loader/list";
const THUMB_ROUTE = "/icy_loader/thumb";

function isVideo(name) {
  return /\.(mp4|webm|mkv|mov|avi|m4v|mpg|mpeg|ts|flv|wmv)$/i.test(name || "");
}

function viewUrl(folder, item) {
  const params = new URLSearchParams();
  params.set("filename", item.name);
  params.set("type", folder);
  if (item.subfolder) params.set("subfolder", item.subfolder);
  return `/view?${params.toString()}`;
}

// Fast cached thumbnail generated server-side (resized + cached to disk).
// Works for videos too (first frame).
function thumbUrl(folder, item) {
  const params = new URLSearchParams();
  params.set("type", folder);
  params.set("filename", item.name);
  if (item.subfolder) params.set("subfolder", item.subfolder);
  return `${THUMB_ROUTE}?${params.toString()}`;
}

function humanSize(bytes) {
  if (bytes == null) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

function formatDate(ts) {
  if (!ts) return "";
  try { return new Date(ts * 1000).toLocaleString(); } catch { return ""; }
}

function toast(summary, type = "info") {
  try {
    app.extensionManager.toast.add({ summary, type });
  } catch {
    console.log(`Icy Loader: ${summary}`);
  }
}

let cssInjected = false;
function injectCss() {
  if (cssInjected) return;
  cssInjected = true;
  const css = `
.icy-overlay{position:fixed;inset:0;z-index:99999;background:rgba(6,10,16,.8);
  display:flex;flex-direction:column;font-family:var(--font-family,sans-serif);color:#e6eaf0}
.icy-window{flex:1;display:flex;flex-direction:column;min-height:0;margin:24px;border-radius:12px;
  background:#12161d;box-shadow:0 20px 60px rgba(0,0,0,.6);overflow:hidden;border:1px solid #27303d}
.icy-topbar{display:flex;align-items:center;gap:10px;padding:10px 14px;background:#181d26;border-bottom:1px solid #27303d}
.icy-brand{font-weight:600;font-size:14px;color:#bfe4ff;white-space:nowrap;display:flex;align-items:baseline;gap:7px}
.icy-brand .icy-credit{font-size:11px;color:#67748a;font-weight:400}
.icy-tabs{display:flex;gap:4px}
.icy-tab{padding:6px 14px;border-radius:8px;cursor:pointer;background:#232b37;border:none;color:#cfd6e0;font-size:13px}
.icy-tab.active{background:#7cc9ff;color:#0d1420}
.icy-spacer{flex:1}
.icy-count{font-size:12px;color:#8a96a8}
.icy-btn{padding:6px 12px;border-radius:8px;cursor:pointer;background:#262e3a;border:none;color:#dde3ec;font-size:13px}
.icy-btn:hover{background:#303a49}
.icy-btn.primary{background:#58b8f0;color:#0d1420}
.icy-btn.primary:hover{background:#7cc9ff}
.icy-search{flex:1;background:#0a0d12;border:1px solid #27303d;color:#eee;border-radius:8px;padding:7px 10px;font-size:13px;min-width:120px}
.icy-toolbar{display:flex;align-items:center;gap:8px;padding:10px 14px;background:#151a22;border-bottom:1px solid #27303d}
.icy-sort{background:#0a0d12;border:1px solid #27303d;color:#ddd;border-radius:8px;padding:6px;font-size:12px}
.icy-body{flex:1;overflow:auto;padding:14px;position:relative}
.icy-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.icy-card{position:relative;border:2px solid transparent;border-radius:10px;overflow:hidden;cursor:pointer;
  background:#0d1117;aspect-ratio:1;display:flex;align-items:center;justify-content:center}
.icy-card:hover{border-color:#3b4a5c}
.icy-card.selected{border-color:#7cc9ff;box-shadow:0 0 0 2px rgba(124,201,255,.25)}
.icy-card img{width:100%;height:100%;object-fit:cover;display:block;background:#1a222c}
.icy-card .icy-ph{color:#55606e;font-size:11px}
.icy-card .icy-meta{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(transparent,rgba(0,0,0,.85));
  padding:14px 6px 5px;font-size:10px;line-height:1.3;color:#eee;word-break:break-all}
.icy-card .icy-check{position:absolute;top:5px;right:5px;width:20px;height:20px;border-radius:50%;
  background:#7cc9ff;color:#0d1420;display:none;align-items:center;justify-content:center;font-size:12px}
.icy-card.selected .icy-check{display:flex}
.icy-card .icy-badge{position:absolute;top:5px;left:5px;padding:1px 6px;border-radius:6px;background:rgba(10,16,24,.8);
  color:#9fd4ff;font-size:10px;display:none}
.icy-card.has-video .icy-badge{display:block}
.icy-zoom{position:absolute;top:5px;left:5px;width:22px;height:22px;border-radius:6px;background:rgba(0,0,0,.55);
  color:#fff;display:none;align-items:center;justify-content:center;font-size:12px;cursor:pointer;z-index:2}
.icy-card.has-video .icy-zoom{top:26px}
.icy-card:hover .icy-zoom{display:flex}
.icy-zoom:hover{background:rgba(0,0,0,.8)}
.icy-empty{color:#66707e;text-align:center;padding:60px 0;font-size:14px}
.icy-loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#8894a6;background:rgba(10,13,18,.6)}
.icy-spinner{width:34px;height:34px;border:3px solid #2a3442;border-top-color:#7cc9ff;border-radius:50%;animation:icyspin 1s linear infinite}
@keyframes icyspin{to{transform:rotate(360deg)}}
.icy-footer{display:flex;align-items:center;gap:10px;padding:10px 14px;background:#181d26;border-top:1px solid #27303d}
.icy-selinfo{flex:1;font-size:12px;color:#9aa5b5;word-break:break-all}
.icy-preview-img{max-width:90vw;max-height:80vh;border-radius:8px;display:block}
.icy-preview-video{max-width:90vw;max-height:80vh;border-radius:8px;display:block}
.icy-sentinel{grid-column:1/-1;height:28px;display:flex;align-items:center;justify-content:center}
.icy-sentinel .icy-spinner{width:24px;height:24px;border-width:2px}
.icy-reflist{display:flex;flex-direction:column;gap:6px;width:100%;box-sizing:border-box;color:#cfd6e0;font-size:12px}
.icy-reflist-top{display:flex;gap:6px;align-items:stretch}
.icy-reflist-drop{flex:1;border:2px dashed #3b4a5c;border-radius:8px;padding:10px 8px;text-align:center;color:#7f8ea3;cursor:pointer;background:rgba(18,22,29,.6)}
.icy-reflist-drop:hover{border-color:#7cc9ff;color:#9fd4ff}
.icy-reflist.icy-dragover .icy-reflist-drop{border-color:#7cc9ff;background:rgba(124,201,255,.08);color:#bfe4ff}
.icy-reflist-clear{flex:none;border:1px solid #4a3540;background:#2a1e24;color:#e0909e;border-radius:8px;padding:0 12px;cursor:pointer;font-size:12px}
.icy-reflist-clear:hover{background:#3a2830}
.icy-reflist-items{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:6px;max-height:264px;overflow-y:auto}
.icy-ref-tile{position:relative;border-radius:10px;overflow:hidden;border:2px solid #27303d;background:#0d1117}
.icy-ref-tile:hover{border-color:#4a5a6e}
.icy-ref-tile-thumb{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#0d1117}
.icy-ref-tile-num{position:absolute;top:4px;left:4px;min-width:18px;height:18px;border-radius:6px;background:rgba(10,16,24,.85);color:#9fd4ff;font-size:11px;display:flex;align-items:center;justify-content:center;padding:0 4px}
.icy-ref-tile-x{position:absolute;top:4px;right:4px;width:20px;height:20px;border:none;border-radius:6px;background:rgba(90,20,30,.9);color:#ffb3c0;cursor:pointer;font-size:11px;display:none;align-items:center;justify-content:center;padding:0}
.icy-ref-tile:hover .icy-ref-tile-x{display:flex}
.icy-ref-tile-x:hover{background:rgba(140,30,45,.95)}
.icy-ref-nav{position:absolute;top:50%;transform:translateY(-50%);width:22px;height:22px;border:none;border-radius:6px;background:rgba(10,16,24,.85);color:#dde3ec;font-size:10px;cursor:pointer;padding:0;display:none;align-items:center;justify-content:center}
.icy-ref-nav:hover{background:rgba(38,46,58,.95)}
.icy-ref-tile:hover .icy-ref-nav:not(:disabled){display:flex}
.icy-ref-tile-nav-prev{left:4px}
.icy-ref-tile-nav-next{right:4px}
.icy-ref-tile-kind{position:absolute;bottom:4px;right:4px;padding:1px 5px;border-radius:5px;background:rgba(10,16,24,.85);color:#9fd4ff;font-size:9px}
.icy-ref-empty{color:#66707e;font-size:11px;text-align:center;padding:6px 0}
`;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);
}

class GalleryViewer {
  constructor(onSelect, currentFolder, multi = false, initialSel = null) {
    this.onSelect = onSelect;
    this.multi = multi;
    this.activeFolder = currentFolder || "input";
    this.data = {};
    this.search = "";
    this.sortBy = "mtime";
    this.selected = null; // {folder, item} (single mode)
    this.multiSel = new Set(initialSel || []); // item paths (multi mode, active folder only)
    this.overlay = null;
    this._lazy = null;
    this.pageSize = 80;
    this.shown = this.pageSize;
    // infinite-scroll pagination state
    this._gridItems = null;
    this._gridTotal = 0;
    this._gridEl = null;
    this._sentinel = null;
    this._scrollHandler = null;
  }

  noun() {
    return this.multi ? "media" : "image";
  }

  async open() {
    injectCss();
    this.overlay = document.createElement("div");
    this.overlay.className = "icy-overlay";
    document.body.appendChild(this.overlay);
    this.overlay.addEventListener("click", (e) => {
      if (e.target === this.overlay) this.close();
    });
    this._keyHandler = (e) => {
      if (e.key === "Escape") {
        if (this._lightbox) this.closeLightbox();
        else this.close();
      }
    };
    document.addEventListener("keydown", this._keyHandler);
    this.render();
    await this.refresh();
  }

  close() {
    if (this._io) {
      try { this._io.disconnect(); } catch {}
      this._io = null;
    }
    this._sentinel = null;
    if (this._scrollHandler && this._body) {
      try { this._body.removeEventListener("scroll", this._scrollHandler); } catch {}
    }
    if (this._keyHandler) document.removeEventListener("keydown", this._keyHandler);
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
    }
    if (this._lazy) {
      window.removeEventListener("scroll", this._lazy, true);
      this._lazy = null;
    }
  }

  async refresh() {
    const body = this.overlay?.querySelector(".icy-body");
    if (body) body.innerHTML = `<div class="icy-loading"><div class="icy-spinner"></div></div>`;
    try {
      const resp = await api.fetchApi(`${LIST_ROUTE}?folder=${this.activeFolder}${this.multi ? "&media=1" : ""}`);
      this.data = await resp.json();
    } catch (err) {
      if (body) body.innerHTML = `<div class="icy-empty">Failed to load: ${err}</div>`;
      return;
    }
    this.renderGrid();
  }

  getItems() {
    let items = this.data[this.activeFolder] || [];
    const q = this.search.trim().toLowerCase();
    if (q) items = items.filter((i) => i.name.toLowerCase().includes(q));
    items = items.slice();
    if (this.sortBy === "name") items.sort((a, b) => a.name.localeCompare(b.name));
    else if (this.sortBy === "size") items.sort((a, b) => (b.size || 0) - (a.size || 0));
    else items.sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
    return items;
  }

  render() {
    const w = document.createElement("div");
    w.className = "icy-window";

    // topbar
    const top = document.createElement("div");
    top.className = "icy-topbar";
    const brand = document.createElement("div");
    brand.className = "icy-brand";
    brand.appendChild(document.createTextNode("❄ Icy Gallery"));
    const credit = document.createElement("span");
    credit.className = "icy-credit";
    credit.textContent = "by icekiub";
    brand.appendChild(credit);
    top.appendChild(brand);

    const tabs = document.createElement("div");
    tabs.className = "icy-tabs";
    for (const f of ["input", "output"]) {
      const t = document.createElement("button");
      t.className = "icy-tab" + (f === this.activeFolder ? " active" : "");
      t.textContent = f === "input" ? "📁 Input" : "💾 Output";
      t.onclick = () => {
        if (this.activeFolder === f) return;
        this.activeFolder = f;
        this.selected = null;
        this.multiSel.clear();
        this.shown = this.pageSize;
        this._updateFooter();
        this.render();
        this.refresh();
      };
      tabs.appendChild(t);
    }
    top.appendChild(tabs);

    const search = document.createElement("input");
    search.className = "icy-search";
    search.type = "text";
    search.placeholder = "Search filename…";
    search.value = this.search;
    search.oninput = () => {
      this.search = search.value;
      this.shown = this.pageSize;
      this.renderGrid();
    };
    top.appendChild(search);

    const refresh = document.createElement("button");
    refresh.className = "icy-btn";
    refresh.textContent = "↻ Refresh";
    refresh.onclick = () => { this.shown = this.pageSize; this.refresh(); };
    top.appendChild(refresh);

    const closeBtn = document.createElement("button");
    closeBtn.className = "icy-btn";
    closeBtn.textContent = "✕ Close";
    closeBtn.onclick = () => this.close();
    top.appendChild(closeBtn);
    w.appendChild(top);

    // toolbar (sort + count)
    const toolbar = document.createElement("div");
    toolbar.className = "icy-toolbar";
    const sortLabel = document.createElement("span");
    sortLabel.style.fontSize = "12px";
    sortLabel.style.color = "#8a96a8";
    sortLabel.textContent = "Sort:";
    const sortSel = document.createElement("select");
    sortSel.className = "icy-sort";
    for (const [k, label] of [["mtime", "Newest"], ["name", "Name"], ["size", "Size"]]) {
      const o = document.createElement("option");
      o.value = k;
      o.textContent = label;
      if (k === this.sortBy) o.selected = true;
      sortSel.appendChild(o);
    }
    sortSel.onchange = () => {
      this.sortBy = sortSel.value;
      this.shown = this.pageSize;
      this.renderGrid();
    };
    this._countEl = document.createElement("span");
    this._countEl.className = "icy-count";
    toolbar.appendChild(sortLabel);
    toolbar.appendChild(sortSel);
    const spacer = document.createElement("div");
    spacer.className = "icy-spacer";
    toolbar.appendChild(spacer);
    toolbar.appendChild(this._countEl);
    w.appendChild(toolbar);

    // body
    const body = document.createElement("div");
    body.className = "icy-body";
    body.innerHTML = `<div class="icy-loading"><div class="icy-spinner"></div></div>`;
    w.appendChild(body);
    this._body = body;

    // footer
    const footer = document.createElement("div");
    footer.className = "icy-footer";
    const info = document.createElement("div");
    info.className = "icy-selinfo";
    info.textContent = this.multi
      ? "Click media to toggle selection · already-loaded references stay selected"
      : "No image selected";
    this._info = info;
    const loadBtn = document.createElement("button");
    loadBtn.className = "icy-btn primary";
    loadBtn.textContent = this.multi ? "Add selected" : "Load selected";
    loadBtn.onclick = () => this.confirm();
    loadBtn.disabled = true;
    this._loadBtn = loadBtn;
    footer.appendChild(info);
    footer.appendChild(loadBtn);
    w.appendChild(footer);

    // replace any existing window (e.g. on tab switch) instead of stacking
    if (this._io) { try { this._io.disconnect(); } catch {} this._io = null; }
    this._sentinel = null;
    this.overlay.innerHTML = "";
    this.overlay.appendChild(w);
    // drive infinite loading from a scroll listener (reliable in Firefox + Chromium)
    if (!this._scrollHandler) this._scrollHandler = () => this._onScroll();
    body.addEventListener("scroll", this._scrollHandler, { passive: true });
  }

  renderGrid() {
    if (!this._body) return;
    const items = this.getItems();
    const total = items.length;
    this._gridItems = items;
    this._gridTotal = total;
    this._gridEl = null;
    this._sentinel = null;
    this._updateCount(total);

    if (total === 0) {
      this._body.innerHTML = `<div class="icy-empty">No ${this.noun()} found${this.search ? " for your search" : " in this folder"}.<br>Upload files to the <code>${this.activeFolder}</code> folder${this.multi ? " or drop them onto the node" : " or refresh"}.</div>`;
      return;
    }

    const visible = items.slice(0, this.shown);
    const grid = document.createElement("div");
    grid.className = "icy-grid";
    this._body.innerHTML = "";
    this._body.appendChild(grid);
    this._gridEl = grid;

    for (const item of visible) {
      this._appendCard(grid, item);
    }

    this._updateFooter();

    if (this.shown < total) {
      this._setupSentinel();
      // a tall window may show the whole first page without scrolling
      requestAnimationFrame(() => this._onScroll());
    }
  }

  _updateCount(total) {
    if (!this._countEl) return;
    const shown = Math.min(this.shown, total);
    this._countEl.textContent = shown < total
      ? `${shown} / ${total} ${this.noun()}${total === 1 ? "" : "s"}`
      : `${total} ${this.noun()}${total === 1 ? "" : "s"}`;
  }

  _setupSentinel() {
    if (!this._gridEl) return;
    const sentinel = document.createElement("div");
    sentinel.className = "icy-sentinel";
    const spin = document.createElement("div");
    spin.className = "icy-spinner";
    sentinel.appendChild(spin);
    this._gridEl.appendChild(sentinel);
    this._sentinel = sentinel;
  }

  _onScroll() {
    if (!this._body || !this._sentinel) return;
    if (this.shown >= this._gridTotal) return;
    const body = this._body;
    const remaining = body.scrollHeight - body.scrollTop - body.clientHeight;
    if (remaining < 600) this._loadMore();
  }

  _loadMore() {
    if (this.shown >= this._gridTotal || !this._gridItems || !this._gridEl) return;
    const prev = this.shown;
    this.shown += this.pageSize;
    const next = this._gridItems.slice(prev, this.shown);
    const sentinel = this._sentinel;
    for (const item of next) {
      const card = this._buildCard(item);
      this._gridEl.insertBefore(card, sentinel);
      this._observeCard(card);
    }
    const total = this._gridTotal;
    this._updateCount(total);
    if (this.shown >= total) {
      if (sentinel) sentinel.remove();
      this._sentinel = null;
    }
    // inserting nodes grows scrollHeight; re-check in case another page fits
    if (this.shown < total) requestAnimationFrame(() => this._onScroll());
  }

  _appendCard(grid, item) {
    const card = this._buildCard(item);
    grid.appendChild(card);
    this._observeCard(card);
  }

  _buildCard(item) {
    const card = document.createElement("div");
    card.className = "icy-card" + (isVideo(item.name) ? " has-video" : "");
    card.dataset.path = item.path;
    card.title = `${item.name}\n${humanSize(item.size)}\n${formatDate(item.mtime)}`;

    const check = document.createElement("div");
    check.className = "icy-check";
    check.textContent = "✓";
    card.appendChild(check);

    const badge = document.createElement("div");
    badge.className = "icy-badge";
    badge.textContent = "video";
    card.appendChild(badge);

    // secondary action: open full-size preview in a lightbox
    const zoom = document.createElement("div");
    zoom.className = "icy-zoom";
    zoom.textContent = "🔍";
    zoom.title = "Preview (click image to select)";
    zoom.onclick = (e) => {
      e.stopPropagation();
      this.openLightbox(card._fullUrl, isVideo(item.name));
    };
    card.appendChild(zoom);

    const ph = document.createElement("div");
    ph.className = "icy-ph";
    ph.textContent = "…";
    card.appendChild(ph);

    const meta = document.createElement("div");
    meta.className = "icy-meta";
    meta.textContent = `${item.name} · ${humanSize(item.size)}`;
    card.appendChild(meta);

    const isSelected = this.multi
      ? this.multiSel.has(item.path)
      : this.selected && this.selected.folder === this.activeFolder && this.selected.item.path === item.path;
    if (isSelected) card.classList.add("selected");

    card.onclick = () => {
      if (this.multi) {
        if (this.multiSel.has(item.path)) {
          this.multiSel.delete(item.path);
          card.classList.remove("selected");
        } else {
          this.multiSel.add(item.path);
          card.classList.add("selected");
        }
      } else {
        this.selected = { folder: this.activeFolder, item };
        const g = card.parentElement || this._body?.querySelector(".icy-grid");
        [...(g ? g.querySelectorAll(".icy-card") : [])].forEach((c) => c.classList.remove("selected"));
        card.classList.add("selected");
        if (this._info) this._info.textContent = `${item.name}  ·  ${humanSize(item.size)}  ·  ${formatDate(item.mtime)}`;
      }
      this._updateFooter();
    };
    card.ondblclick = () => {
      if (this.multi) this.multiSel = new Set([item.path]);
      else this.selected = { folder: this.activeFolder, item };
      this.confirm();
    };
    // lazy-load thumbnail (fast cached server thumbnail)
    card._imgUrl = thumbUrl(this.activeFolder, item);
    card._fullUrl = viewUrl(this.activeFolder, item);
    return card;
  }

  _updateFooter() {
    if (this.multi) {
      // initial selection may contain paths from another folder; count what is visible here
      const n = this.getItems().filter((i) => this.multiSel.has(i.path)).length;
      if (this._info) this._info.textContent = n ? `${n} media selected` : "Click media to toggle selection · loaded references stay selected";
      if (this._loadBtn) {
        this._loadBtn.disabled = n === 0;
        this._loadBtn.textContent = n ? `Load ${n} selected` : "Add selected";
      }
    } else if (this._loadBtn) {
      this._loadBtn.disabled = !this.selected;
    }
  }

  _observeCard(card) {
    if (!this._io) {
      this._io = new IntersectionObserver(
        (entries) => {
          for (const ent of entries) {
            if (!ent.isIntersecting) continue;
            const c = ent.target;
            if (c._loaded) continue;
            c._loaded = true;
            const img = document.createElement("img");
            img.loading = "lazy";
            img.src = c._imgUrl;
            img.onerror = () => {
              if (c._fallback) {
                const ph = c.querySelector(".icy-ph");
                if (ph) ph.textContent = "⚠";
                return;
              }
              c._fallback = true;
              img.src = c._fullUrl;
            };
            img.onload = () => {
              const ph = c.querySelector(".icy-ph");
              if (ph) ph.remove();
            };
            c.insertBefore(img, c.querySelector(".icy-meta"));
            this._io.unobserve(c);
          }
        },
        { root: this._body, rootMargin: "300px" }
      );
    }
    this._io.observe(card);
  }

  openLightbox(url, video = false) {
    const lb = document.createElement("div");
    lb.style.cssText =
      "position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.9);display:flex;align-items:center;justify-content:center;cursor:zoom-out";
    let el;
    if (video) {
      el = document.createElement("video");
      el.className = "icy-preview-video";
      el.controls = true;
      el.autoplay = true;
      el.muted = true;
      el.loop = true;
    } else {
      el = document.createElement("img");
      el.className = "icy-preview-img";
    }
    el.src = url;
    lb.appendChild(el);
    lb.onclick = () => this.closeLightbox();
    document.body.appendChild(lb);
    this._lightbox = lb;
  }

  closeLightbox() {
    if (this._lightbox) {
      this._lightbox.remove();
      this._lightbox = null;
    }
  }

  _finish() {
    document.removeEventListener("keydown", this._keyHandler);
    this.closeLightbox();
    this.close();
  }

  confirm() {
    if (this.multi) {
      if (!this.multiSel.size) return;
      const items = this.getItems().filter((i) => this.multiSel.has(i.path));
      if (!items.length) return;
      this._finish();
      if (this.onSelect) this.onSelect(this.activeFolder, items);
    } else {
      if (!this.selected) return;
      const { folder, item } = this.selected;
      this._finish();
      if (this.onSelect) this.onSelect(folder, item);
    }
  }
}

function findWidget(node, name) {
  return (node.widgets || []).find((w) => (w.name || w.options?.name) === name);
}

function setNodePreview(node, url) {
  const img = new Image();
  img.onload = () => {
    // LiteGraph renders node.imgs natively (works in both Nodes 2.0 and
    // legacy canvas), so we just assign it and resize the node to fit.
    node.imgs = [img];
    try {
      if (typeof node.setSizeForImage === "function") {
        node.setSizeForImage();
      } else if (img.naturalWidth) {
        const w = node.size[0] || 256;
        const h = Math.min(512, Math.round((w * img.naturalHeight) / Math.max(1, img.naturalWidth)));
        const base = node.computeSize?.(w)?.[1] ?? node.size[1];
        node.size[1] = Math.max(node.size[1], base + h);
      }
    } catch {}
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
  };
  img.src = url;
}

function setFolderWidget(node, folder) {
  const folderW = findWidget(node, "folder");
  if (folderW) {
    folderW.value = folder;
    if (typeof folderW.callback === "function") { try { folderW.callback(folder); } catch {} }
  }
}

function applySelection(node, folder, item) {
  setFolderWidget(node, folder);

  const imageW = findWidget(node, "image");
  if (imageW) {
    // make the combo accept the chosen value (esp. for output-folder picks)
    imageW.options = imageW.options || {};
    if (Array.isArray(imageW.options.values) && !imageW.options.values.includes(item.path)) {
      imageW.options.values.unshift(item.path);
    }
    imageW.value = item.path;
    if (typeof imageW.callback === "function") { try { imageW.callback(item.path); } catch {} }
  }

  // render the selected image into the node so the user sees it loaded
  setNodePreview(node, viewUrl(folder, item));
}

function applyMultiSelection(node, folder, items) {
  const mediaW = findWidget(node, "media");
  const folderW = findWidget(node, "folder");
  const currentFolder = folderW ? folderW.value : folder;
  // entries resolve against one folder root: switching folders replaces,
  // picking from the same folder keeps what is already loaded and appends
  const lines = folder === currentFolder
    ? (mediaW?.value || "").split("\n").map((s) => s.trim()).filter(Boolean)
    : [];

  setFolderWidget(node, folder);
  if (mediaW) {
    for (const it of items) {
      if (!lines.includes(it.path)) lines.push(it.path);
    }
    mediaW.value = lines.join("\n");
    if (typeof mediaW.callback === "function") { try { mediaW.callback(mediaW.value); } catch {} }
  }
}

// ---------------- drop-in media loading for MultiRef ----------------

const MEDIA_RE = /\.(png|jpe?g|webp|gif|bmp|tiff?|avif|mp4|webm|mkv|mov|avi|m4v|mpg|mpeg|ts|flv|wmv)$/i;

async function uploadMedia(file) {
  const send = (name) => {
    const fd = new FormData();
    fd.append("image", file, name);
    return api.fetchApi("/upload/image", { method: "POST", body: fd }).then(async (r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
  };
  try {
    return await send(file.name);
  } catch {
    // usually a name clash in the input folder -> retry once with a unique name
    const dot = file.name.lastIndexOf(".");
    const unique = dot < 0
      ? `${file.name}_${Date.now().toString(36)}`
      : `${file.name.slice(0, dot)}_${Date.now().toString(36)}${file.name.slice(dot)}`;
    return await send(unique);
  }
}

async function handleFiles(node, files) {
  const list = [...files].filter((f) => MEDIA_RE.test(f.name) || f.type.startsWith("image/") || f.type.startsWith("video/"));
  if (!list.length) {
    toast("No image or video files in the drop", "error");
    return;
  }
  toast(`Uploading ${list.length} file${list.length > 1 ? "s" : ""}…`);
  const entries = [];
  for (const f of list) {
    try {
      const info = await uploadMedia(f);
      entries.push(info.subfolder ? `${info.subfolder}/${info.name}` : info.name);
    } catch (err) {
      toast(`Upload failed: ${f.name}`, "error");
      console.warn("Icy Loader upload failed:", err);
    }
  }
  if (entries.length) addMediaEntries(node, entries);
}

function addMediaEntries(node, entries) {
  // uploads always land in the input folder
  setFolderWidget(node, "input");

  const mediaW = findWidget(node, "media");
  if (mediaW) {
    const lines = (mediaW.value || "").split("\n").map((s) => s.trim()).filter(Boolean);
    for (const e of entries) if (!lines.includes(e)) lines.push(e);
    mediaW.value = lines.join("\n");
    if (typeof mediaW.callback === "function") { try { mediaW.callback(mediaW.value); } catch {} }
  }
}

// ---------------- ordered media list (HTML/JS DOM widget) ----------------

function mediaEntriesOf(node) {
  return (findWidget(node, "media")?.value || "").split("\n").map((s) => s.trim()).filter(Boolean);
}

function setMediaEntries(node, entries) {
  const mediaW = findWidget(node, "media");
  if (mediaW) mediaW.value = entries.join("\n");
  renderMediaList(node);
  node.setDirtyCanvas?.(true, true);
  app.graph?.setDirtyCanvas?.(true, true);
}

function renderMediaList(node) {
  const root = node._icyRefListEl;
  if (!root) return;
  const gridEl = root._list;
  const folder = findWidget(node, "folder")?.value || "input";
  const entries = mediaEntriesOf(node);

  gridEl.innerHTML = "";
  root._clearBtn.disabled = entries.length === 0;
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "icy-ref-empty";
    empty.textContent = "no references yet";
    gridEl.appendChild(empty);
    return;
  }

  entries.forEach((path, idx) => {
    const parts = path.split("/");
    const name = parts.pop();
    const subfolder = parts.join("/");

    const tile = document.createElement("div");
    tile.className = "icy-ref-tile";
    tile.title = `${idx + 1}. ${name}`;

    const thumb = document.createElement("img");
    thumb.className = "icy-ref-tile-thumb";
    thumb.src = thumbUrl(folder, { name, subfolder });
    thumb.onerror = () => { thumb.style.visibility = "hidden"; };
    tile.appendChild(thumb);

    const num = document.createElement("span");
    num.className = "icy-ref-tile-num";
    num.textContent = String(idx + 1);
    tile.appendChild(num);

    if (isVideo(name)) {
      const kind = document.createElement("span");
      kind.className = "icy-ref-tile-kind";
      kind.textContent = "▶ video";
      tile.appendChild(kind);
    }

    const rm = document.createElement("button");
    rm.className = "icy-ref-tile-x";
    rm.textContent = "✕";
    rm.title = "Remove";
    rm.onclick = (e) => {
      e.stopPropagation();
      const arr = mediaEntriesOf(node);
      arr.splice(idx, 1);
      setMediaEntries(node, arr);
    };
    tile.appendChild(rm);

    const mkNav = (label, title, posCls, delta, disabled) => {
      const b = document.createElement("button");
      b.className = `icy-ref-nav ${posCls}`;
      b.textContent = label;
      b.title = title;
      b.disabled = !!disabled;
      b.onclick = (e) => {
        e.stopPropagation();
        const arr = mediaEntriesOf(node);
        const j = idx + delta;
        if (j < 0 || j >= arr.length) return;
        [arr[idx], arr[j]] = [arr[j], arr[idx]];
        setMediaEntries(node, arr);
      };
      return b;
    };
    tile.appendChild(mkNav("◀", "Move earlier", "icy-ref-tile-nav-prev", -1, idx === 0));
    tile.appendChild(mkNav("▶", "Move later", "icy-ref-tile-nav-next", 1, idx === entries.length - 1));

    gridEl.appendChild(tile);
  });
}

function openGallery(node) {
  const folderW = findWidget(node, "folder");
  const viewer = new GalleryViewer(
    (folder, items) => applyMultiSelection(node, folder, items),
    folderW ? folderW.value : "input",
    true,
    mediaEntriesOf(node) // pre-select whatever is already loaded
  );
  viewer.open();
}

function buildMediaList(node) {
  if (typeof node.addDOMWidget !== "function") return; // fallback: plain text widget stays visible
  injectCss(); // the grid needs its styles immediately, not when the gallery first opens

  const root = document.createElement("div");
  root.className = "icy-reflist";

  const top = document.createElement("div");
  top.className = "icy-reflist-top";

  const drop = document.createElement("div");
  drop.className = "icy-reflist-drop";
  drop.textContent = "❄ drop media here · click to browse";
  drop.onclick = () => openGallery(node);
  top.appendChild(drop);

  const clearBtn = document.createElement("button");
  clearBtn.className = "icy-reflist-clear";
  clearBtn.textContent = "🗑 Clear all";
  clearBtn.title = "Remove all references";
  clearBtn.disabled = true;
  clearBtn.onclick = (e) => {
    e.stopPropagation();
    setMediaEntries(node, []);
  };
  top.appendChild(clearBtn);
  root.appendChild(top);
  root._clearBtn = clearBtn;

  const list = document.createElement("div");
  list.className = "icy-reflist-items";
  root.appendChild(list);
  root._list = list;
  node._icyRefListEl = root;

  root.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.stopPropagation();
    root.classList.add("icy-dragover");
  });
  root.addEventListener("dragleave", () => root.classList.remove("icy-dragover"));
  root.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    root.classList.remove("icy-dragover");
    handleFiles(node, e.dataTransfer?.files);
  });

  node.addDOMWidget("icy media list", "icy_reflist", root, {
    getValue: () => findWidget(node, "media")?.value ?? "",
    setValue: (v) => {
      const mediaW = findWidget(node, "media");
      if (mediaW) mediaW.value = v ?? "";
      renderMediaList(node);
    },
    height: 288,
  });

  const mediaW = findWidget(node, "media");
  if (mediaW) {
    mediaW.hidden = true;
    const origCb = mediaW.callback;
    mediaW.callback = function (...args) {
      const r = origCb ? origCb.apply(this, args) : undefined;
      renderMediaList(node);
      return r;
    };
  }
  const folderW = findWidget(node, "folder");
  if (folderW) {
    const origCb = folderW.callback;
    folderW.callback = function (...args) {
      const r = origCb ? origCb.apply(this, args) : undefined;
      renderMediaList(node);
      return r;
    };
  }

  renderMediaList(node);
}

let dropWired = false;
let dropHoverNode = null;

function nodeUnderEvent(e) {
  try {
    const canvas = app.canvas?.canvas;
    const ds = app.canvas?.ds;
    if (!canvas || !ds) return null;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / ds.scale - ds.offset[0];
    const y = (e.clientY - rect.top) / ds.scale - ds.offset[1];
    const n = app.graph?.getNodeOnPos?.(x, y, app.graph._nodes);
    return n?.icyMulti ? n : null;
  } catch {
    return null;
  }
}

function setDragNode(node) {
  if (dropHoverNode === node) return;
  if (dropHoverNode) {
    dropHoverNode._icyDragOver = false;
    dropHoverNode.setDirtyCanvas?.(true, true);
  }
  dropHoverNode = node;
  if (node) {
    node._icyDragOver = true;
    node.setDirtyCanvas?.(true, true);
  }
}

function wireDrop() {
  if (dropWired) return;
  dropWired = true;
  document.addEventListener(
    "dragover",
    (e) => {
      const n = nodeUnderEvent(e);
      if (n) {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
      setDragNode(n);
    },
    true
  );
  document.addEventListener(
    "drop",
    (e) => {
      let n = nodeUnderEvent(e);
      if (!n && e.target instanceof HTMLCanvasElement) {
        // canvas hit-test unavailable (e.g. Nodes 2.0): if the graph has exactly
        // one MultiRef node, take the drop anywhere on the canvas
        const nodes = (app.graph?._nodes || []).filter((x) => x.icyMulti);
        if (nodes.length === 1) n = nodes[0];
      }
      setDragNode(null);
      if (!n) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      handleFiles(n, e.dataTransfer?.files);
    },
    true
  );
}

app.registerExtension({
  name: "icy.loader",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const isMulti = nodeData.name === "IcyMultiRefLoader";
    if (!isMulti && nodeData.name !== "IcyImageLoader") return;

    if (isMulti) {
      const origDraw = nodeType.prototype.onDrawBackground;
      nodeType.prototype.onDrawBackground = function (ctx) {
        const r = origDraw ? origDraw.apply(this, arguments) : undefined;
        if (this._icyDragOver) {
          const w = this.size[0];
          const h = this.size[1];
          ctx.save();
          ctx.strokeStyle = "rgba(150,220,255,0.95)";
          ctx.lineWidth = 2.5;
          ctx.setLineDash([8, 6]);
          ctx.strokeRect(4, 4, w - 8, h - 8);
          ctx.setLineDash([]);
          ctx.fillStyle = "rgba(150,220,255,0.95)";
          ctx.font = "14px sans-serif";
          ctx.textAlign = "center";
          ctx.fillText("❄ drop media to add references", w / 2, h / 2);
          ctx.restore();
        }
        return r;
      };
    }

    const original = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = original ? original.apply(this, arguments) : undefined;
      try {
        if (isMulti) {
          buildMediaList(this);
          this.addWidget("button", "🖼️ Open Gallery", "gallery", () => openGallery(this));
          this.icyMulti = true;
          this.onDropFile = (file) => {
            handleFiles(this, [file]);
            return true;
          };
          wireDrop();
        } else {
          this.addWidget("button", "🖼️ Open Gallery", "gallery", () => {
            const folderW = findWidget(this, "folder");
            const viewer = new GalleryViewer(
              (folder, item) => applySelection(this, folder, item),
              folderW ? folderW.value : "input",
              false
            );
            viewer.open();
          });
        }
      } catch (e) {
        console.warn("Icy Loader: failed to add gallery widget", e);
      }
      return r;
    };
  },
});
