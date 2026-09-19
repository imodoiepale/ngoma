/**
 * Icy Prompt by icekiub - frontend
 * Compact status panel for the ICYLMStudioMultimodalPrompt node: connection
 * state, live streaming text with tok/s, batch metrics, context usage, and a
 * stream toggle. Collapses to a single slim bar when idle.
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_NAME = "ICYLMStudioMultimodalPrompt";
const STYLE_ID = "icylm-ui-styles";

const CSS = `
.icylm-panel {
    width: 100%;
    box-sizing: border-box;
    background: #12161d;
    border: 1px solid #27303d;
    border-radius: 10px;
    padding: 5px 8px;
    margin-top: 4px;
    font-family: var(--font-family, -apple-system, "Segoe UI", sans-serif);
    color: #cfd6e0;
    font-size: 11px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    pointer-events: auto;
}
.icylm-head {
    display: flex;
    align-items: center;
    gap: 7px;
    cursor: pointer;
    user-select: none;
}
.icylm-brand {
    font-weight: 600;
    color: #bfe4ff;
    white-space: nowrap;
    font-size: 11px;
}
.icylm-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #55606e;
    flex-shrink: 0;
    transition: background 0.2s;
}
.icylm-dot.online  { background: #7cc9ff; }
.icylm-dot.offline { background: #e0909e; }
.icylm-dot.checking{ background: #d9b06a; }
.icylm-status-text {
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    color: #8a96a8;
    flex: 1;
    min-width: 0;
}
.icylm-batch {
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    color: #7cc9ff;
    font-weight: 600;
    white-space: nowrap;
    background: rgba(124, 201, 255, 0.12);
    padding: 1px 6px;
    border-radius: 6px;
}
.icylm-btn {
    background: #262e3a;
    border: none;
    color: #dde3ec;
    border-radius: 6px;
    padding: 2px 7px;
    font-size: 10px;
    cursor: pointer;
    font-family: inherit;
    line-height: 1.4;
    transition: background 0.15s;
}
.icylm-btn:hover { background: #303a49; }
.icylm-btn.active { background: #58b8f0; color: #0d1420; }
.icylm-chev {
    color: #67748a;
    font-size: 9px;
    transition: transform 0.15s;
    flex-shrink: 0;
}
.icylm-panel.collapsed .icylm-chev { transform: rotate(-90deg); }
.icylm-panel.collapsed .icylm-body { display: none; }
.icylm-body {
    display: flex;
    flex-direction: column;
    gap: 5px;
}
.icylm-metrics {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 10px;
    color: #8a96a8;
}
.icylm-metrics b { color: #7cc9ff; font-weight: 600; }
.icylm-ctx {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 9px;
    color: #8a96a8;
}
.icylm-ctx-label { white-space: nowrap; }
.icylm-ctx-bar {
    flex: 1;
    height: 5px;
    background: #0a0d12;
    border-radius: 3px;
    overflow: hidden;
    min-width: 40px;
}
.icylm-ctx-fill {
    height: 100%;
    background: #58b8f0;
    width: 0%;
    transition: width 0.3s ease, background 0.3s ease;
}
.icylm-ctx-fill.warn { background: #d9b06a; }
.icylm-ctx-fill.crit { background: #e0909e; }
.icylm-preview {
    background: #0a0d12;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 7px;
    max-height: 54px;
    overflow: hidden;
    line-height: 1.35;
    color: #9aa5b5;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
}
.icylm-preview.empty { color: #55606e; font-style: italic; }
.icylm-preview.cache { color: #d9b06a; }
.icylm-preview.error { color: #e0909e; border-color: rgba(224, 144, 158, 0.4); }
.icylm-preview.streaming {
    color: #bfe4ff;
    border-color: rgba(124, 201, 255, 0.45);
}
`;

function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = CSS;
    document.head.appendChild(el);
}

function truncate(s, n) {
    s = String(s || "").replace(/\s+/g, " ").trim();
    return s.length <= n ? s : s.slice(0, n - 1) + "\u2026";
}

function fmtSec(ms) {
    const s = (ms || 0) / 1000;
    if (s >= 10) return s.toFixed(0) + "s";
    return s.toFixed(1) + "s";
}

function setContext(refs, used, limit, pct) {
    if (!refs) return;
    refs.ctxFill.style.width = Math.min(100, Math.max(0, pct)) + "%";
    refs.ctxFill.className = "icylm-ctx-fill" + (pct >= 95 ? " crit" : pct >= 80 ? " warn" : "");
    refs.ctxText.textContent = used + "/" + limit + " (" + pct + "%)";
}

// Live stream listener — registered once globally, dispatches by node id.
let streamListenerInstalled = false;
function ensureStreamListener() {
    if (streamListenerInstalled) return;
    streamListenerInstalled = true;
    api.addEventListener("icylm_stream", (e) => {
        const detail = e && e.detail;
        if (!detail || detail.node_id == null) return;
        const node = app.graph && app.graph.getNodeById(Number(detail.node_id));
        if (!node || !node._icylm) return;
        const refs = node._icylm;
        refs.preview.className = "icylm-preview streaming";
        refs.preview.textContent = truncate(detail.accumulated || "", 280);
        // live tok/s: each delta is roughly one token on llama.cpp/LM Studio
        const now = performance.now();
        if (!refs.streamStart) refs.streamStart = now;
        refs.streamTokens = (refs.streamTokens || 0) + 1;
        const secs = (now - refs.streamStart) / 1000;
        if (secs > 0.3) {
            refs.tps.innerHTML = "<b>" + (refs.streamTokens / secs).toFixed(1) + "</b> tok/s";
        }
    });
}

function buildPanel(node) {
    const panel = document.createElement("div");
    panel.className = "icylm-panel collapsed";

    // --- header (always visible, click to expand/collapse) ---
    const head = document.createElement("div");
    head.className = "icylm-head";

    const brand = document.createElement("span");
    brand.className = "icylm-brand";
    brand.textContent = "\u2744 Icy Prompt";
    const dot = document.createElement("span");
    dot.className = "icylm-dot checking";
    const statusText = document.createElement("span");
    statusText.className = "icylm-status-text";
    statusText.textContent = "checking\u2026";
    const batch = document.createElement("span");
    batch.className = "icylm-batch";
    batch.textContent = "#0";
    const streamBtn = document.createElement("button");
    streamBtn.className = "icylm-btn";
    streamBtn.type = "button";
    streamBtn.textContent = "\u26A1";
    streamBtn.title = "Toggle stream_response";
    const chev = document.createElement("span");
    chev.className = "icylm-chev";
    chev.textContent = "\u25BC";

    head.appendChild(brand);
    head.appendChild(dot);
    head.appendChild(statusText);
    head.appendChild(batch);
    head.appendChild(streamBtn);
    head.appendChild(chev);
    panel.appendChild(head);

    // --- collapsible body ---
    const body = document.createElement("div");
    body.className = "icylm-body";

    const metrics = document.createElement("div");
    metrics.className = "icylm-metrics";
    const tps = document.createElement("span");
    tps.innerHTML = "<b>0.0</b> tok/s";
    const batchSum = document.createElement("span");
    batchSum.textContent = "batch: 0 \u00b7 0 tok \u00b7 0.0s";
    metrics.appendChild(tps);
    metrics.appendChild(batchSum);
    body.appendChild(metrics);

    const ctx = document.createElement("div");
    ctx.className = "icylm-ctx";
    const ctxLabel = document.createElement("span");
    ctxLabel.className = "icylm-ctx-label";
    ctxLabel.textContent = "ctx";
    const ctxBar = document.createElement("div");
    ctxBar.className = "icylm-ctx-bar";
    const ctxFill = document.createElement("div");
    ctxFill.className = "icylm-ctx-fill";
    ctxBar.appendChild(ctxFill);
    const ctxText = document.createElement("span");
    ctxText.textContent = "0/0 (0%)";
    ctx.appendChild(ctxLabel);
    ctx.appendChild(ctxBar);
    ctx.appendChild(ctxText);
    body.appendChild(ctx);

    const preview = document.createElement("div");
    preview.className = "icylm-preview empty";
    preview.textContent = "No response yet.";
    body.appendChild(preview);

    panel.appendChild(body);

    node._icylm = {
        panel, dot, statusText, batch, tps, batchSum, ctxFill, ctxText, preview,
        streamStart: 0, streamTokens: 0,
    };

    const widget = node.addDOMWidget("ICYLM Status", "HTML", panel, {
        serialize: false,
        hideOnZoom: false,
    });
    widget.computeSize = () => (panel.classList.contains("collapsed") ? [0, 30] : [0, 150]);

    const getWidget = (name) => node.widgets && node.widgets.find((w) => w.name === name);
    const getBaseUrl = () => {
        const w = getWidget("base_url");
        return ((w && w.value) || "http://127.0.0.1:1234").replace(/\/+$/, "");
    };

    head.addEventListener("click", (e) => {
        if (e.target === streamBtn) return;
        panel.classList.toggle("collapsed");
        node.setDirtyCanvas(true, true);
    });

    const setStatus = (state, text) => {
        dot.className = "icylm-dot " + state;
        statusText.textContent = text;
    };
    const checkConnection = async () => {
        const base = getBaseUrl();
        try {
            const resp = await fetch(base + "/v1/models");
            if (!resp.ok) throw new Error("HTTP " + resp.status);
            const data = await resp.json();
            const count = (data && data.data && data.data.length) || 0;
            setStatus("online", count + " model" + (count === 1 ? "" : "s") + " available");
        } catch (e) {
            setStatus("offline", "offline");
        }
    };

    streamBtn.addEventListener("click", () => {
        const w = getWidget("stream_response");
        if (!w) return;
        w.value = !w.value;
        syncStreamBtn();
        if (typeof w.callback === "function") w.callback(w.value);
        node.setDirtyCanvas(true);
    });
    const syncStreamBtn = () => {
        const w = getWidget("stream_response");
        if (w && w.value) streamBtn.classList.add("active");
        else streamBtn.classList.remove("active");
    };
    // keep the button in sync if the widget is toggled elsewhere
    const streamWidget = getWidget("stream_response");
    if (streamWidget) {
        const orig = streamWidget.callback;
        streamWidget.callback = function () {
            if (orig) orig.apply(this, arguments);
            syncStreamBtn();
        };
    }

    // re-check connection whenever base_url changes
    const baseUrlWidget = getWidget("base_url");
    if (baseUrlWidget) {
        const orig = baseUrlWidget.callback;
        baseUrlWidget.callback = function () {
            if (orig) orig.apply(this, arguments);
            checkConnection();
        };
    }

    syncStreamBtn();
    ensureStreamListener();
    checkConnection();
    const timer = setInterval(checkConnection, 15000);
    node._icylmStopPolling = () => clearInterval(timer);
}

function updatePanelAfterExec(node, message) {
    const refs = node._icylm;
    if (!refs) return;
    try {
        const dbgRaw = message && message.debug_json;
        const dbg = dbgRaw && dbgRaw.length ? JSON.parse(dbgRaw[0] || "{}") : {};

        if (typeof dbg.batch_index === "number") {
            refs.batch.textContent = "#" + dbg.batch_index;
        }
        if (typeof dbg.tokens_per_second === "number") {
            refs.tps.innerHTML = "<b>" + dbg.tokens_per_second.toFixed(1) + "</b> tok/s";
        }
        if (typeof dbg.batch_count === "number") {
            refs.batchSum.textContent =
                "batch: " + dbg.batch_count +
                " \u00b7 " + (dbg.batch_total_tokens || 0) + " tok" +
                " \u00b7 " + fmtSec(dbg.batch_total_time_ms);
        }
        if (typeof dbg.context_limit === "number" && typeof dbg.context_used === "number") {
            setContext(refs, dbg.context_used, dbg.context_limit, dbg.context_pct || 0);
        }

        // reset live-stream counters; final metrics above have overwritten them
        refs.streamStart = 0;
        refs.streamTokens = 0;

        const texts = message && message.response_text;
        const first = texts && texts.length && typeof texts[0] === "string" ? texts[0] : "";
        if (first.startsWith("LM Studio request failed")) {
            refs.preview.className = "icylm-preview error";
            refs.preview.textContent = truncate(first, 220);
        } else if (first.length) {
            refs.preview.textContent = truncate(first, 220);
            refs.preview.className = "icylm-preview" + (dbg.cache_hit ? " cache" : "");
        } else if (dbg.cache_hit) {
            refs.preview.className = "icylm-preview cache";
        }
    } catch (e) {
        // never let a parse error break execution
    }
}

app.registerExtension({
    name: "Comfy.ICYLM.UI",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        injectStyles();

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            buildPanel(this);
            requestAnimationFrame(() => {
                if (this.size[0] < 320) this.size[0] = 320;
                this.setDirtyCanvas(true, true);
            });
            return r;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const res = onExecuted ? onExecuted.apply(this, arguments) : undefined;
            updatePanelAfterExec(this, message);
            return res;
        };

        const onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            if (this._icylmStopPolling) this._icylmStopPolling();
            return onRemoved ? onRemoved.apply(this, arguments) : undefined;
        };
    },
});
