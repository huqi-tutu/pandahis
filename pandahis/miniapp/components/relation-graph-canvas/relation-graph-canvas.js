"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const relation_mindmap_layout_1 = require("../../utils/relation-mindmap-layout");
const BG = '#F8F6F2';
const CENTER_FILL = '#B85C48';
const CENTER_STROKE = 'rgba(140, 72, 58, 0.72)';
const CENTER_TEXT = '#FAF8F5';
const CATEGORY_FILL = {
    家庭: 'rgba(250, 246, 242, 0.95)',
    同僚: 'rgba(248, 246, 244, 0.95)',
    敌对: 'rgba(250, 244, 244, 0.95)',
    师徒: 'rgba(246, 250, 248, 0.95)',
    好友: 'rgba(246, 248, 252, 0.95)',
};
const CATEGORY_STROKE = {
    家庭: 'rgba(162, 115, 79, 0.38)',
    同僚: 'rgba(127, 176, 105, 0.38)',
    敌对: 'rgba(180, 100, 100, 0.35)',
    师徒: 'rgba(99, 137, 156, 0.38)',
    好友: 'rgba(120, 140, 180, 0.38)',
};
const CATEGORY_TEXT = '#6C757D';
const LEAF_FILL = '#FAF8F5';
const LEAF_STROKE = 'rgba(162, 115, 79, 0.32)';
const LEAF_TEXT = '#343A40';
const REL_LABEL_FILL = 'rgba(108, 117, 125, 0.9)';
const REL_LABEL_TEXT = '#FAF8F5';
const GROUP_EDGE = {
    家庭: 'rgba(162, 115, 79, 0.45)',
    同僚: 'rgba(127, 176, 105, 0.45)',
    敌对: 'rgba(180, 100, 100, 0.42)',
    师徒: 'rgba(99, 137, 156, 0.45)',
    好友: 'rgba(120, 140, 180, 0.42)',
    other: 'rgba(120, 110, 105, 0.38)',
};
const NO_EDGE_LABEL_GROUPS = new Set(['同僚', '敌对', '师徒', '好友']);
const CENTER_R = 28;
const PERSON_R = 22;
const NODE_GAP = 10;
const CAT_FONT = 11;
const REL_LABEL_H = 13;
const REL_LABEL_FONT = 7;
function normalizeGroupName(raw) {
    const g = (raw || '').trim();
    if (g === '君臣')
        return '同僚';
    if (g === '师从')
        return '师徒';
    if (g === '外敌')
        return '敌对';
    return g;
}
function parseExtraGroup(extraJson) {
    if (!extraJson)
        return '';
    try {
        const o = JSON.parse(extraJson);
        if (o.isCategoryNode || o.isSubCategoryNode) {
            return normalizeGroupName(String(o.关系类别 || ''));
        }
        const raw = String(o.关系类别 || o.group || o.category || o.cat || '');
        const m = normalizeGroupName(raw).match(/家庭|同僚|敌对|师徒|好友/);
        return m ? m[0] : '';
    }
    catch {
        return '';
    }
}
function isSubCategoryNode(meta) {
    if (!meta)
        return false;
    if (meta.type === 'subcategory')
        return true;
    try {
        if (meta.extraJson) {
            const o = JSON.parse(meta.extraJson);
            if (o.isSubCategoryNode || o.节点类型 === '二级分类')
                return true;
        }
    }
    catch {
        /* ignore */
    }
    return false;
}
function isCategoryNode(meta) {
    if (!meta)
        return false;
    if (isSubCategoryNode(meta))
        return false;
    if (meta.type === 'category')
        return true;
    if (String(meta.key || '').startsWith('cat_'))
        return true;
    try {
        if (meta.extraJson) {
            const o = JSON.parse(meta.extraJson);
            if (o.isCategoryNode)
                return true;
        }
    }
    catch {
        /* ignore */
    }
    return false;
}
function isExpandNode(meta, name) {
    const n = (name || (meta === null || meta === void 0 ? void 0 : meta.name) || '').trim();
    return /展开全部|展开更多|\+(\d+)/.test(n) || (meta === null || meta === void 0 ? void 0 : meta.type) === 'expand';
}
function buildParentMap(centerKey, edges) {
    const parent = new Map();
    const adj = new Map();
    for (const e of edges || []) {
        if (!adj.has(e.fromKey))
            adj.set(e.fromKey, []);
        adj.get(e.fromKey).push(e.toKey);
    }
    const q = [centerKey];
    const seen = new Set([centerKey]);
    while (q.length) {
        const u = q.shift();
        for (const v of adj.get(u) || []) {
            if (seen.has(v))
                continue;
            seen.add(v);
            parent.set(v, u);
            q.push(v);
        }
    }
    return parent;
}
function nodeGroup(meta, fallback = 'other') {
    if (!meta)
        return fallback;
    if (isCategoryNode(meta))
        return normalizeGroupName(String(meta.name || '')) || fallback;
    return parseExtraGroup(meta.extraJson) || fallback;
}
function personFontSize(name) {
    const len = name.length;
    if (len <= 2)
        return 10;
    if (len <= 3)
        return 9;
    if (len <= 4)
        return 8;
    return 7;
}
function radialOf(x, y) {
    return Math.hypot(x, y);
}
function categoryBox(name, compact = false) {
    if (compact)
        return { w: Math.max(48, name.length * 10 + 18), h: 26 };
    return { w: Math.max(56, name.length * 12 + 24), h: 30 };
}
function truncateName(name, maxLen) {
    if (name.length <= maxLen)
        return name;
    return `${name.slice(0, Math.max(1, maxLen - 1))}…`;
}
function addPos(posMap, meta, x, y, depth, group, flags) {
    const fullName = ((meta.name != null && String(meta.name).trim()) || meta.key).trim();
    const isCenter = !!flags.isCenter;
    const isCategory = !!flags.isCategory;
    const isSubCategory = !!flags.isSubCategory;
    let circleR = 0;
    let boxW = 0;
    let boxH = 0;
    let fontSize = personFontSize(fullName);
    let displayName = fullName;
    if (isCenter) {
        circleR = CENTER_R;
        boxW = CENTER_R * 2;
        boxH = CENTER_R * 2;
        fontSize = 14;
    }
    else if (isCategory) {
        const box = categoryBox(fullName);
        boxW = box.w;
        boxH = box.h;
        fontSize = CAT_FONT;
    }
    else if (isSubCategory) {
        const box = categoryBox(fullName, true);
        boxW = box.w;
        boxH = box.h;
        fontSize = Math.max(9, CAT_FONT - 1);
    }
    else {
        circleR = PERSON_R;
        boxW = PERSON_R * 2;
        boxH = PERSON_R * 2;
        fontSize = personFontSize(fullName);
    }
    posMap.set(meta.key, {
        key: meta.key,
        x,
        y,
        fullName,
        displayName,
        fontSize,
        type: meta.type || 'person',
        depth,
        group,
        targetBoxId: meta.targetBoxId,
        isCategory,
        isSubCategory,
        isCenter,
        isExpandNode: !!flags.isExpand,
        isPerson: !isCenter && !isCategory && !isSubCategory,
        circleR,
        boxW,
        boxH,
        minR: isCenter ? 0 : Math.max(0, radialOf(x, y) - 4),
    });
}
function computeDepthMap(centerKey, edges) {
    const parent = buildParentMap(centerKey, edges);
    const depth = new Map();
    depth.set(centerKey, 0);
    for (const key of parent.keys()) {
        let d = 0;
        let cur = key;
        while (cur && cur !== centerKey) {
            d++;
            cur = parent.get(cur);
        }
        depth.set(key, d);
    }
    return depth;
}
function posFromNode(meta, x, y, depth, centerKey) {
    const posMap = new Map();
    const name = ((meta.name != null && String(meta.name).trim()) || meta.key).trim();
    addPos(posMap, meta, x, y, depth, nodeGroup(meta), {
        isCenter: meta.key === centerKey,
        isCategory: isCategoryNode(meta),
        isSubCategory: isSubCategoryNode(meta),
        isExpand: isExpandNode(meta, name),
    });
    return posMap.get(meta.key);
}
function layoutMindMap(nodes, edges, centerKey) {
    var _a;
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const centerMeta = nodeMap.get(centerKey);
    if (!centerMeta) {
        return { positions: [], edgeList: [], bounds: { minX: -1, minY: -1, maxX: 1, maxY: 1 }, centerKey };
    }
    const coordMap = (0, relation_mindmap_layout_1.computeMindmapPositions)(centerKey, nodes, edges);
    const depthMap = computeDepthMap(centerKey, edges);
    const positions = [];
    for (const n of nodes) {
        const pt = coordMap.get(n.key);
        if (!pt)
            continue;
        positions.push(posFromNode(n, pt.x, pt.y, (_a = depthMap.get(n.key)) !== null && _a !== void 0 ? _a : 0, centerKey));
    }
    const edgeList = buildEdgeList(positions, edges, nodeMap);
    enrichEdgesWithCurves(edgeList);
    placeEdgeLabelsOnLine(edgeList, positions);
    return { positions, edgeList, bounds: computeBounds(positions, edgeList), centerKey };
}
function nodeBounds(p) {
    const hw = (p.isCategory ? p.boxW : p.boxW) / 2 + 6;
    const hh = (p.isCategory ? p.boxH : p.boxH) / 2 + 6;
    return { l: p.x - hw, r: p.x + hw, t: p.y - hh, b: p.y + hh };
}
function labelBox(x, y, w, h) {
    return { l: x - w / 2, r: x + w / 2, t: y - h / 2, b: y + h / 2 };
}
function boxesOverlap(a, b) {
    return a.l < b.r && a.r > b.l && a.t < b.b && a.b > b.t;
}
function measureRelLabel(text) {
    const w = Math.max(22, text.length * 7 + 10);
    return { w, h: REL_LABEL_H };
}
/** 标签贴在线上；同父多条边按序号错开 t，避免「儿子」叠成一堆 */
function placeEdgeLabelsOnLine(edgeList, positions) {
    const placed = positions.map((p) => nodeBounds(p));
    const byKey = new Map(positions.map((p) => [p.key, p]));
    const labeled = edgeList.filter((e) => e.label);
    const groups = new Map();
    for (const e of labeled) {
        const g = e.fromKey;
        if (!groups.has(g))
            groups.set(g, []);
        groups.get(g).push(e);
    }
    for (const [, edges] of groups) {
        const from = byKey.get(edges[0].fromKey);
        const hideLabels = edges.length > 5;
        edges.sort((ea, eb) => {
            const ta = byKey.get(ea.toKey);
            const tb = byKey.get(eb.toKey);
            if (!from || !ta || !tb)
                return 0;
            return Math.atan2(ta.y - from.y, ta.x - from.x) - Math.atan2(tb.y - from.y, tb.x - from.x);
        });
        edges.forEach((e, idx) => {
            if (hideLabels) {
                e.label = '';
                e.labelW = 0;
                e.labelH = 0;
                return;
            }
            const { w, h } = measureRelLabel(e.label);
            e.labelW = w;
            e.labelH = h;
            const n = edges.length;
            const baseT = n === 1 ? 0.5 : 0.34 + (idx / Math.max(1, n - 1)) * 0.32;
            const tCandidates = [baseT, baseT - 0.06, baseT + 0.06, baseT - 0.12, baseT + 0.12, 0.5];
            let found = false;
            for (const t of tCandidates) {
                if (t < 0.22 || t > 0.78)
                    continue;
                const lane = n > 1 ? idx - (n - 1) / 2 : 0;
                const pt = pointOnEdge(e, t);
                const tg = tangentOnEdge(e, t);
                const lx = pt.x - tg.uy * lane * 9;
                const ly = pt.y + tg.ux * lane * 9;
                const box = labelBox(lx, ly, w + 2, h + 2);
                if (placed.some((b) => boxesOverlap(box, b)))
                    continue;
                e.labelX = lx;
                e.labelY = ly;
                placed.push(box);
                found = true;
                break;
            }
            if (!found) {
                const lane = n > 1 ? idx - (n - 1) / 2 : 0;
                const pt = pointOnEdge(e, baseT);
                const tg = tangentOnEdge(e, baseT);
                e.labelX = pt.x - tg.uy * lane * 9;
                e.labelY = pt.y + tg.ux * lane * 9;
                placed.push(labelBox(e.labelX, e.labelY, w + 2, h + 2));
            }
        });
    }
    for (const e of labeled) {
        if (e.labelW > 0)
            continue;
        const { w, h } = measureRelLabel(e.label);
        e.labelW = w;
        e.labelH = h;
        e.labelX = (e.x1 + e.x2) / 2;
        e.labelY = (e.y1 + e.y2) / 2;
    }
}
function quadPoint(x1, y1, cx, cy, x2, y2, t) {
    const u = 1 - t;
    return {
        x: u * u * x1 + 2 * u * t * cx + t * t * x2,
        y: u * u * y1 + 2 * u * t * cy + t * t * y2,
    };
}
function quadTangent(x1, y1, cx, cy, x2, y2, t) {
    const u = 1 - t;
    return {
        x: 2 * u * (cx - x1) + 2 * t * (x2 - cx),
        y: 2 * u * (cy - y1) + 2 * t * (y2 - cy),
    };
}
/** 借鉴 F6 processParallelEdges：同对节点多边错开；控制点向中心微弯成思维导图弧 */
function enrichEdgesWithCurves(edgeList) {
    const pairTotal = new Map();
    for (const e of edgeList) {
        const k = [e.fromKey, e.toKey].sort().join('|');
        pairTotal.set(k, (pairTotal.get(k) || 0) + 1);
    }
    const pairIdx = new Map();
    for (const e of edgeList) {
        const k = [e.fromKey, e.toKey].sort().join('|');
        const total = pairTotal.get(k) || 1;
        const idx = pairIdx.get(k) || 0;
        pairIdx.set(k, idx + 1);
        const lane = total === 1 ? 0 : (idx - (total - 1) / 2) * 16;
        const mx = (e.x1 + e.x2) / 2;
        const my = (e.y1 + e.y2) / 2;
        const bend = 0.2;
        let cx = mx * (1 - bend);
        let cy = my * (1 - bend);
        const dx = e.x2 - e.x1;
        const dy = e.y2 - e.y1;
        const len = Math.hypot(dx, dy) || 1;
        cx += (-dy / len) * lane;
        cy += (dx / len) * lane;
        e.cx = cx;
        e.cy = cy;
    }
}
/** 借鉴 F6 fitView：仅缩小不放大，主题仍居中 */
function fitZoomScale(w, h, bounds) {
    const bw = bounds.maxX - bounds.minX;
    const bh = bounds.maxY - bounds.minY;
    if (bw <= 0 || bh <= 0)
        return 1;
    const pad = 36;
    return Math.min(1, (w - pad * 2) / bw, (h - pad * 2) / bh);
}
function pointOnEdge(e, t) {
    return quadPoint(e.x1, e.y1, e.cx, e.cy, e.x2, e.y2, t);
}
function tangentOnEdge(e, t) {
    const tg = quadTangent(e.x1, e.y1, e.cx, e.cy, e.x2, e.y2, t);
    const len = Math.hypot(tg.x, tg.y) || 1;
    return { ux: tg.x / len, uy: tg.y / len };
}
function computeBounds(positions, edgeList) {
    let minX = -120;
    let minY = -120;
    let maxX = 120;
    let maxY = 120;
    for (const p of positions) {
        const hw = p.boxW / 2 + 10;
        const hh = p.boxH / 2 + 10;
        minX = Math.min(minX, p.x - hw);
        maxX = Math.max(maxX, p.x + hw);
        minY = Math.min(minY, p.y - hh);
        maxY = Math.max(maxY, p.y + hh);
    }
    for (const e of edgeList) {
        if (!e.label)
            continue;
        const box = labelBox(e.labelX, e.labelY, e.labelW, e.labelH);
        minX = Math.min(minX, box.l);
        maxX = Math.max(maxX, box.r);
        minY = Math.min(minY, box.t);
        maxY = Math.max(maxY, box.b);
    }
    const pad = 64;
    return { minX: minX - pad, minY: minY - pad, maxX: maxX + pad, maxY: maxY + pad };
}
function edgeLabelText(e, a, b) {
    if (a.isCenter && (b.isCategory || b.isSubCategory))
        return '';
    // 一级分类 → 二级枢纽：不显示边标题
    if (a.isCategory && b.isSubCategory)
        return '';
    // 同僚 / 敌对 / 师徒 / 好友：二级→人物（或好友一级→人物）不显示边标题
    if (NO_EDGE_LABEL_GROUPS.has(a.group || b.group)) {
        if (a.isSubCategory || a.isCategory)
            return '';
    }
    const labelRaw = (e.label || '').trim().slice(0, 8);
    if (!labelRaw)
        return '';
    if (b.fullName.includes(`(${labelRaw})`))
        return '';
    return labelRaw;
}
function nodeAnchor(from, to) {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len;
    const uy = dy / len;
    if (from.isCategory || from.isSubCategory || from.isCenter) {
        const hw = from.boxW / 2;
        const hh = from.boxH / 2;
        const ax = Math.abs(ux);
        const ay = Math.abs(uy);
        let t = Infinity;
        if (ax > 1e-6)
            t = Math.min(t, hw / ax);
        if (ay > 1e-6)
            t = Math.min(t, hh / ay);
        if (!Number.isFinite(t))
            t = Math.max(hw, hh);
        return { x: from.x + ux * t, y: from.y + uy * t };
    }
    const r = from.circleR + 2;
    return { x: from.x + ux * r, y: from.y + uy * r };
}
function buildEdgeList(positions, edges, nodeMap) {
    var _a, _b;
    const m = new Map(positions.map((p) => [p.key, p]));
    const out = [];
    for (const e of edges || []) {
        const a = m.get(e.fromKey);
        const b = m.get(e.toKey);
        if (!a || !b)
            continue;
        const group = parseExtraGroup((_a = nodeMap.get(e.toKey)) === null || _a === void 0 ? void 0 : _a.extraJson) ||
            parseExtraGroup((_b = nodeMap.get(e.fromKey)) === null || _b === void 0 ? void 0 : _b.extraJson) ||
            a.group ||
            b.group ||
            'other';
        const start = nodeAnchor(a, b);
        const end = nodeAnchor(b, a);
        const label = edgeLabelText(e, a, b);
        const { w, h } = label ? measureRelLabel(label) : { w: 0, h: 0 };
        out.push({
            fromKey: e.fromKey,
            toKey: e.toKey,
            x1: start.x,
            y1: start.y,
            x2: end.x,
            y2: end.y,
            cx: (start.x + end.x) / 2,
            cy: (start.y + end.y) / 2,
            color: GROUP_EDGE[group] || GROUP_EDGE.other,
            group,
            label,
            labelX: (start.x + end.x) / 2,
            labelY: (start.y + end.y) / 2,
            labelW: w,
            labelH: h,
        });
    }
    return out;
}
function pathEdgeKeys(targetKey, centerKey, parentMap) {
    const keys = new Set();
    let cur = targetKey;
    while (cur && cur !== centerKey) {
        const parent = parentMap.get(cur);
        if (!parent)
            break;
        keys.add(`${parent}|${cur}`);
        cur = parent;
    }
    return keys;
}
function pathNodeKeys(targetKey, centerKey, parentMap) {
    const keys = new Set([centerKey]);
    let cur = targetKey;
    const chain = [];
    while (cur && cur !== centerKey) {
        chain.push(cur);
        const parent = parentMap.get(cur);
        if (!parent)
            break;
        cur = parent;
    }
    for (let i = chain.length - 1; i >= 0; i--)
        keys.add(chain[i]);
    return keys;
}
function roundRectPath(ctx, x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.lineTo(x + w - rr, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
    ctx.lineTo(x + w, y + h - rr);
    ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
    ctx.lineTo(x + rr, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
    ctx.lineTo(x, y + rr);
    ctx.quadraticCurveTo(x, y, x + rr, y);
    ctx.closePath();
}
function drawRelLabelPill(ctx, text, x, y, w, h, dimmed) {
    if (!text)
        return;
    roundRectPath(ctx, x - w / 2, y - h / 2, w, h, 5);
    ctx.fillStyle = dimmed ? 'rgba(108,117,125,0.4)' : REL_LABEL_FILL;
    ctx.fill();
    ctx.fillStyle = dimmed ? 'rgba(250,248,245,0.55)' : REL_LABEL_TEXT;
    ctx.font = `${REL_LABEL_FONT}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x, y);
}
function drawCatRect(ctx, p, highlighted, dimmed) {
    ctx.save();
    ctx.globalAlpha = dimmed ? 0.38 : 1;
    const x = p.x - p.boxW / 2;
    const y = p.y - p.boxH / 2;
    roundRectPath(ctx, x, y, p.boxW, p.boxH, 8);
    ctx.fillStyle = CATEGORY_FILL[p.group] || 'rgba(248,246,242,0.95)';
    ctx.fill();
    ctx.strokeStyle = highlighted
        ? (GROUP_EDGE[p.group] || GROUP_EDGE.other).replace(/[\d.]+\)$/, '0.75)')
        : CATEGORY_STROKE[p.group] || 'rgba(162,115,79,0.28)';
    ctx.lineWidth = highlighted ? 1.5 : 1;
    ctx.stroke();
    ctx.fillStyle = CATEGORY_TEXT;
    ctx.font = `500 ${p.fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(p.fullName, p.x, p.y);
    ctx.restore();
}
Component({
    properties: {
        graph: {
            type: Object,
            value: null,
            observer: 'onGraphObserver',
        },
    },
    data: {
        hint: '',
        scaleLabel: '100%',
    },
    lifetimes: {
        attached() {
            this.scheduleDraw();
        },
    },
    methods: {
        onGraphObserver() {
            this.scheduleDraw();
        },
        scheduleDraw() {
            wx.nextTick(() => setTimeout(() => this.draw(), 48));
        },
        redraw() {
            this.draw();
        },
        formatScaleLabel(scale) {
            const pct = Math.round(scale * 100);
            return `${Math.max(25, Math.min(300, pct))}%`;
        },
        syncScaleLabel() {
            const scale = this._zoomScale || 1;
            const label = this.formatScaleLabel(scale);
            if (label !== this.data.scaleLabel)
                this.setData({ scaleLabel: label });
            this.triggerEvent('zoomChange', { scale });
        },
        zoomIn() {
            const cur = this._zoomScale || 1;
            this._zoomScale = Math.min(3, +(cur * 1.18).toFixed(4));
            this.syncScaleLabel();
            this.paintCached();
        },
        zoomOut() {
            const cur = this._zoomScale || 1;
            this._zoomScale = Math.max(0.25, +(cur / 1.18).toFixed(4));
            this.syncScaleLabel();
            this.paintCached();
        },
        resetZoom() {
            ;
            this._zoomScale = 1;
            this._selectedKey = '';
            this.centerView();
            this.syncScaleLabel();
            this.paintCached();
        },
        centerView() {
            // 布局原点即主题人物 (0,0)，视口 translate(w/2,h/2) 后 pan 归零即正中
            ;
            this._panX = 0;
            this._panY = 0;
        },
        getZoomScale() {
            return this._zoomScale || 1;
        },
        paintCached() {
            const layout = this._layout;
            const w = this._w;
            const h = this._h;
            const dpr = this._dpr || 1;
            let ctx = this._ctx;
            const canvas = this._canvas;
            if (!layout || !w || !h)
                return;
            if (!ctx && canvas) {
                ctx = canvas.getContext('2d');
                this._ctx = ctx;
            }
            if (!ctx)
                return;
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.scale(dpr, dpr);
            this.paint(ctx, w, h, layout);
        },
        draw() {
            const graph = this.properties.graph;
            const nodes = (graph === null || graph === void 0 ? void 0 : graph.nodes) || [];
            const edges = (graph === null || graph === void 0 ? void 0 : graph.edges) || [];
            if (!nodes.length) {
                this.setData({ hint: '暂无关系数据' });
                return;
            }
            this.setData({ hint: '' });
            const query = wx.createSelectorQuery().in(this);
            query
                .select('#relGraphCanvas')
                .fields({ node: true, size: true })
                .exec((res) => {
                var _a;
                const info = res && res[0];
                if (!info || !info.node)
                    return;
                const canvas = info.node;
                const w = info.width;
                const h = info.height;
                if (!w || !h)
                    return;
                const dpr = wx.getWindowInfo().pixelRatio || 1;
                this._w = w;
                this._h = h;
                this._dpr = dpr;
                canvas.width = w * dpr;
                canvas.height = h * dpr;
                const ctx = canvas.getContext('2d');
                this._ctx = ctx;
                this._canvas = canvas;
                ctx.setTransform(1, 0, 0, 1, 0, 0);
                ctx.scale(dpr, dpr);
                const centerKey = graph.centerNodeKey || ((_a = nodes[0]) === null || _a === void 0 ? void 0 : _a.key) || '';
                this._selectedKey = '';
                const layout = layoutMindMap(nodes, edges, centerKey);
                this._layout = layout;
                this._parentMap = buildParentMap(centerKey, edges);
                this._zoomScale = fitZoomScale(w, h, layout.bounds);
                this.centerView();
                this.syncScaleLabel();
                this.paint(ctx, w, h, layout);
                wx.createSelectorQuery()
                    .in(this)
                    .select('#relGraphCanvas')
                    .boundingClientRect((r) => {
                    ;
                    this._rect = r;
                })
                    .exec();
            });
        },
        paint(ctx, w, h, layout) {
            const s = this._zoomScale || 1;
            const panX = this._panX || 0;
            const panY = this._panY || 0;
            const selectedKey = this._selectedKey || '';
            const parentMap = this._parentMap || new Map();
            const highlightEdges = selectedKey
                ? pathEdgeKeys(selectedKey, layout.centerKey, parentMap)
                : new Set();
            const highlightNodes = selectedKey
                ? pathNodeKeys(selectedKey, layout.centerKey, parentMap)
                : new Set();
            ctx.save();
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = BG;
            ctx.fillRect(0, 0, w, h);
            ctx.translate(w / 2 + panX, h / 2 + panY);
            ctx.scale(s, s);
            for (const e of layout.edgeList) {
                const id = `${e.fromKey}|${e.toKey}`;
                const active = !selectedKey || highlightEdges.has(id);
                const highlighted = highlightEdges.has(id);
                ctx.beginPath();
                ctx.moveTo(e.x1, e.y1);
                ctx.quadraticCurveTo(e.cx, e.cy, e.x2, e.y2);
                ctx.strokeStyle = active ? e.color : 'rgba(180, 172, 165, 0.12)';
                ctx.globalAlpha = highlighted ? 1 : active ? 0.58 : 1;
                ctx.lineWidth = highlighted ? 1.5 : 1;
                ctx.setLineDash([4, 4]);
                ctx.lineCap = 'round';
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.globalAlpha = 1;
            }
            for (const p of layout.positions) {
                this.drawNode(ctx, p, highlightNodes.has(p.key), !!selectedKey);
            }
            for (const e of layout.edgeList) {
                const id = `${e.fromKey}|${e.toKey}`;
                const active = !selectedKey || highlightEdges.has(id);
                if (!e.label || !active)
                    continue;
                drawRelLabelPill(ctx, e.label, e.labelX, e.labelY, e.labelW, e.labelH, !!selectedKey && !highlightEdges.has(id));
            }
            ctx.restore();
        },
        drawNode(ctx, p, highlighted, hasSelection) {
            const dimmed = hasSelection && !highlighted;
            ctx.save();
            ctx.globalAlpha = dimmed ? 0.38 : 1;
            if (p.isCenter) {
                const s = p.boxW;
                roundRectPath(ctx, p.x - p.boxW / 2, p.y - p.boxH / 2, s, s, 8);
                ctx.fillStyle = CENTER_FILL;
                ctx.fill();
                ctx.strokeStyle = highlighted ? '#8C483A' : CENTER_STROKE;
                ctx.lineWidth = highlighted ? 2 : 1.5;
                ctx.stroke();
                ctx.fillStyle = CENTER_TEXT;
                ctx.font = `600 ${p.fontSize}px sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(p.fullName, p.x, p.y);
                ctx.restore();
                return;
            }
            if (p.isCategory || p.isSubCategory) {
                drawCatRect(ctx, p, highlighted, dimmed);
                ctx.restore();
                return;
            }
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.circleR, 0, Math.PI * 2);
            ctx.fillStyle = LEAF_FILL;
            ctx.fill();
            ctx.strokeStyle = highlighted
                ? (GROUP_EDGE[p.group] || GROUP_EDGE.other).replace(/[\d.]+\)$/, '0.85)')
                : LEAF_STROKE;
            ctx.lineWidth = highlighted ? 1.5 : 1;
            ctx.stroke();
            ctx.fillStyle = LEAF_TEXT;
            const text = p.fullName;
            let fs = p.fontSize;
            for (; fs >= 6; fs--) {
                ctx.font = `400 ${fs}px sans-serif`;
                if (ctx.measureText(text).width <= p.circleR * 1.7)
                    break;
            }
            let show = text;
            if (fs === 6 && ctx.measureText(show).width > p.circleR * 1.7) {
                show = truncateName(text, 4);
            }
            ctx.font = `400 ${fs}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(show, p.x, p.y);
            ctx.restore();
        },
        onZoomInTap() {
            this.zoomIn();
        },
        onZoomOutTap() {
            this.zoomOut();
        },
        touchDistance(touches) {
            if (touches.length < 2)
                return 0;
            return Math.hypot(touches[1].clientX - touches[0].clientX, touches[1].clientY - touches[0].clientY);
        },
        screenToLayout(x, y) {
            const w = this._w;
            const h = this._h;
            const s = this._zoomScale || 1;
            const panX = this._panX || 0;
            const panY = this._panY || 0;
            return { x: (x - w / 2 - panX) / s, y: (y - h / 2 - panY) / s };
        },
        hitTestNode(layout, lx, ly) {
            const ordered = [...layout.positions].sort((a, b) => {
                const pa = (a.isCenter ? 3 : 0) + (a.isCategory ? 2 : 0) + (a.isSubCategory ? 1 : 0);
                const pb = (b.isCenter ? 3 : 0) + (b.isCategory ? 2 : 0) + (b.isSubCategory ? 1 : 0);
                return pa - pb;
            });
            for (let i = ordered.length - 1; i >= 0; i--) {
                const p = ordered[i];
                if (p.isCategory || p.isSubCategory || p.isCenter) {
                    if (lx >= p.x - p.boxW / 2 - 4 &&
                        lx <= p.x + p.boxW / 2 + 4 &&
                        ly >= p.y - p.boxH / 2 - 4 &&
                        ly <= p.y + p.boxH / 2 + 4) {
                        return p;
                    }
                    continue;
                }
                if (Math.hypot(lx - p.x, ly - p.y) <= p.circleR + 6)
                    return p;
            }
            return null;
        },
        onTouchStart(e) {
            const layout = this._layout;
            if (!(layout === null || layout === void 0 ? void 0 : layout.positions.length))
                return;
            const touches = e.touches;
            if (touches.length >= 2) {
                ;
                this._touchMode = 'pinch';
                this._pinchStartDist = this.touchDistance(touches);
                this._pinchStartScale = this._zoomScale || 1;
                return;
            }
            const touch = touches[0];
            this._touchMode = 'pending';
            this._touchStartX = touch.clientX;
            this._touchStartY = touch.clientY;
            this._panStartX = this._panX || 0;
            this._panStartY = this._panY || 0;
        },
        onTouchMove(e) {
            const touches = e.touches;
            if (this._touchMode === 'pinch' && touches.length >= 2) {
                const startDist = this._pinchStartDist;
                const curDist = this.touchDistance(touches);
                if (startDist > 0 && curDist > 0) {
                    ;
                    this._zoomScale = Math.max(0.25, Math.min(3, (this._pinchStartScale || 1) * (curDist / startDist)));
                    this.syncScaleLabel();
                    this.paintCached();
                }
                return;
            }
            const touch = touches[0];
            if (!touch)
                return;
            const dx = touch.clientX - (this._touchStartX || 0);
            const dy = touch.clientY - (this._touchStartY || 0);
            if (this._touchMode === 'pending' && Math.hypot(dx, dy) > 8) {
                ;
                this._touchMode = 'pan';
            }
            if (this._touchMode !== 'pan')
                return;
            this._panX = (this._panStartX || 0) + dx;
            this._panY = (this._panStartY || 0) + dy;
            this.paintCached();
        },
        onTouchEnd(e) {
            var _a;
            if (this._touchMode === 'pinch') {
                if (e.touches.length >= 2)
                    return;
                this._touchMode = 'pending';
                this.syncScaleLabel();
                return;
            }
            if (this._touchMode === 'pan') {
                ;
                this._touchMode = 'pending';
                return;
            }
            const layout = this._layout;
            const rect = this._rect;
            const touch = (_a = e.changedTouches) === null || _a === void 0 ? void 0 : _a[0];
            if (!layout || !rect || !touch)
                return;
            const pt = this.screenToLayout(touch.clientX - rect.left, touch.clientY - rect.top);
            const hit = this.hitTestNode(layout, pt.x, pt.y);
            if (!hit || hit.isCategory || hit.isSubCategory) {
                if (this._selectedKey) {
                    ;
                    this._selectedKey = '';
                    this.paintCached();
                }
                return;
            }
            ;
            this._selectedKey = hit.key;
            this.paintCached();
            this.triggerEvent('nodeTap', { key: hit.key, targetBoxId: hit.targetBoxId, nodeType: hit.type });
        },
    },
});
