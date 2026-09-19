import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "Comfy.IcyHider";
const SIDEBAR_TAB_ID = "icyhider";

const DEFAULT_TARGET_CLASSES = ["PreviewImage", "LoadImage", "SaveImage"];
const PREVIEW_WIDGET_TAGS = new Set(["IMG", "VIDEO", "CANVAS"]);
const PREVIEW_CLASS_HINTS = ["preview", "viewer"];

const SIDEBAR_THEME = {
    bg: "#0f141d",
    panel: "#1a2230",
    border: "#2b374a",
    text: "#e6edf3",
    muted: "#9fb0c8",
    button: "#223146",
    buttonAlt: "#1b2738",
    primary: "#2f81f7",
    primarySoft: "rgba(47, 129, 247, 0.25)",
};

let sidebarContainer = null;
let contextMenuHookInstalled = false;

// Hover reveal is delayed so brushing the mouse over a node does not flash its
// contents.  Arming/clearing happens on mouseenter/mouseleave (classic) or on
// the .lg-node element (Vue).  Per-node timers live here keyed by node id.
const hoverTimers = new Map();
function clearHoverTimer(nodeId) {
    const timer = hoverTimers.get(nodeId);
    if (timer !== undefined) {
        clearTimeout(timer);
        hoverTimers.delete(nodeId);
    }
}

// Vue-nodes mode renders .lg-node elements; classic canvas rendering does not.
// Decided LIVE per call: a cached value computed at extension setup time would
// be wrong (settings hydrate asynchronously and Vue nodes render later) and
// would go stale when the user toggles renderers at runtime.  The querySelector
// is cheap and only runs once per sync pass, not per node.
function isVueNodesMode() {
    return Boolean(document.querySelector(".lg-node"));
}

const settingsCache = {
    enabled: true,
    hideMode: "cover",
    blurAmount: 20,
    revealOnHover: true,
    revealDelay: 200,
    targetNodeClassesRaw: DEFAULT_TARGET_CLASSES.join(", "),
    targetNodeClasses: new Set(DEFAULT_TARGET_CLASSES.map((name) => name.toLowerCase())),
    hiddenNodeIdsRaw: "",
    hiddenNodeIds: new Set(),
    gradientStart: "1E3C72",
    gradientEnd: "2A5298",
    borderColor: "A5DEE5",
    icon: "❄️",
    text: "FROZEN",
    textColor: "E0F7FA",
    dirty: true,
};

function splitNodeClassList(value) {
    const raw = typeof value === "string" ? value : "";
    const parts = raw.split(",");
    const seen = new Set();
    const normalized = [];

    for (let i = 0; i < parts.length; i++) {
        const item = parts[i].trim();
        if (!item) continue;

        const key = item.toLowerCase();
        if (seen.has(key)) continue;

        seen.add(key);
        normalized.push(item);
    }

    if (!normalized.length) {
        return [...DEFAULT_TARGET_CLASSES];
    }

    return normalized;
}

function splitNodeIdList(value) {
    const raw = typeof value === "string" ? value : "";
    const parts = raw.split(",");
    const seen = new Set();
    const ids = [];

    for (let i = 0; i < parts.length; i++) {
        const parsed = parseInt(parts[i].trim(), 10);
        if (!Number.isFinite(parsed) || parsed < 0) continue;
        if (seen.has(parsed)) continue;

        seen.add(parsed);
        ids.push(parsed);
    }

    ids.sort((a, b) => a - b);
    return ids;
}

function setSettingValue(id, value) {
    if (!app.ui || !app.ui.settings || typeof app.ui.settings.setSettingValue !== "function") {
        return;
    }

    if (typeof app.ui.settings.getSettingValue === "function") {
        const currentValue = app.ui.settings.getSettingValue(id);
        if (currentValue === value) {
            return;
        }
    }

    app.ui.settings.setSettingValue(id, value);
}

function setTargetClassesInCache(classList) {
    const normalizedList = splitNodeClassList(classList.join(", "));
    settingsCache.targetNodeClassesRaw = normalizedList.join(", ");
    settingsCache.targetNodeClasses = new Set(
        normalizedList.map((className) => className.toLowerCase())
    );
}

function setHiddenNodeIdsInCache(ids) {
    const normalizedIds = splitNodeIdList(ids.join(","));
    settingsCache.hiddenNodeIdsRaw = normalizedIds.join(", ");
    settingsCache.hiddenNodeIds = new Set(normalizedIds);
}

// Source of truth for forced-hidden state is node.properties.icyHidden so it
// persists with the workflow JSON.  This rebuilds the in-memory cache by
// walking the current graph.
function rebuildHiddenNodeIdsFromGraph() {
    const ids = [];
    if (app.graph && app.graph._nodes) {
        for (let i = 0; i < app.graph._nodes.length; i++) {
            const n = app.graph._nodes[i];
            if (n && n.properties && n.properties.icyHidden === true) {
                const parsed = Number(n.id);
                if (Number.isFinite(parsed) && parsed >= 0) ids.push(parsed);
            }
        }
    }
    setHiddenNodeIdsInCache(ids);
}

function refreshSettingsCache() {
    if (!settingsCache.dirty) return;

    settingsCache.enabled = app.ui.settings.getSettingValue("IcyHider.Enabled", true);
    settingsCache.hideMode = app.ui.settings.getSettingValue("IcyHider.HideMode", "cover");
    settingsCache.blurAmount = app.ui.settings.getSettingValue("IcyHider.BlurAmount", 20);
    settingsCache.revealOnHover = app.ui.settings.getSettingValue("IcyHider.RevealOnHover", true);
    const parsedDelay = parseInt(
        app.ui.settings.getSettingValue("IcyHider.RevealDelay", 200),
        10
    );
    settingsCache.revealDelay = Number.isFinite(parsedDelay)
        ? Math.min(2000, Math.max(0, parsedDelay))
        : 200;

    const targetClassesRaw =
        app.ui.settings.getSettingValue(
            "IcyHider.TargetNodeClasses",
            DEFAULT_TARGET_CLASSES.join(", ")
        ) || DEFAULT_TARGET_CLASSES.join(", ");
    const targetClassList = splitNodeClassList(targetClassesRaw);
    settingsCache.targetNodeClassesRaw = targetClassList.join(", ");
    settingsCache.targetNodeClasses = new Set(targetClassList.map((name) => name.toLowerCase()));

    rebuildHiddenNodeIdsFromGraph();

    settingsCache.gradientStart =
        app.ui.settings.getSettingValue("IcyHider.GradientStart", "1E3C72") || "1E3C72";
    settingsCache.gradientEnd =
        app.ui.settings.getSettingValue("IcyHider.GradientEnd", "2A5298") || "2A5298";
    settingsCache.borderColor =
        app.ui.settings.getSettingValue("IcyHider.BorderColor", "A5DEE5") || "A5DEE5";
    settingsCache.icon = app.ui.settings.getSettingValue("IcyHider.Icon", "❄️") || "❄️";
    settingsCache.text = app.ui.settings.getSettingValue("IcyHider.Text", "FROZEN") || "FROZEN";
    settingsCache.textColor =
        app.ui.settings.getSettingValue("IcyHider.TextColor", "E0F7FA") || "E0F7FA";

    settingsCache.dirty = false;
}

function persistNormalizedListSettings() {
    setSettingValue("IcyHider.TargetNodeClasses", settingsCache.targetNodeClassesRaw);
}

function markSettingsDirty() {
    settingsCache.dirty = true;
}

function isNodeSelected(node) {
    return Boolean(
        node.is_selected ||
            node.selected ||
            (app.canvas && app.canvas.selected_nodes && app.canvas.selected_nodes[node.id])
    );
}

function isTargetClass(node) {
    if (!node || !node.comfyClass) return false;
    return settingsCache.targetNodeClasses.has(String(node.comfyClass).toLowerCase());
}

function isNodeForcedHidden(node) {
    return Boolean(node && node.properties && node.properties.icyHidden === true);
}

function shouldManageNode(node) {
    return isTargetClass(node) || isNodeForcedHidden(node) || shouldDetectNodeAsPreviewTarget(node);
}

function computeHiddenForNode(node) {
    if (!settingsCache.enabled) return false;
    if (!shouldManageNode(node)) return false;
    // Selection always reveals (intentional). Hover only reveals when enabled.
    if (isNodeSelected(node)) return false;
    if (settingsCache.revealOnHover && node.icy_is_hovered) return false;
    return true;
}

// Arm a delayed hover-reveal.  delay=0 applies immediately (identical to the
// old behavior); a positive delay waits that long before revealing, so
// brushing the mouse across a node does not flash its contents.  The caller
// owns the "leave cancels immediately" path via clearHoverTimer().
function scheduleHoverReveal(nodeId, apply, onChange) {
    clearHoverTimer(nodeId);
    const delay = settingsCache.revealDelay || 0;
    if (!delay) {
        apply(true);
        onChange();
        return;
    }
    hoverTimers.set(
        nodeId,
        setTimeout(() => {
            hoverTimers.delete(nodeId);
            apply(true);
            onChange();
        }, delay)
    );
}

function isAnimatedMediaElement(element) {
    if (!element || !element.tagName) return false;

    const tag = element.tagName.toUpperCase();

    if (tag === "VIDEO") {
        return true;
    }

    if (tag === "IMG") {
        const src = (element.src || "").toLowerCase();
        if (!src) return false;

        const animatedHints = [
            ".gif",
            ".apng",
            ".avif",
            ".webp",
            "format=image%2Fgif",
            "format=image/gif",
        ];

        return animatedHints.some((hint) => src.includes(hint));
    }

    return false;
}

function getWidgetStyleTargets(widget) {
    const element = widget.inputEl || widget.element;
    if (!element) {
        return { targets: [], hasDomPreview: false };
    }

    const targets = [];
    const seen = new Set();
    let hasDomPreview = false;

    const pushTarget = (target, marksPreview = false) => {
        if (!target || !target.style) return;
        if (seen.has(target)) return;

        seen.add(target);
        targets.push(target);
        if (marksPreview) {
            hasDomPreview = true;
        }
    };

    const tagName = element.tagName ? String(element.tagName).toUpperCase() : "";
    const isElementPreview = PREVIEW_WIDGET_TAGS.has(tagName);
    const isElementTextInput =
        tagName === "TEXTAREA" ||
        (typeof element.classList?.contains === "function" &&
            element.classList.contains("comfy-multiline-input"));

    if (isElementPreview) {
        pushTarget(element, true);
    }
    if (isElementTextInput) {
        pushTarget(element, false);
    }

    if (typeof element.querySelectorAll === "function") {
        const mediaTargets = element.querySelectorAll("img, video, canvas");
        for (let i = 0; i < mediaTargets.length; i++) {
            pushTarget(mediaTargets[i], true);
        }

        const inputTargets = element.querySelectorAll("textarea, .comfy-multiline-input");
        for (let i = 0; i < inputTargets.length; i++) {
            pushTarget(inputTargets[i], false);
        }
    }

    if (!targets.length) {
        pushTarget(element, false);
    }

    return { targets, hasDomPreview };
}

function updateNodeDOMElements(node, hide) {
    if (!node.widgets) {
        node.icy_has_dom_preview = false;
        return;
    }

    const hideMode = settingsCache.hideMode;
    const blurAmount = settingsCache.blurAmount;
    let nodeHasDomPreview = false;

    for (let i = 0; i < node.widgets.length; i++) {
        const widget = node.widgets[i];
        const { targets, hasDomPreview } = getWidgetStyleTargets(widget);
        if (!targets.length) continue;

        if (hasDomPreview) {
            nodeHasDomPreview = true;
        }

        for (let j = 0; j < targets.length; j++) {
            const target = targets[j];
            const effectiveMode = isAnimatedMediaElement(target) ? "cover" : hideMode;

            if (hide && effectiveMode === "blur") {
                target.style.filter = `blur(${blurAmount}px)`;
                target.style.opacity = "1";
                target.style.pointerEvents = "none";
                target.style.userSelect = "none";
            } else if (hide && effectiveMode === "cover") {
                target.style.filter = "none";
                target.style.opacity = "0";
                target.style.pointerEvents = "none";
                target.style.userSelect = "none";
            } else {
                target.style.filter = "none";
                target.style.opacity = "1";
                target.style.pointerEvents = "auto";
                target.style.userSelect = "auto";
            }
        }
    }

    node.icy_has_dom_preview = nodeHasDomPreview;
}

function updateNodeHidden(node, skipDOMUpdate = false, forceDOMUpdate = false) {
    const shouldManage = settingsCache.enabled && shouldManageNode(node);

    if (!shouldManage) {
        const wasManagedOrHidden = Boolean(node.icy_managed || node.icy_hidden);
        if (!wasManagedOrHidden && !forceDOMUpdate) return false;

        node.icy_managed = false;
        node.icy_hidden = false;
        if (!skipDOMUpdate) {
            updateNodeDOMElements(node, false);
        }
        return wasManagedOrHidden;
    }

    node.icy_managed = true;
    const newHidden = computeHiddenForNode(node);

    if (node.icy_hidden === newHidden) {
        if (forceDOMUpdate && !skipDOMUpdate) {
            updateNodeDOMElements(node, node.icy_hidden);
        }
        return false;
    }

    node.icy_hidden = newHidden;
    if (!skipDOMUpdate) {
        updateNodeDOMElements(node, node.icy_hidden);
    }

    return true;
}

function syncHiddenState(node) {
    if (!node.icy_managed) return;

    const newHidden = computeHiddenForNode(node);
    if (node.icy_hidden !== newHidden) {
        node.icy_hidden = newHidden;
        updateNodeDOMElements(node, newHidden);
    }
}

// --- Vue / Nodes 2.0 rendering ---------------------------------------------
// In Vue mode the LiteGraph canvas is never painted, so hiding is driven from
// the DOM instead.  Each rendered node is a `.lg-node[data-node-id]` element.
// We keep the node element itself visible (display:none breaks slot geometry
// and snaps links) and instead occlude its contents with either a CSS blur on
// the element or an absolutely-positioned cover child.

const VUE_OVERLAY_ATTR = "data-icy-overlay";
const VUE_HOVER_BOUND_ATTR = "data-icy-hover-bound";

function graphNodeByStringId(idStr) {
    // app.canvas.graph is the graph currently on screen -- inside a subgraph it
    // differs from app.graph, and the visible .lg-node elements belong to it.
    const graphs = [app.canvas && app.canvas.graph, app.graph];
    const asNum = Number(idStr);
    for (let g = 0; g < graphs.length; g++) {
        const nodes = graphs[g] && graphs[g]._nodes;
        if (!nodes) continue;
        for (let i = 0; i < nodes.length; i++) {
            const n = nodes[i];
            if (String(n.id) === idStr || Number(n.id) === asNum) return n;
        }
    }
    return null;
}

// A Vue node's media is rendered inside its DOM, so animated-media detection
// works directly on the element tree instead of guessing from a filename.
function vueNodeHasAnimatedMedia(nodeEl) {
    if (!nodeEl) return false;
    if (nodeEl.querySelector("video")) return true;
    const imgs = nodeEl.querySelectorAll("img");
    for (let i = 0; i < imgs.length; i++) {
        const src = (imgs[i].src || "").toLowerCase();
        if (!src) continue;
        if (
            src.includes(".gif") ||
            src.includes(".apng") ||
            src.includes("format=image%2fgif") ||
            src.includes("format=image/gif")
        ) {
            return true;
        }
    }
    return false;
}

function buildVueCoverOverlay() {
    const overlay = document.createElement("div");
    overlay.setAttribute(VUE_OVERLAY_ATTR, "1");
    overlay.style.position = "absolute";
    overlay.style.inset = "0";
    overlay.style.zIndex = "50";
    overlay.style.pointerEvents = "none";
    overlay.style.display = "flex";
    overlay.style.flexDirection = "column";
    overlay.style.alignItems = "center";
    overlay.style.justifyContent = "center";
    overlay.style.gap = "6px";
    overlay.style.borderRadius = "inherit";
    overlay.style.background = `linear-gradient(135deg, #${settingsCache.gradientStart}, #${settingsCache.gradientEnd})`;
    overlay.style.border = `2px solid #${settingsCache.borderColor}`;
    overlay.style.color = `#${settingsCache.textColor}`;
    overlay.style.userSelect = "none";

    const icon = document.createElement("div");
    icon.textContent = settingsCache.icon;
    icon.style.fontSize = "32px";
    icon.style.lineHeight = "1";
    overlay.appendChild(icon);

    const label = document.createElement("div");
    label.textContent = settingsCache.text;
    label.style.fontWeight = "700";
    label.style.fontSize = "14px";
    label.style.textShadow = "0 1px 4px rgba(0,0,0,0.5)";
    overlay.appendChild(label);

    return overlay;
}

function applyVueHidden(nodeEl, node, hidden) {
    if (!nodeEl) return;

    // Blur mode: filter the whole node body.  Animated media is forced to cover
    // (a blurred video is still recognizably a video, and motion leaks frames).
    const forceCover = vueNodeHasAnimatedMedia(nodeEl);
    const useCover = hidden && (settingsCache.hideMode === "cover" || forceCover);
    const useBlur = hidden && settingsCache.hideMode === "blur" && !forceCover;

    // Write only when the value actually changes: the body observer watches the
    // style attribute, so an unconditional rewrite of the same filter value
    // would re-trigger the observer and loop sync forever.
    const filter = useBlur ? `blur(${settingsCache.blurAmount}px)` : "";
    if (nodeEl.style.filter !== filter) {
        nodeEl.style.filter = filter;
    }

    const existing = nodeEl.querySelector(`[${VUE_OVERLAY_ATTR}]`);
    if (useCover) {
        if (!existing) {
            nodeEl.appendChild(buildVueCoverOverlay());
        }
    } else if (existing) {
        existing.remove();
    }
}

function ensureVueHoverBinding(nodeEl) {
    if (nodeEl.getAttribute(VUE_HOVER_BOUND_ATTR) === "1") return;
    nodeEl.setAttribute(VUE_HOVER_BOUND_ATTR, "1");

    // Resolve the graph node at event time: Vue reuses these elements across
    // workflow loads while the graph node objects are replaced, so a captured
    // node reference would go stale.
    const nodeId = nodeEl.dataset.nodeId;
    nodeEl.addEventListener("mouseenter", () => {
        const node = graphNodeByStringId(nodeId);
        if (!node) return;
        scheduleHoverReveal(
            node.id,
            (h) => {
                node.icy_is_hovered = h;
            },
            scheduleVueSync
        );
    });
    nodeEl.addEventListener("mouseleave", () => {
        const node = graphNodeByStringId(nodeId);
        if (!node) return;
        clearHoverTimer(node.id);
        node.icy_is_hovered = false;
        scheduleVueSync();
    });
}

let vueSyncQueued = false;
function scheduleVueSync() {
    if (vueSyncQueued) return;
    vueSyncQueued = true;
    requestAnimationFrame(() => {
        vueSyncQueued = false;
        syncVueNodes();
    });
}

function syncVueNodes() {
    if (!isVueNodesMode()) return;
    refreshSettingsCache();

    const nodeEls = document.querySelectorAll(".lg-node[data-node-id]");
    if (!nodeEls.length) return;

    for (let i = 0; i < nodeEls.length; i++) {
        const nodeEl = nodeEls[i];
        const node = graphNodeByStringId(nodeEl.dataset.nodeId);
        if (!node) {
            // No backing graph node (transient/ghost): make sure we leave no overlay.
            const overlay = nodeEl.querySelector(`[${VUE_OVERLAY_ATTR}]`);
            if (overlay) overlay.remove();
            if (nodeEl.style.filter) nodeEl.style.filter = "";
            continue;
        }

        if (node.icy_managed === undefined) node.icy_managed = false;
        if (node.icy_hidden === undefined) node.icy_hidden = false;

        // Mirror the classic updateNodeHidden decision so hover/selection/target
        // logic stays in one place.
        const shouldManage = settingsCache.enabled && shouldManageNode(node);
        if (!shouldManage) {
            node.icy_managed = false;
            node.icy_hidden = false;
            // Cleanup must be decided from the DOM, not from the node flags:
            // the classic updateNodeHidden pass (refreshAllNodes) already
            // cleared the flags before this sync runs, so gating on them here
            // would leave a stale overlay behind after disabling.
            if (nodeEl.querySelector(`[${VUE_OVERLAY_ATTR}]`) || nodeEl.style.filter) {
                applyVueHidden(nodeEl, node, false);
            }
            continue;
        }

        node.icy_managed = true;
        ensureVueHoverBinding(nodeEl);

        const newHidden = computeHiddenForNode(node);
        if (node.icy_hidden !== newHidden) {
            node.icy_hidden = newHidden;
            applyVueHidden(nodeEl, node, newHidden);
        } else {
            // Re-apply anyway: settings (mode/blur/colors) may have changed.
            applyVueHidden(nodeEl, node, node.icy_hidden);
        }
    }
}

function drawCoverOverlay(ctx, node) {
    const titleHeight = 30;
    const gradStart = `#${settingsCache.gradientStart}`;
    const gradEnd = `#${settingsCache.gradientEnd}`;
    const borderColor = `#${settingsCache.borderColor}`;
    const textColor = `#${settingsCache.textColor}`;

    ctx.save();

    const grad = ctx.createLinearGradient(0, titleHeight, 0, node.size[1]);
    grad.addColorStop(0, gradStart);
    grad.addColorStop(1, gradEnd);
    ctx.fillStyle = grad;

    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(0, titleHeight, node.size[0], node.size[1] - titleHeight, [0, 0, 10, 10]);
    } else {
        ctx.rect(0, titleHeight, node.size[0], node.size[1] - titleHeight);
    }
    ctx.fill();

    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 2;
    ctx.stroke();

    const centerX = node.size[0] / 2;
    const centerY = (node.size[1] + titleHeight) / 2;

    ctx.fillStyle = textColor;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.font = "32px Arial";
    ctx.fillText(settingsCache.icon, centerX, centerY - 15);

    ctx.font = "bold 14px Arial";
    ctx.shadowColor = "rgba(0, 0, 0, 0.5)";
    ctx.shadowBlur = 4;
    ctx.fillText(settingsCache.text, centerX, centerY + 15);

    ctx.restore();
}

function drawBlurred(ctx, node, drawFn, argsLike) {
    if (!drawFn) return;

    ctx.save();

    const titleHeight = 30;
    ctx.beginPath();
    ctx.rect(0, titleHeight, node.size[0], node.size[1] - titleHeight);
    ctx.clip();

    ctx.filter = `blur(${settingsCache.blurAmount}px)`;
    drawFn.apply(node, argsLike);
    ctx.filter = "none";

    ctx.restore();
}

function findBlurredNodeForImage(image) {
    if (!image || !settingsCache.enabled) return null;
    if (settingsCache.hideMode !== "blur") return null;
    if (!app.graph || !app.graph._nodes) return null;

    const nodes = app.graph._nodes;
    for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        if (!node.icy_managed || !node.icy_hidden) continue;

        const imgs = node.imgs;
        if (imgs && imgs.length) {
            for (let j = 0; j < imgs.length; j++) {
                if (imgs[j] === image) return node;
            }
        }

        const animatedImages = node.animatedImages;
        if (animatedImages && animatedImages.length) {
            for (let j = 0; j < animatedImages.length; j++) {
                if (animatedImages[j] === image) return node;
            }
        }
    }
    return null;
}

function patchCanvasDrawImage() {
    // In Vue/Nodes 2.0 mode the LiteGraph canvas is never painted into, so the
    // drawImage patch would be dead code on top of a no-op renderer.  Skip it
    // rather than spin the retry loop in setup() forever.
    if (isVueNodesMode()) return true;

    const canvasEl = app.canvas?.canvas;
    if (!canvasEl) return false;

    const ctx = canvasEl.getContext("2d");
    if (!ctx || ctx._icyDrawImagePatched) return Boolean(ctx?._icyDrawImagePatched);

    const original = ctx.drawImage;
    ctx.drawImage = function patchedDrawImage(image) {
        const ownerNode = findBlurredNodeForImage(image);
        if (ownerNode) {
            // The deferred render closure (scheduleDeferredImageRender) restores the
            // LiteGraph node-local transform before calling drawImage, so coordinates
            // here are node-local (0,0 = node top-left).  Clip to the node body so
            // the blur never bleeds outside the node boundaries.
            const titleHeight = (window.LiteGraph?.NODE_TITLE_HEIGHT ?? 30);
            this.save();
            this.beginPath();
            this.rect(0, titleHeight, ownerNode.size[0], ownerNode.size[1] - titleHeight);
            this.clip();
            this.filter = `blur(${settingsCache.blurAmount}px)`;
            try {
                original.apply(this, arguments);
            } finally {
                this.restore();
            }
            return;
        }
        return original.apply(this, arguments);
    };
    ctx._icyDrawImagePatched = true;
    return true;
}

function refreshAllNodes(options = {}) {
    const forceVisualUpdate = Boolean(options.forceVisualUpdate);
    const skipSettingsRefresh = Boolean(options.skipSettingsRefresh);

    if (!skipSettingsRefresh) {
        refreshSettingsCache();
    }

    if (!app.graph || !app.graph._nodes) return;

    // Rebuild hidden-id cache from current graph each refresh: keeps it in sync
    // after workflow load, node deletion, copy/paste, or remote changes.
    rebuildHiddenNodeIdsFromGraph();

    for (let i = 0; i < app.graph._nodes.length; i++) {
        const node = app.graph._nodes[i];
        const changed = updateNodeHidden(node, false, forceVisualUpdate);
        if (changed || (forceVisualUpdate && node.icy_managed)) {
            node.setDirtyCanvas?.(true, true);
        }
    }

    app.graph.setDirtyCanvas?.(true, true);

    if (isVueNodesMode()) {
        // No canvas painting in Vue mode; drive DOM updates directly.
        scheduleVueSync();
    } else {
        // If the session started in Vue mode the drawImage patch was skipped;
        // re-attempt it in case the user switched to classic at runtime
        // (patchCanvasDrawImage is a no-op once installed).
        patchCanvasDrawImage();
    }
}

function requestSidebarRefresh() {
    if (sidebarContainer) {
        buildSidebarContent(sidebarContainer);
    }
}

// Update only the live-value widgets in place.  Used by settings that change a
// value (blur amount, reveal delay, target classes) without changing panel
// structure, so the textarea/slider the user is editing keeps focus.
function requestSidebarValueRefresh() {
    if (!sidebarContainer) return;
    const refs = sidebarContainer._icyRefs;
    if (!refs) {
        buildSidebarContent(sidebarContainer);
        return;
    }

    if (refs.blurLabel) {
        refs.blurLabel.textContent = `Blur Amount: ${settingsCache.blurAmount}px`;
    }
    if (refs.blurSlider && document.activeElement !== refs.blurSlider) {
        refs.blurSlider.value = String(settingsCache.blurAmount);
    }
    if (refs.delayLabel) {
        refs.delayLabel.textContent = `Reveal Delay: ${settingsCache.revealDelay}ms`;
    }
    if (refs.delaySlider && document.activeElement !== refs.delaySlider) {
        refs.delaySlider.value = String(settingsCache.revealDelay);
    }
    // Only re-seed the textarea when the user is not actively editing it;
    // otherwise we clobber in-progress typing.
    if (
        refs.targetInput &&
        document.activeElement !== refs.targetInput &&
        refs.targetInput.value !== settingsCache.targetNodeClassesRaw
    ) {
        refs.targetInput.value = settingsCache.targetNodeClassesRaw;
    }
}

function markDirtyAndRefresh() {
    markSettingsDirty();
    refreshSettingsCache();
    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarRefresh();
}

function applyEnabledSettingValue(newValue) {
    settingsCache.enabled = Boolean(newValue);
    settingsCache.dirty = false;
    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarRefresh();
}

function applyHideModeSettingValue(newValue) {
    settingsCache.hideMode = newValue === "blur" ? "blur" : "cover";
    settingsCache.dirty = false;
    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarRefresh();
}

function applyBlurAmountSettingValue(newValue) {
    const parsed = parseInt(newValue, 10);
    settingsCache.blurAmount = Number.isFinite(parsed)
        ? Math.min(50, Math.max(0, parsed))
        : settingsCache.blurAmount;
    settingsCache.dirty = false;
    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarValueRefresh();
}

function applyTargetNodeClassesSettingValue(rawValue) {
    const nextClasses = splitNodeClassList(rawValue);
    setTargetClassesInCache(nextClasses);
    settingsCache.dirty = false;
    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarRefresh();
}

function shouldDetectNodeAsPreviewTarget(node) {
    if (!node) return false;

    // Runtime-populated preview data (set after execution by Comfy / VHS / etc.)
    if (node.imgs && node.imgs.length) return true;
    if (node.animatedImages && node.animatedImages.length) return true;
    if (node.videos && node.videos.length) return true;
    if (node.preview && node.preview.length) return true;

    const className = String(node.comfyClass || node.type || "").trim();
    const lowerClass = className.toLowerCase();
    if (className && PREVIEW_CLASS_HINTS.some((hint) => lowerClass.includes(hint))) {
        return true;
    }

    // Class-name hints for common video/animation preview nodes
    if (className) {
        const videoHints = ["video", "animated", "webp", "gif", "mp4"];
        if (videoHints.some((hint) => lowerClass.includes(hint))) {
            // only count if it has widgets / outputs that look media-related
            if (node.widgets || (node.outputs && node.outputs.length)) {
                return true;
            }
        }
    }

    // Output type hints
    if (node.outputs && node.outputs.length) {
        for (let i = 0; i < node.outputs.length; i++) {
            const out = node.outputs[i];
            const t = String(out?.type || "").toUpperCase();
            if (t === "IMAGE" || t === "VIDEO" || t === "MASK" || t === "VHS_VIDEO") {
                // image output alone isn't enough — only count if combined with no other useful output
                // Skip — too broad. Keep this hint disabled by default.
            }
        }
    }

    if (!node.widgets) return false;

    for (let i = 0; i < node.widgets.length; i++) {
        const widget = node.widgets[i];
        const element = widget.inputEl || widget.element;
        if (!element) continue;

        const tagName = element.tagName ? String(element.tagName).toUpperCase() : "";
        if (PREVIEW_WIDGET_TAGS.has(tagName)) return true;

        // Deep scan: many video/image preview widgets wrap <video>/<img>/<canvas>
        // inside a container div.
        if (typeof element.querySelector === "function") {
            if (element.querySelector("video, img, canvas")) {
                return true;
            }
        }
    }

    return false;
}

function detectTargetNodeClassesFromGraph() {
    if (!app.graph || !app.graph._nodes || !app.graph._nodes.length) {
        return [...DEFAULT_TARGET_CLASSES];
    }

    const discovered = [];
    const seen = new Set();

    for (let i = 0; i < app.graph._nodes.length; i++) {
        const node = app.graph._nodes[i];
        if (!shouldDetectNodeAsPreviewTarget(node)) continue;

        const className = String(node.comfyClass || "").trim();
        if (!className) continue;

        const key = className.toLowerCase();
        if (seen.has(key)) continue;

        seen.add(key);
        discovered.push(className);
    }

    if (!discovered.length) {
        return [...DEFAULT_TARGET_CLASSES];
    }

    discovered.sort((a, b) => a.localeCompare(b));
    return discovered;
}

function autoDetectTargetClassesFromGraph() {
    refreshSettingsCache();
    const detected = detectTargetNodeClassesFromGraph();
    setTargetClassesInCache(detected);
    settingsCache.dirty = false;
    persistNormalizedListSettings();

    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarValueRefresh();
}

function updateTargetClassesFromRawValue(rawValue) {
    refreshSettingsCache();
    const nextClasses = splitNodeClassList(rawValue);
    setTargetClassesInCache(nextClasses);
    settingsCache.dirty = false;
    persistNormalizedListSettings();

    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarValueRefresh();
}

function findGraphNodeById(nodeId) {
    if (!app.graph || !app.graph._nodes) return null;
    const target = Number(nodeId);
    for (let i = 0; i < app.graph._nodes.length; i++) {
        if (Number(app.graph._nodes[i].id) === target) return app.graph._nodes[i];
    }
    return null;
}

function markGraphChanged() {
    if (app.graph && typeof app.graph.change === "function") {
        app.graph.change();
    }
}

function addNodeIdsToHiddenState(nodeIds) {
    let changed = false;

    for (let i = 0; i < nodeIds.length; i++) {
        const parsed = parseInt(nodeIds[i], 10);
        if (!Number.isFinite(parsed) || parsed < 0) continue;

        const node = findGraphNodeById(parsed);
        if (!node) continue;
        if (!node.properties) node.properties = {};
        if (node.properties.icyHidden !== true) {
            node.properties.icyHidden = true;
            changed = true;
        }
    }

    if (!changed) return false;

    rebuildHiddenNodeIdsFromGraph();
    markGraphChanged();
    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarRefresh();
    return true;
}

function removeNodeIdsFromHiddenState(nodeIds) {
    let changed = false;

    for (let i = 0; i < nodeIds.length; i++) {
        const parsed = parseInt(nodeIds[i], 10);
        if (!Number.isFinite(parsed) || parsed < 0) continue;

        const node = findGraphNodeById(parsed);
        if (!node || !node.properties) continue;
        if (node.properties.icyHidden) {
            delete node.properties.icyHidden;
            changed = true;
        }
    }

    if (!changed) return false;

    rebuildHiddenNodeIdsFromGraph();
    markGraphChanged();
    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarRefresh();
    return true;
}

function clearHiddenNodeIds() {
    let changed = false;
    if (app.graph && app.graph._nodes) {
        for (let i = 0; i < app.graph._nodes.length; i++) {
            const n = app.graph._nodes[i];
            if (n && n.properties && n.properties.icyHidden) {
                delete n.properties.icyHidden;
                changed = true;
            }
        }
    }

    if (!changed) return;

    rebuildHiddenNodeIdsFromGraph();
    markGraphChanged();
    refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
    requestSidebarRefresh();
}

function getSelectedNodeIds() {
    const selected = app && app.canvas && app.canvas.selected_nodes;
    if (!selected) return [];

    const ids = Object.keys(selected)
        .map((id) => parseInt(id, 10))
        .filter((id) => Number.isFinite(id));

    ids.sort((a, b) => a - b);
    return ids;
}

function findNodeClassById(nodeId) {
    if (!app.graph || !app.graph._nodes) return "Unknown";

    for (let i = 0; i < app.graph._nodes.length; i++) {
        const node = app.graph._nodes[i];
        if (Number(node.id) === Number(nodeId)) {
            return String(node.comfyClass || node.type || "Unknown");
        }
    }

    return "Unknown";
}

function createSidebarSection(container, title) {
    const section = document.createElement("div");
    section.style.padding = "10px";
    section.style.background = SIDEBAR_THEME.panel;
    section.style.border = `1px solid ${SIDEBAR_THEME.border}`;
    section.style.borderRadius = "8px";
    section.style.display = "flex";
    section.style.flexDirection = "column";
    section.style.gap = "8px";

    const heading = document.createElement("div");
    heading.textContent = title;
    heading.style.fontSize = "10px";
    heading.style.fontWeight = "700";
    heading.style.color = SIDEBAR_THEME.muted;
    heading.style.textTransform = "uppercase";
    heading.style.letterSpacing = "0.5px";
    section.appendChild(heading);

    container.appendChild(section);
    return section;
}

function createActionButton(label, onClick, isPrimary = false) {
    const button = document.createElement("button");
    button.textContent = label;
    button.style.border = "none";
    button.style.borderRadius = "6px";
    button.style.padding = "7px 10px";
    button.style.cursor = "pointer";
    button.style.fontFamily = "inherit";
    button.style.fontSize = "11px";
    button.style.textAlign = "left";
    button.style.background = isPrimary
        ? SIDEBAR_THEME.primarySoft
        : SIDEBAR_THEME.buttonAlt;
    button.style.color = SIDEBAR_THEME.text;
    button.style.border = `1px solid ${SIDEBAR_THEME.border}`;
    button.style.transition = "background 120ms ease";
    button.addEventListener("mouseenter", () => {
        button.style.background = isPrimary ? SIDEBAR_THEME.primarySoft : SIDEBAR_THEME.button;
    });
    button.addEventListener("mouseleave", () => {
        button.style.background = isPrimary ? SIDEBAR_THEME.primarySoft : SIDEBAR_THEME.buttonAlt;
    });
    button.addEventListener("click", onClick);
    return button;
}

function buildSidebarContent(container) {
    refreshSettingsCache();

    container.innerHTML = "";
    container.style.display = "flex";
    container.style.flexDirection = "column";
    container.style.gap = "8px";
    container.style.padding = "12px 8px";
    container.style.height = "100%";
    container.style.overflowY = "auto";
    container.style.boxSizing = "border-box";
    container.style.background = SIDEBAR_THEME.bg;
    container.style.color = SIDEBAR_THEME.text;

    const header = document.createElement("div");
    header.style.fontSize = "13px";
    header.style.fontWeight = "600";
    header.style.color = SIDEBAR_THEME.text;
    header.style.padding = "8px";
    header.style.background = SIDEBAR_THEME.panel;
    header.style.border = `1px solid ${SIDEBAR_THEME.border}`;
    header.style.marginBottom = "4px";
    header.style.borderRadius = "8px";
    header.innerHTML = "<span style=\"font-size:16px; margin-right:8px;\">❄️</span>Icy Hider";
    container.appendChild(header);

    const behaviorSection = createSidebarSection(container, "Behavior");

    const enableButton = createActionButton(
        settingsCache.enabled ? "Disable Preview Hiding" : "Enable Preview Hiding",
        () => {
            const nextEnabled = !settingsCache.enabled;
            setSettingValue("IcyHider.Enabled", nextEnabled);
            applyEnabledSettingValue(nextEnabled);
        },
        !settingsCache.enabled
    );
    behaviorSection.appendChild(enableButton);

    const modeRow = document.createElement("div");
    modeRow.style.display = "flex";
    modeRow.style.gap = "6px";

    const coverButton = createActionButton(
        "Cover",
        () => {
            setSettingValue("IcyHider.HideMode", "cover");
            applyHideModeSettingValue("cover");
        },
        settingsCache.hideMode === "cover"
    );
    coverButton.style.flex = "1";

    const blurButton = createActionButton(
        "Blur",
        () => {
            setSettingValue("IcyHider.HideMode", "blur");
            applyHideModeSettingValue("blur");
        },
        settingsCache.hideMode === "blur"
    );
    blurButton.style.flex = "1";

    modeRow.appendChild(coverButton);
    modeRow.appendChild(blurButton);
    behaviorSection.appendChild(modeRow);

    const blurLabel = document.createElement("div");
    blurLabel.textContent = `Blur Amount: ${settingsCache.blurAmount}px`;
    blurLabel.style.fontSize = "11px";
    blurLabel.style.color = SIDEBAR_THEME.text;
    behaviorSection.appendChild(blurLabel);

    const blurSlider = document.createElement("input");
    blurSlider.type = "range";
    blurSlider.min = "0";
    blurSlider.max = "50";
    blurSlider.step = "1";
    blurSlider.value = String(settingsCache.blurAmount);
    blurSlider.addEventListener("input", () => {
        const nextValue = parseInt(blurSlider.value, 10);
        const clamped = Number.isFinite(nextValue) ? Math.min(50, Math.max(0, nextValue)) : 20;
        setSettingValue("IcyHider.BlurAmount", clamped);
        applyBlurAmountSettingValue(clamped);
        blurLabel.textContent = `Blur Amount: ${settingsCache.blurAmount}px`;
    });
    behaviorSection.appendChild(blurSlider);

    const hoverButton = createActionButton(
        settingsCache.revealOnHover ? "Hover Reveal: On" : "Hover Reveal: Off",
        () => {
            const next = !settingsCache.revealOnHover;
            setSettingValue("IcyHider.RevealOnHover", next);
            settingsCache.revealOnHover = next;
            settingsCache.dirty = false;
            hoverButton.textContent = next ? "Hover Reveal: On" : "Hover Reveal: Off";
            refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
        },
        settingsCache.revealOnHover
    );
    behaviorSection.appendChild(hoverButton);

    const delayLabel = document.createElement("div");
    delayLabel.textContent = `Reveal Delay: ${settingsCache.revealDelay}ms`;
    delayLabel.style.fontSize = "11px";
    delayLabel.style.color = SIDEBAR_THEME.text;
    behaviorSection.appendChild(delayLabel);

    const delaySlider = document.createElement("input");
    delaySlider.type = "range";
    delaySlider.min = "0";
    delaySlider.max = "2000";
    delaySlider.step = "50";
    delaySlider.value = String(settingsCache.revealDelay);
    delaySlider.addEventListener("input", () => {
        const nextValue = parseInt(delaySlider.value, 10);
        const clamped = Number.isFinite(nextValue) ? Math.min(2000, Math.max(0, nextValue)) : 200;
        setSettingValue("IcyHider.RevealDelay", clamped);
        settingsCache.revealDelay = clamped;
        settingsCache.dirty = false;
        delayLabel.textContent = `Reveal Delay: ${settingsCache.revealDelay}ms`;
    });
    behaviorSection.appendChild(delaySlider);

    // Cache the live-value widgets so external changes can update them in
    // place instead of tearing the whole panel down (which would steal focus
    // from the textarea/slider the user is interacting with).
    container._icyRefs = { blurLabel, blurSlider, delayLabel, delaySlider };

    const targetSection = createSidebarSection(container, "Target Classes");

    const targetInput = document.createElement("textarea");
    targetInput.value = settingsCache.targetNodeClassesRaw;
    targetInput.rows = 3;
    targetInput.style.width = "100%";
    targetInput.style.resize = "vertical";
    targetInput.style.boxSizing = "border-box";
    targetInput.style.background = SIDEBAR_THEME.bg;
    targetInput.style.border = `1px solid ${SIDEBAR_THEME.border}`;
    targetInput.style.borderRadius = "6px";
    targetInput.style.color = SIDEBAR_THEME.text;
    targetInput.style.fontFamily = "inherit";
    targetInput.style.fontSize = "11px";
    targetInput.style.padding = "8px";
    targetSection.appendChild(targetInput);
    container._icyRefs.targetInput = targetInput;

    const targetButtons = document.createElement("div");
    targetButtons.style.display = "flex";
    targetButtons.style.gap = "6px";

    const saveTargetsButton = createActionButton(
        "Save Classes",
        () => {
            updateTargetClassesFromRawValue(targetInput.value);
        },
        true
    );
    saveTargetsButton.style.flex = "1";

    const autoDetectButton = createActionButton("Auto Detect", () => {
        autoDetectTargetClassesFromGraph();
    });
    autoDetectButton.style.flex = "1";

    targetButtons.appendChild(saveTargetsButton);
    targetButtons.appendChild(autoDetectButton);
    targetSection.appendChild(targetButtons);

    const hiddenSection = createSidebarSection(container, "Hidden State Nodes");

    const selectedNodeIds = getSelectedNodeIds();
    if (selectedNodeIds.length > 0) {
        const addSelectedButton = createActionButton(
            `Add Selected (${selectedNodeIds.length})`,
            () => {
                addNodeIdsToHiddenState(selectedNodeIds);
            },
            true
        );
        hiddenSection.appendChild(addSelectedButton);
    }

    const hiddenIds = Array.from(settingsCache.hiddenNodeIds).sort((a, b) => a - b);
    if (!hiddenIds.length) {
        const emptyLabel = document.createElement("div");
        emptyLabel.textContent = "No node is currently forced into hidden state.";
        emptyLabel.style.fontSize = "11px";
        emptyLabel.style.color = SIDEBAR_THEME.muted;
        hiddenSection.appendChild(emptyLabel);
    } else {
        for (let i = 0; i < hiddenIds.length; i++) {
            const nodeId = hiddenIds[i];
            const row = document.createElement("div");
            row.style.display = "flex";
            row.style.alignItems = "center";
            row.style.justifyContent = "space-between";
            row.style.gap = "8px";
            row.style.padding = "6px 8px";
            row.style.borderRadius = "6px";
            row.style.background = SIDEBAR_THEME.bg;
            row.style.border = `1px solid ${SIDEBAR_THEME.border}`;

            const label = document.createElement("div");
            label.style.display = "flex";
            label.style.flexDirection = "column";

            const title = document.createElement("span");
            title.textContent = `Node #${nodeId}`;
            title.style.fontSize = "11px";
            title.style.color = SIDEBAR_THEME.text;

            const subtitle = document.createElement("span");
            subtitle.textContent = findNodeClassById(nodeId);
            subtitle.style.fontSize = "10px";
            subtitle.style.color = SIDEBAR_THEME.muted;

            label.appendChild(title);
            label.appendChild(subtitle);

            const removeButton = createActionButton("Remove", () => {
                removeNodeIdsFromHiddenState([nodeId]);
            });
            removeButton.style.padding = "5px 8px";
            removeButton.style.fontSize = "10px";

            row.appendChild(label);
            row.appendChild(removeButton);
            hiddenSection.appendChild(row);
        }

        const clearAllButton = createActionButton("Clear All Hidden State Nodes", () => {
            clearHiddenNodeIds();
        });
        hiddenSection.appendChild(clearAllButton);
    }

    const info = document.createElement("div");
    info.textContent =
        "Tip: Right-click any node and use IcyHider menu action to add/remove hidden state.";
    info.style.fontSize = "10px";
    info.style.color = SIDEBAR_THEME.muted;
    info.style.padding = "4px 4px 8px";
    container.appendChild(info);
}

function registerSidebarTab() {
    const tryRegister = () => {
        if (app && app.extensionManager && app.extensionManager.registerSidebarTab) {
            app.extensionManager.registerSidebarTab({
                id: SIDEBAR_TAB_ID,
                icon: "pi pi-eye-slash",
                title: "Icy Hider",
                tooltip: "Icy Hider Controls",
                type: "custom",
                render: (container) => {
                    sidebarContainer = container;
                    buildSidebarContent(container);
                },
                destroy: () => {
                    sidebarContainer = null;
                },
            });
        } else {
            setTimeout(tryRegister, 200);
        }
    };

    tryRegister();
}

function addIcyContextMenuOption(menuOptions, nodeInstance) {
    refreshSettingsCache();

    const nodeId = Number(nodeInstance && nodeInstance.id);
    if (!Number.isFinite(nodeId)) return menuOptions;

    let hasIcyOption = false;
    for (let i = 0; i < menuOptions.length; i++) {
        const option = menuOptions[i];
        if (
            option &&
            typeof option.content === "string" &&
            option.content.startsWith("IcyHider:")
        ) {
            hasIcyOption = true;
            break;
        }
    }

    if (hasIcyOption) {
        return menuOptions;
    }

    const isHiddenStateNode = settingsCache.hiddenNodeIds.has(nodeId);

    if (menuOptions.length && menuOptions[menuOptions.length - 1] !== null) {
        menuOptions.push(null);
    }

    menuOptions.push({
        content: isHiddenStateNode
            ? "IcyHider: Remove Node from Hidden State"
            : "IcyHider: Add Node to Hidden State",
        callback: () => {
            if (isHiddenStateNode) {
                removeNodeIdsFromHiddenState([nodeId]);
            } else {
                addNodeIdsToHiddenState([nodeId]);
            }
        },
    });

    return menuOptions;
}

function patchNodeTypeContextMenu(nodeType) {
    if (!nodeType || !nodeType.prototype || nodeType.prototype._icyHiderExtraMenuPatched) {
        return;
    }

    const originalGetExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
    nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
        if (originalGetExtraMenuOptions) {
            originalGetExtraMenuOptions.apply(this, arguments);
        }
        if (Array.isArray(options)) {
            addIcyContextMenuOption(options, this);
        }
    };

    nodeType.prototype._icyHiderExtraMenuPatched = true;
}

function patchNodeInstanceContextMenu(node) {
    if (!node || node._icyHiderInstanceMenuPatched) return;

    const originalFn = node.getExtraMenuOptions;
    node.getExtraMenuOptions = function (canvas, options) {
        if (originalFn) {
            originalFn.apply(this, arguments);
        }
        if (Array.isArray(options)) {
            addIcyContextMenuOption(options, this);
        }
    };

    node._icyHiderInstanceMenuPatched = true;
}

function installContextMenuHook() {
    if (contextMenuHookInstalled) return;

    const liteGraph =
        typeof globalThis !== "undefined" && globalThis.LiteGraph ? globalThis.LiteGraph : null;
    const nodeProto = liteGraph && liteGraph.LGraphNode ? liteGraph.LGraphNode.prototype : null;

    if (!nodeProto) {
        setTimeout(installContextMenuHook, 250);
        return;
    }

    if (nodeProto._icyHiderContextMenuPatched) {
        contextMenuHookInstalled = true;
        return;
    }

    const originalGetExtraMenuOptions = nodeProto.getExtraMenuOptions;

    nodeProto.getExtraMenuOptions = function (canvas, options) {
        refreshSettingsCache();

        let menuOptions = [];
        if (originalGetExtraMenuOptions) {
            const result = originalGetExtraMenuOptions.apply(this, arguments);
            if (Array.isArray(result)) {
                menuOptions = result;
            } else if (Array.isArray(options)) {
                menuOptions = options;
            }
        } else if (Array.isArray(options)) {
            menuOptions = options;
        }

        const nodeId = Number(this && this.id);
        if (!Number.isFinite(nodeId)) return menuOptions;

        const isHiddenStateNode = settingsCache.hiddenNodeIds.has(nodeId);

        if (menuOptions.length && menuOptions[menuOptions.length - 1] !== null) {
            menuOptions.push(null);
        }

        menuOptions.push({
            content: isHiddenStateNode
                ? "IcyHider: Remove Node from Hidden State"
                : "IcyHider: Add Node to Hidden State",
            callback: () => {
                if (isHiddenStateNode) {
                    removeNodeIdsFromHiddenState([nodeId]);
                } else {
                    addNodeIdsToHiddenState([nodeId]);
                }
            },
        });

        return menuOptions;
    };

    nodeProto._icyHiderContextMenuPatched = true;
    contextMenuHookInstalled = true;
}

app.registerExtension({
    name: EXTENSION_NAME,

    async beforeRegisterNodeDef(nodeType) {
        patchNodeTypeContextMenu(nodeType);
    },

    init() {
        registerSidebarTab();
    },

    settings: [
        {
            id: "IcyHider.Enabled",
            name: "Enable Preview Hiding",
            type: "boolean",
            defaultValue: true,
            tooltip: "When ON, selected target classes and hidden-state nodes stay hidden until hover or selection.",
            onChange: (newVal) => {
                applyEnabledSettingValue(newVal);
            },
        },
        {
            id: "IcyHider.TargetNodeClasses",
            name: "Target Node Classes",
            type: "text",
            defaultValue: DEFAULT_TARGET_CLASSES.join(", "),
            tooltip:
                "Comma-separated comfyClass names to hide, e.g. PreviewImage, LoadImage, SaveImage.",
            onChange: (newVal) => {
                applyTargetNodeClassesSettingValue(newVal);
            },
        },
        {
            id: "IcyHider.HideMode",
            name: "Hide Mode",
            type: "combo",
            defaultValue: "cover",
            options: ["cover", "blur"],
            tooltip: "Choose between cover overlay or blur effect.",
            onChange: (newVal) => {
                applyHideModeSettingValue(newVal);
            },
        },
        {
            id: "IcyHider.BlurAmount",
            name: "Blur Amount",
            type: "slider",
            defaultValue: 20,
            attrs: {
                min: 0,
                max: 50,
                step: 1,
            },
            tooltip: "Amount of blur to apply (0-50px). Only applies when Hide Mode is blur.",
            onChange: (newVal) => {
                applyBlurAmountSettingValue(newVal);
            },
        },
        {
            id: "IcyHider.RevealOnHover",
            name: "Reveal on Hover",
            type: "boolean",
            defaultValue: true,
            tooltip:
                "When ON, hovering a hidden node reveals its contents. Turn OFF to reveal only via selection.",
            onChange: (newVal) => {
                settingsCache.revealOnHover = Boolean(newVal);
                settingsCache.dirty = false;
                refreshAllNodes({ forceVisualUpdate: true, skipSettingsRefresh: true });
                requestSidebarRefresh();
            },
        },
        {
            id: "IcyHider.RevealDelay",
            name: "Reveal Delay (ms)",
            type: "slider",
            defaultValue: 200,
            attrs: {
                min: 0,
                max: 2000,
                step: 50,
            },
            tooltip:
                "How long the pointer must rest on a node before hover reveals it (0-2000ms). Prevents accidental reveals when brushing the mouse.",
            onChange: (newVal) => {
                const parsed = parseInt(newVal, 10);
                settingsCache.revealDelay = Number.isFinite(parsed)
                    ? Math.min(2000, Math.max(0, parsed))
                    : 200;
                settingsCache.dirty = false;
                requestSidebarValueRefresh();
            },
        },
        {
            id: "IcyHider.GradientStart",
            name: "Gradient Start Color",
            type: "color",
            defaultValue: "1E3C72",
            tooltip: "The starting color of the gradient background (cover mode only).",
            onChange: markDirtyAndRefresh,
        },
        {
            id: "IcyHider.GradientEnd",
            name: "Gradient End Color",
            type: "color",
            defaultValue: "2A5298",
            tooltip: "The ending color of the gradient background (cover mode only).",
            onChange: markDirtyAndRefresh,
        },
        {
            id: "IcyHider.BorderColor",
            name: "Border Color",
            type: "color",
            defaultValue: "A5DEE5",
            tooltip: "The color of the border around the cover (cover mode only).",
            onChange: markDirtyAndRefresh,
        },
        {
            id: "IcyHider.Icon",
            name: "Icon",
            type: "text",
            defaultValue: "❄️",
            tooltip: "The emoji or text icon to display (cover mode only).",
            onChange: markDirtyAndRefresh,
        },
        {
            id: "IcyHider.Text",
            name: "Text",
            type: "text",
            defaultValue: "FROZEN",
            tooltip: "The text to display below the icon (cover mode only).",
            onChange: markDirtyAndRefresh,
        },
        {
            id: "IcyHider.TextColor",
            name: "Text Color",
            type: "color",
            defaultValue: "E0F7FA",
            tooltip: "The color of the text and icon (cover mode only).",
            onChange: markDirtyAndRefresh,
        },
    ],

    async nodeCreated(node) {
        node.icy_is_hovered = false;
        node.icy_managed = false;
        node.icy_hidden = false;
        node.icy_has_dom_preview = false;

        refreshSettingsCache();
        updateNodeHidden(node, false, true);
        patchNodeInstanceContextMenu(node);

        const updateAndRedraw = () => {
            refreshSettingsCache();
            if (updateNodeHidden(node, false, true)) {
                node.setDirtyCanvas(true, true);
            }
        };

        const origOnSelected = node.onSelected;
        node.onSelected = function () {
            updateAndRedraw();
            if (origOnSelected) origOnSelected.apply(this, arguments);
        };

        const origOnDeselected = node.onDeselected;
        node.onDeselected = function () {
            updateAndRedraw();
            if (origOnDeselected) origOnDeselected.apply(this, arguments);
        };

        const origOnMouseEnter = node.onMouseEnter;
        node.onMouseEnter = function () {
            const self = this;
            scheduleHoverReveal(
                node.id,
                (h) => {
                    self.icy_is_hovered = h;
                },
                updateAndRedraw
            );
            if (origOnMouseEnter) origOnMouseEnter.apply(this, arguments);
        };

        const origOnMouseLeave = node.onMouseLeave;
        node.onMouseLeave = function () {
            // Leaving a node cancels any pending reveal immediately; never flash.
            clearHoverTimer(node.id);
            this.icy_is_hovered = false;
            updateAndRedraw();
            if (origOnMouseLeave) origOnMouseLeave.apply(this, arguments);
        };

        const origOnExecuted = node.onExecuted;
        node.onExecuted = function () {
            const result = origOnExecuted ? origOnExecuted.apply(this, arguments) : undefined;
            // Defer one frame so node.imgs/animatedImages are populated.
            setTimeout(updateAndRedraw, 0);
            return result;
        };

        const wrapDrawWidgets = () => {
            const currentFn = node.drawWidgets;
            if (currentFn && currentFn._icyWrapped) return;

            const wrappedFn = function (ctx) {
                syncHiddenState(this);

                if (!this.icy_managed || !this.icy_hidden) {
                    if (currentFn) currentFn.apply(this, arguments);
                    return;
                }

                if (settingsCache.hideMode === "blur") {
                    if (this.icy_has_dom_preview) {
                        if (currentFn) currentFn.apply(this, arguments);
                    } else {
                        drawBlurred(ctx, this, currentFn, arguments);
                    }
                }
            };

            wrappedFn._icyWrapped = true;
            wrappedFn._icyOriginal = currentFn;
            node.drawWidgets = wrappedFn;
        };

        const wrapDrawBackground = () => {
            const currentFn = node.onDrawBackground;
            if (currentFn && currentFn._icyWrapped) return;

            const wrappedFn = function (ctx) {
                syncHiddenState(this);

                if (
                    this.icy_managed &&
                    this.icy_hidden &&
                    settingsCache.hideMode === "blur" &&
                    !this.icy_has_dom_preview
                ) {
                    drawBlurred(ctx, this, currentFn, arguments);
                    return;
                }

                if (currentFn) currentFn.apply(this, arguments);
            };

            wrappedFn._icyWrapped = true;
            wrappedFn._icyOriginal = currentFn;
            node.onDrawBackground = wrappedFn;
        };

        const wrapDrawForeground = () => {
            const currentFn = node.onDrawForeground;
            if (currentFn && currentFn._icyWrapped) return;

            const wrappedFn = function (ctx) {
                syncHiddenState(this);

                if (
                    this.icy_managed &&
                    this.icy_hidden &&
                    settingsCache.hideMode === "blur" &&
                    !this.icy_has_dom_preview
                ) {
                    drawBlurred(ctx, this, currentFn, arguments);
                    return;
                }

                if (currentFn) currentFn.apply(this, arguments);

                if (this.icy_managed && this.icy_hidden && settingsCache.hideMode === "cover") {
                    drawCoverOverlay(ctx, this);
                }
            };

            wrappedFn._icyWrapped = true;
            wrappedFn._icyOriginal = currentFn;
            node.onDrawForeground = wrappedFn;
        };

        wrapDrawWidgets();
        wrapDrawBackground();
        wrapDrawForeground();

        // The three draw wrappers above are LiteGraph canvas paint hooks.  In
        // Vue/Nodes 2.0 mode LGraphCanvas.drawNode returns early and never
        // invokes them, so the deferred re-wrap is classic-only.
        if (!isVueNodesMode()) {
            setTimeout(() => {
                if (!node.drawWidgets || !node.drawWidgets._icyWrapped) {
                    wrapDrawWidgets();
                }
                if (!node.onDrawBackground || !node.onDrawBackground._icyWrapped) {
                    wrapDrawBackground();
                }
                if (!node.onDrawForeground || !node.onDrawForeground._icyWrapped) {
                    wrapDrawForeground();
                }
            }, 100);
        }
    },

    async setup() {
        refreshSettingsCache();
        persistNormalizedListSettings();

        const ensureDrawImagePatched = () => {
            if (patchCanvasDrawImage()) {
                app.graph?.setDirtyCanvas?.(true, true);
                return;
            }
            setTimeout(ensureDrawImagePatched, 200);
        };
        ensureDrawImagePatched();

        // Refresh hidden-node cache when a workflow is loaded or nodes are
        // removed/added so the sidebar stays consistent with the graph.
        const hookGraphLifecycle = () => {
            if (!app.graph) {
                setTimeout(hookGraphLifecycle, 200);
                return;
            }
            if (app.graph._icyHiderLifecycleHooked) return;

            const origOnConfigure = app.graph.onConfigure;
            app.graph.onConfigure = function () {
                const r = origOnConfigure ? origOnConfigure.apply(this, arguments) : undefined;
                setTimeout(() => {
                    refreshAllNodes({ forceVisualUpdate: true });
                    requestSidebarRefresh();
                }, 0);
                return r;
            };

            const origOnNodeRemoved = app.graph.onNodeRemoved;
            app.graph.onNodeRemoved = function () {
                const r = origOnNodeRemoved ? origOnNodeRemoved.apply(this, arguments) : undefined;
                rebuildHiddenNodeIdsFromGraph();
                requestSidebarRefresh();
                return r;
            };

            const origOnNodeAdded = app.graph.onNodeAdded;
            app.graph.onNodeAdded = function () {
                const r = origOnNodeAdded ? origOnNodeAdded.apply(this, arguments) : undefined;
                rebuildHiddenNodeIdsFromGraph();
                requestSidebarRefresh();
                return r;
            };

            app.graph._icyHiderLifecycleHooked = true;
        };
        hookGraphLifecycle();

        let domUpdateTimeout = null;
        const debouncedDOMUpdate = () => {
            if (domUpdateTimeout) return;

            domUpdateTimeout = setTimeout(() => {
                domUpdateTimeout = null;

                if (!app.graph || !app.graph._nodes) return;
                for (let i = 0; i < app.graph._nodes.length; i++) {
                    const node = app.graph._nodes[i];
                    const changed = updateNodeHidden(node, false, true);
                    if (changed || node.icy_managed) {
                        node.setDirtyCanvas?.(true, true);
                    }
                }
            }, 50);
        };

        const observer = new MutationObserver((mutations) => {
            let hasRelevantChanges = false;
            let hasVueNodeChange = false;

            for (let i = 0; i < mutations.length; i++) {
                const mutation = mutations[i];

                for (let j = 0; j < mutation.addedNodes.length; j++) {
                    const domNode = mutation.addedNodes[j];
                    if (domNode.nodeType !== 1) continue;

                    if (
                        domNode.tagName === "TEXTAREA" ||
                        domNode.tagName === "VIDEO" ||
                        domNode.tagName === "IMG" ||
                        domNode.tagName === "CANVAS"
                    ) {
                        hasRelevantChanges = true;
                    }

                    // Vue nodes: a new .lg-node, or media added inside one.
                    if (
                        domNode.classList?.contains("lg-node") ||
                        domNode.querySelector?.(".lg-node") ||
                        (domNode.parentElement?.classList?.contains("lg-node") &&
                            (domNode.tagName === "VIDEO" ||
                                domNode.tagName === "IMG" ||
                                domNode.tagName === "CANVAS"))
                    ) {
                        hasVueNodeChange = true;
                    }
                }

                // Attribute mutations on .lg-node (selection class toggles,
                // collapse, resize via style) also require a re-sync.
                if (!hasVueNodeChange && mutation.type === "attributes") {
                    const target = mutation.target;
                    if (target && target.classList?.contains("lg-node")) {
                        hasVueNodeChange = true;
                    }
                }

                if (hasRelevantChanges && hasVueNodeChange) break;
            }

            if (hasRelevantChanges) {
                debouncedDOMUpdate();
            }
            if (hasVueNodeChange && isVueNodesMode()) {
                scheduleVueSync();
            }
        });

        // Observe body so we catch Vue's node layer regardless of where it
        // mounts, plus the classic widget DOM inside .graphcanvas.
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ["class", "data-node-id", "data-collapsed", "style"],
        });

        const style = document.createElement("style");
        style.textContent = `
            .graphcanvas textarea,
            .graphcanvas video,
            .graphcanvas img,
            .graphcanvas canvas,
            .graphcanvas .comfy-multiline-input {
                transition: opacity 0.2s ease, filter 0.2s ease;
            }
        `;

        document.head.appendChild(style);

        setTimeout(() => {
            refreshAllNodes({ forceVisualUpdate: true });
            requestSidebarRefresh();
        }, 0);
    },
});
