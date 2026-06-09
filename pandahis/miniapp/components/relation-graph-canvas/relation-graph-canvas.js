const BRANCH = ['#e0e5cc', '#f3dedb', '#e0e5cc', '#f3dedb'];
const CENTER_FILL = '#f3dedb';
const CENTER_STROKE = '#dec0bc';
const SECTOR_BASE = {
    家庭: -Math.PI / 2,
    师从: Math.PI,
    君臣: 0,
    敌对: Math.PI / 2,
};
function inferGroupFromLabel(label) {
    const l = label || '';
    if (/父|母|妻|子|女|配偶|家庭/.test(l))
        return '家庭';
    if (/师|医|道|问|徒/.test(l))
        return '师从';
    if (/臣|官|君臣|相|史|乐|牧/.test(l))
        return '君臣';
    if (/敌|战|逐|伐|对手|反|阪泉|涿鹿/.test(l))
        return '敌对';
    return 'other';
}
function parseExtraGroup(extraJson) {
    if (!extraJson)
        return '';
    try {
        const o = JSON.parse(extraJson);
        const raw = String(o.group || o.category || o.cat || '');
        const m = raw.match(/家庭|师从|君臣|敌对/);
        return m ? m[0] : '';
    }
    catch {
        return '';
    }
}
function assignNodeGroups(root, nodes, edges, depthMap) {
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const groupOf = new Map();
    groupOf.set(root, '');
    for (const n of nodes) {
        const g = parseExtraGroup(n.extraJson);
        if (g)
            groupOf.set(n.key, g);
    }
    for (const e of edges || []) {
        const label = e.label || '';
        if (e.fromKey === root && depthMap.get(e.toKey) === 1) {
            const g = groupOf.get(e.toKey) || inferGroupFromLabel(label);
            if (g !== 'other')
                groupOf.set(e.toKey, g);
        }
        else if (e.toKey === root && depthMap.get(e.fromKey) === 1) {
            const g = groupOf.get(e.fromKey) || inferGroupFromLabel(label);
            if (g !== 'other')
                groupOf.set(e.fromKey, g);
        }
    }
    for (let pass = 0; pass < 10; pass++) {
        for (const e of edges || []) {
            const a = e.fromKey;
            const b = e.toKey;
            const da = depthMap.get(a);
            const db = depthMap.get(b);
            if (da == null || db == null)
                continue;
            if (da < db && groupOf.get(a) && groupOf.get(a) !== 'other' && !groupOf.get(b)) {
                groupOf.set(b, groupOf.get(a));
            }
            else if (db < da && groupOf.get(b) && groupOf.get(b) !== 'other' && !groupOf.get(a)) {
                groupOf.set(a, groupOf.get(b));
            }
        }
    }
    for (const n of nodes) {
        if (!groupOf.get(n.key)) {
            const g = parseExtraGroup(n.extraJson) || 'other';
            groupOf.set(n.key, g);
        }
    }
    return groupOf;
}
function countNamedGroups(groupOf) {
    const s = new Set();
    for (const g of groupOf.values()) {
        if (g && g !== 'other')
            s.add(g);
    }
    return s.size;
}
function buildAdj(nodes, edges) {
    const adj = new Map();
    const add = (a, b) => {
        if (!a || !b)
            return;
        if (!adj.has(a))
            adj.set(a, new Set());
        if (!adj.has(b))
            adj.set(b, new Set());
        adj.get(a).add(b);
        adj.get(b).add(a);
    };
    for (const e of edges || [])
        add(e.fromKey, e.toKey);
    for (const n of nodes || []) {
        if (!adj.has(n.key))
            adj.set(n.key, new Set());
    }
    return adj;
}
function bfsDepth(root, adj) {
    var _a;
    const depth = new Map();
    const q = [];
    if (adj.has(root)) {
        depth.set(root, 0);
        q.push(root);
    }
    while (q.length) {
        const u = q.shift();
        const du = (_a = depth.get(u)) !== null && _a !== void 0 ? _a : 0;
        for (const v of adj.get(u) || []) {
            if (!depth.has(v)) {
                depth.set(v, du + 1);
                q.push(v);
            }
        }
    }
    return depth;
}
function findParentKey(key, edges, depthMap) {
    const d = depthMap.get(key);
    if (d == null || d <= 1)
        return '';
    for (const e of edges) {
        const other = e.fromKey === key ? e.toKey : e.toKey === key ? e.fromKey : '';
        if (!other)
            continue;
        const od = depthMap.get(other);
        if (od === d - 1)
            return other;
    }
    return '';
}
function hashCode(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++)
        h = (h << 5) - h + s.charCodeAt(i);
    return Math.abs(h);
}
function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
}
function shade(hex, amt) {
    const n = parseInt(hex.slice(1), 16);
    let r = (n >> 16) & 255;
    let g = (n >> 8) & 255;
    let b = n & 255;
    r = clamp(r + amt, 0, 255);
    g = clamp(g + amt, 0, 255);
    b = clamp(b + amt, 0, 255);
    return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}
function tint(hex, t) {
    const n = parseInt(hex.slice(1), 16);
    let r = (n >> 16) & 255;
    let g = (n >> 8) & 255;
    let b = n & 255;
    r = Math.round(r + (255 - r) * t);
    g = Math.round(g + (255 - g) * t);
    b = Math.round(b + (255 - b) * t);
    return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}
function rgbaFromHex(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    const r = (n >> 16) & 255;
    const g = (n >> 8) & 255;
    const b = n & 255;
    return `rgba(${r},${g},${b},${a})`;
}
function layoutRadial(nodes, edges, centerKey, w, h) {
    var _a;
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const adj = buildAdj(nodes, edges);
    let root = centerKey && nodeMap.has(centerKey) ? centerKey : ((_a = nodes[0]) === null || _a === void 0 ? void 0 : _a.key) || '';
    if (!root)
        return { positions: [], depthMap: new Map() };
    const depthMap = bfsDepth(root, adj);
    const byDepth = new Map();
    for (const n of nodes) {
        const d = depthMap.has(n.key) ? depthMap.get(n.key) : 99;
        if (!byDepth.has(d))
            byDepth.set(d, []);
        byDepth.get(d).push(n.key);
    }
    for (const arr of byDepth.values())
        arr.sort();
    const cx = w / 2;
    const cy = h / 2;
    const minDim = Math.min(w, h);
    const posMap = new Map();
    const depthRadius = (d) => {
        if (d <= 0)
            return 0;
        if (d >= 99)
            return minDim * 0.4;
        return minDim * (0.12 + d * 0.12);
    };
    const baseDist = (d) => {
        if (d <= 0)
            return 0;
        if (d >= 99)
            return depthRadius(99);
        return depthRadius(d) + 52;
    };
    const sortedDepths = [...byDepth.keys()].sort((a, b) => a - b);
    for (const d of sortedDepths) {
        const keys = byDepth.get(d) || [];
        const n = keys.length;
        keys.forEach((key, i) => {
            const meta = nodeMap.get(key);
            const fullName = ((meta.name != null && String(meta.name).trim()) || key).trim();
            const typ = meta.type || 'node';
            let x;
            let y;
            if (d === 0) {
                x = cx;
                y = cy;
            }
            else if (d >= 99) {
                const ang = -Math.PI / 2 + (i / Math.max(n, 1)) * Math.PI * 2;
                const dist = baseDist(99);
                x = cx + dist * Math.cos(ang);
                y = cy + dist * Math.sin(ang);
            }
            else {
                const angle = -Math.PI / 2 + (i / Math.max(n, 1)) * Math.PI * 2;
                const jitter = ((hashCode(key) % 13) - 6) * 0.016 * minDim;
                const dist = baseDist(d) + jitter;
                x = cx + dist * Math.cos(angle);
                y = cy + dist * Math.sin(angle);
            }
            x = clamp(x, 52, w - 52);
            y = clamp(y, 52, h - 52);
            let color = BRANCH[i % BRANCH.length];
            let stroke = color;
            if (d === 0) {
                color = CENTER_FILL;
                stroke = CENTER_STROKE;
            }
            else if (d === 1) {
                color = BRANCH[i % BRANCH.length];
                stroke = '#c4c9b1';
            }
            else {
                const pk = findParentKey(key, edges, depthMap);
                const parent = pk ? posMap.get(pk) : null;
                color = parent ? tint(parent.color, 0.12) : BRANCH[i % BRANCH.length];
                stroke = '#dec0bc';
            }
            const p = {
                key,
                x,
                y,
                r: 22,
                fullName,
                lines: [fullName],
                fontSize: 12,
                type: typ,
                depth: d,
                color,
                stroke,
                targetBoxId: meta.targetBoxId,
            };
            posMap.set(key, p);
        });
    }
    const positions = nodes.map((n) => posMap.get(n.key)).filter((p) => p != null) || [];
    return { positions, depthMap };
}
function layoutSectorGrouped(nodes, edges, centerKey, w, h) {
    var _a, _b;
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const adj = buildAdj(nodes, edges);
    let root = centerKey && nodeMap.has(centerKey) ? centerKey : ((_a = nodes[0]) === null || _a === void 0 ? void 0 : _a.key) || '';
    if (!root)
        return { positions: [], depthMap: new Map(), groupBoxes: [] };
    const depthMap = bfsDepth(root, adj);
    const groupOf = assignNodeGroups(root, nodes, edges, depthMap);
    const byDepth = new Map();
    for (const n of nodes) {
        const d = depthMap.has(n.key) ? depthMap.get(n.key) : 99;
        if (!byDepth.has(d))
            byDepth.set(d, []);
        byDepth.get(d).push(n.key);
    }
    for (const arr of byDepth.values())
        arr.sort();
    const cx = w / 2;
    const cy = h / 2;
    const minDim = Math.min(w, h);
    const posMap = new Map();
    const sectorDist = (d) => {
        if (d <= 0)
            return 0;
        return minDim * (0.1 + d * 0.11) + 48;
    };
    const rootMeta = nodeMap.get(root);
    posMap.set(root, {
        key: root,
        x: cx,
        y: cy,
        r: 22,
        fullName: ((rootMeta.name != null && String(rootMeta.name).trim()) || root).trim(),
        lines: [],
        fontSize: 14,
        type: rootMeta.type || 'event',
        depth: 0,
        color: CENTER_FILL,
        stroke: CENTER_STROKE,
        targetBoxId: rootMeta.targetBoxId,
    });
    const byGroup = new Map();
    for (const key of byDepth.get(1) || []) {
        const g = groupOf.get(key) || 'other';
        if (!byGroup.has(g))
            byGroup.set(g, []);
        byGroup.get(g).push(key);
    }
    const placeInSector = (keys, baseAngle, spread, dist) => {
        keys.forEach((key, i) => {
            const meta = nodeMap.get(key);
            const n = keys.length;
            const t = n <= 1 ? 0.5 : i / Math.max(n - 1, 1);
            const ang = baseAngle - spread / 2 + t * spread;
            const jitter = ((hashCode(key) % 9) - 4) * 0.008 * minDim;
            let x = cx + (dist + jitter) * Math.cos(ang);
            let y = cy + (dist + jitter) * Math.sin(ang);
            x = clamp(x, 52, w - 52);
            y = clamp(y, 52, h - 52);
            const fullName = ((meta.name != null && String(meta.name).trim()) || key).trim();
            posMap.set(key, {
                key,
                x,
                y,
                r: 22,
                fullName,
                lines: [fullName],
                fontSize: 11,
                type: meta.type || 'node',
                depth: 1,
                color: BRANCH[i % BRANCH.length],
                stroke: '#c4c9b1',
                targetBoxId: meta.targetBoxId,
            });
        });
    };
    const groupNames = ['家庭', '师从', '君臣', '敌对', 'other'];
    for (const g of groupNames) {
        const keys = byGroup.get(g) || [];
        if (!keys.length)
            continue;
        const base = (_b = SECTOR_BASE[g]) !== null && _b !== void 0 ? _b : -Math.PI / 2 + (groupNames.indexOf(g) / groupNames.length) * Math.PI * 2;
        const spread = g === 'other' ? Math.PI * 0.55 : Math.PI / 2.6;
        placeInSector(keys, base, spread, sectorDist(1));
    }
    for (let d = 2; d <= 6; d++) {
        const keys = byDepth.get(d) || [];
        keys.forEach((key, i) => {
            var _a;
            if (posMap.has(key))
                return;
            const meta = nodeMap.get(key);
            const pk = findParentKey(key, edges, depthMap);
            const parent = pk ? posMap.get(pk) : null;
            const dist = sectorDist(d);
            let x;
            let y;
            if (parent) {
                const pa = Math.atan2(parent.y - cy, parent.x - cx);
                const step = Math.max(56, dist - sectorDist(d - 1) * 0.55);
                x = parent.x + step * Math.cos(pa);
                y = parent.y + step * Math.sin(pa);
            }
            else {
                const g = groupOf.get(key) || 'other';
                const base = (_a = SECTOR_BASE[g]) !== null && _a !== void 0 ? _a : -Math.PI / 2;
                const spread = 0.35;
                const t = keys.length <= 1 ? 0.5 : i / Math.max(keys.length - 1, 1);
                const a = base - spread / 2 + t * spread;
                x = cx + dist * Math.cos(a);
                y = cy + dist * Math.sin(a);
            }
            x = clamp(x, 40, w - 40);
            y = clamp(y, 40, h - 40);
            const fullName = ((meta.name != null && String(meta.name).trim()) || key).trim();
            const color = parent ? tint(parent.color, 0.12) : BRANCH[i % BRANCH.length];
            posMap.set(key, {
                key,
                x,
                y,
                r: 20,
                fullName,
                lines: [fullName],
                fontSize: 11,
                type: meta.type || 'node',
                depth: d,
                color,
                stroke: '#dec0bc',
                targetBoxId: meta.targetBoxId,
            });
        });
    }
    for (const key of byDepth.get(99) || []) {
        if (posMap.has(key))
            continue;
        const meta = nodeMap.get(key);
        const fullName = ((meta.name != null && String(meta.name).trim()) || key).trim();
        posMap.set(key, {
            key,
            x: cx,
            y: cy + sectorDist(3),
            r: 20,
            fullName,
            lines: [fullName],
            fontSize: 11,
            type: meta.type || 'node',
            depth: 99,
            color: '#f3dedb',
            stroke: '#dec0bc',
            targetBoxId: meta.targetBoxId,
        });
    }
    const positions = nodes.map((n) => posMap.get(n.key)).filter((p) => p != null);
    const groupBoxes = [];
    for (const g of ['家庭', '师从', '君臣', '敌对']) {
        const keys = (byDepth.get(1) || []).filter((k) => groupOf.get(k) === g);
        if (!keys.length)
            continue;
        let minX = 1e9;
        let minY = 1e9;
        let maxX = -1e9;
        let maxY = -1e9;
        for (const k of keys) {
            const p = posMap.get(k);
            if (!p)
                continue;
            minX = Math.min(minX, p.x - p.r);
            minY = Math.min(minY, p.y - p.r);
            maxX = Math.max(maxX, p.x + p.r);
            maxY = Math.max(maxY, p.y + p.r);
        }
        const pad = 28;
        const bw = Math.max(60, maxX - minX + pad * 2);
        const bh = 24;
        const bx = (minX + maxX) / 2 - bw / 2;
        const by = minY - bh - 12;
        groupBoxes.push({ name: g, x: bx, y: by, w: bw, h: bh });
    }
    return { positions, depthMap, groupBoxes };
}
function applyFixedNodeSizes(positions, minDim) {
    const scale = minDim / 800;
    for (const p of positions) {
        if (p.depth === 0) {
            p.r = Math.max(36, 45 * scale);
            p.fontSize = 14;
        }
        else if (p.depth === 1) {
            p.r = Math.max(20, 24 * scale);
            p.fontSize = 11;
        }
        else {
            p.r = Math.max(16, 20 * scale);
            p.fontSize = 11;
        }
        p.lines = [p.fullName.length > 5 && p.r < 22 ? p.fullName.slice(0, 4) + '…' : p.fullName];
    }
}
function chooseLayout(nodes, edges, centerKey, w, h) {
    var _a;
    const adj = buildAdj(nodes, edges);
    const root = centerKey && nodes.some((n) => n.key === centerKey) ? centerKey : ((_a = nodes[0]) === null || _a === void 0 ? void 0 : _a.key) || '';
    const depthMap = root ? bfsDepth(root, adj) : new Map();
    const groupOf = assignNodeGroups(root, nodes, edges, depthMap);
    if (countNamedGroups(groupOf) >= 2) {
        return layoutSectorGrouped(nodes, edges, centerKey, w, h);
    }
    const { positions, depthMap: dm } = layoutRadial(nodes, edges, centerKey, w, h);
    return { positions, depthMap: dm, groupBoxes: [] };
}
/** 按最大宽度折行（适合中文），最后一行可截断加 … */
function wrapToWidth(ctx, text, maxW, maxLines) {
    const t = (text || '').trim() || '—';
    const out = [];
    let i = 0;
    while (i < t.length && out.length < maxLines) {
        let lo = i + 1;
        let hi = t.length;
        let best = i + 1;
        while (lo <= hi) {
            const mid = (lo + hi) >> 1;
            const seg = t.slice(i, mid);
            if (ctx.measureText(seg).width <= maxW) {
                best = mid;
                lo = mid + 1;
            }
            else {
                hi = mid - 1;
            }
        }
        if (best <= i)
            best = i + 1;
        if (out.length === maxLines - 1 && best < t.length) {
            let tail = t.slice(i);
            while (tail.length > 1 && ctx.measureText(`${tail}…`).width > maxW) {
                tail = tail.slice(0, -1);
            }
            out.push(`${tail}…`);
            break;
        }
        out.push(t.slice(i, best));
        i = best;
    }
    return out.length ? out : [t];
}
function sizeNodesForFullText(ctx, positions, minDim) {
    for (const p of positions) {
        const maxR = minDim * (p.depth === 0 ? 0.2 : p.depth === 1 ? 0.15 : p.depth >= 99 ? 0.13 : 0.12);
        const minR = minDim * (p.depth === 0 ? 0.048 : 0.036);
        const maxLines = p.depth === 0 ? 10 : 8;
        let bestFs = 11;
        let bestR = minR;
        let bestLines = [p.fullName];
        for (let fs = p.depth === 0 ? 17 : 14; fs >= 9; fs--) {
            ctx.font = `${fs}px sans-serif`;
            let lo = minR;
            let hi = maxR;
            for (let b = 0; b < 20; b++) {
                const mid = (lo + hi) / 2;
                const lines = wrapToWidth(ctx, p.fullName, mid * 1.72, maxLines);
                const tw = Math.max(6, ...lines.map((ln) => ctx.measureText(ln).width));
                const need = Math.max(tw / 2 + 10, (lines.length * fs * 1.38) / 2 + 8);
                if (need <= mid)
                    hi = mid;
                else
                    lo = mid;
            }
            const rTry = clamp(hi, minR, maxR);
            const lines = wrapToWidth(ctx, p.fullName, rTry * 1.72, maxLines);
            const tw = Math.max(6, ...lines.map((ln) => ctx.measureText(ln).width));
            const need = Math.max(tw / 2 + 10, (lines.length * fs * 1.38) / 2 + 8);
            if (need <= maxR * 1.04) {
                bestFs = fs;
                bestR = clamp(need, minR, maxR);
                bestLines = wrapToWidth(ctx, p.fullName, bestR * 1.72, maxLines);
                break;
            }
        }
        p.fontSize = bestFs;
        p.lines = bestLines;
        p.r = bestR;
    }
}
function radialReflow(positions, cx, cy, w, h, minDim) {
    const byDepthMaxR = new Map();
    for (const p of positions) {
        byDepthMaxR.set(p.depth, Math.max(byDepthMaxR.get(p.depth) || 0, p.r));
    }
    const depthRing = (d) => {
        if (d <= 0)
            return 0;
        if (d >= 99)
            return minDim * 0.38;
        return minDim * (0.11 + d * 0.11);
    };
    for (const p of positions) {
        if (p.depth === 0)
            continue;
        const ang = Math.atan2(p.y - cy, p.x - cx);
        const ring = depthRing(p.depth) + (byDepthMaxR.get(p.depth) || p.r) * 0.5 + p.r * 0.42;
        let x = cx + ring * Math.cos(ang);
        let y = cy + ring * Math.sin(ang);
        const m = p.r + 12;
        x = clamp(x, m, w - m);
        y = clamp(y, m, h - m);
        p.x = x;
        p.y = y;
    }
}
function buildEdgeList(positions, edges) {
    const m = new Map(positions.map((p) => [p.key, p]));
    const out = [];
    for (const e of edges || []) {
        const a = m.get(e.fromKey);
        const b = m.get(e.toKey);
        if (!a || !b)
            continue;
        out.push({
            x1: a.x,
            y1: a.y,
            x2: b.x,
            y2: b.y,
            label: (e.label || '关联').slice(0, 16),
            color: 'rgba(222, 192, 188, 0.92)',
        });
    }
    return out;
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
        zoomIn() {
            const cur = this._zoomScale || 1;
            this._zoomScale = Math.min(2.5, cur * 1.18);
            this.scheduleDraw();
            this.triggerEvent('zoomChange', { scale: this._zoomScale });
        },
        zoomOut() {
            const cur = this._zoomScale || 1;
            this._zoomScale = Math.max(0.52, cur / 1.18);
            this.scheduleDraw();
            this.triggerEvent('zoomChange', { scale: this._zoomScale });
        },
        resetZoom() {
            this._zoomScale = 1;
            this._panX = 0;
            this._panY = 0;
            this.scheduleDraw();
            this.triggerEvent('zoomChange', { scale: 1 });
        },
        getZoomScale() {
            return this._zoomScale || 1;
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
                ctx.setTransform(1, 0, 0, 1, 0, 0);
                ctx.scale(dpr, dpr);
                const centerKey = graph.centerNodeKey || ((_a = nodes[0]) === null || _a === void 0 ? void 0 : _a.key) || '';
                const { positions, groupBoxes } = chooseLayout(nodes, edges, centerKey, w, h);
                const minDim = Math.min(w, h);
                const useSector = groupBoxes.length > 0;
                if (useSector) {
                    applyFixedNodeSizes(positions, minDim);
                }
                else {
                    sizeNodesForFullText(ctx, positions, minDim);
                    radialReflow(positions, w / 2, h / 2, w, h, minDim);
                }
                const edgeList = buildEdgeList(positions, edges);
                const layout = { positions, edgeList, groupBoxes };
                this._layout = layout;
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
        drawGroupBoxes(ctx, boxes) {
            for (const b of boxes) {
                ctx.save();
                ctx.fillStyle = '#fff0ee';
                ctx.strokeStyle = '#dec0bc';
                ctx.lineWidth = 1;
                ctx.setLineDash([4, 4]);
                const r = 6;
                ctx.beginPath();
                ctx.moveTo(b.x + r, b.y);
                ctx.lineTo(b.x + b.w - r, b.y);
                ctx.quadraticCurveTo(b.x + b.w, b.y, b.x + b.w, b.y + r);
                ctx.lineTo(b.x + b.w, b.y + b.h - r);
                ctx.quadraticCurveTo(b.x + b.w, b.y + b.h, b.x + b.w - r, b.y + b.h);
                ctx.lineTo(b.x + r, b.y + b.h);
                ctx.quadraticCurveTo(b.x, b.y + b.h, b.x, b.y + b.h - r);
                ctx.lineTo(b.x, b.y + r);
                ctx.quadraticCurveTo(b.x, b.y, b.x + r, b.y);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.font = '9px sans-serif';
                ctx.fillStyle = '#8a716e';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(b.name, b.x + b.w / 2, b.y + b.h / 2);
                ctx.restore();
            }
        },
        paint(ctx, w, h, layout) {
            var _a;
            const s = this._zoomScale || 1;
            const panX = this._panX || 0;
            const panY = this._panY || 0;
            ctx.save();
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, w, h);
            ctx.translate(w / 2 + panX, h / 2 + panY);
            ctx.scale(s, s);
            ctx.translate(-w / 2, -h / 2);
            if ((_a = layout.groupBoxes) === null || _a === void 0 ? void 0 : _a.length) {
                this.drawGroupBoxes(ctx, layout.groupBoxes);
            }
            for (const e of layout.edgeList) {
                this.drawBezierEdge(ctx, e.x1, e.y1, e.x2, e.y2, e.color, e.label);
            }
            for (const p of layout.positions) {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = p.color;
                ctx.strokeStyle = p.stroke;
                ctx.lineWidth = p.depth === 0 ? 1.5 : 1;
                ctx.fill();
                ctx.stroke();
                ctx.fillStyle = '#262626';
                const fontWeight = p.depth === 0 ? '600' : '400';
                ctx.font = `${fontWeight} ${p.fontSize}px sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                const lh = p.fontSize * 1.36;
                const startY = p.y - ((p.lines.length - 1) * lh) / 2;
                p.lines.forEach((line, idx) => {
                    ctx.fillText(line, p.x, startY + idx * lh);
                });
            }
            ctx.restore();
        },
        drawBezierEdge(ctx, x1, y1, x2, y2, stroke, label) {
            const mx = (x1 + x2) / 2;
            const my = (y1 + y2) / 2;
            const dx = x2 - x1;
            const dy = y2 - y1;
            const len = Math.sqrt(dx * dx + dy * dy) || 1;
            const ox = (-dy / len) * Math.min(48, len * 0.22);
            const oy = (dx / len) * Math.min(48, len * 0.22);
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.bezierCurveTo(mx + ox, my + oy, mx - ox * 0.6, my - oy * 0.6, x2, y2);
            ctx.strokeStyle = stroke;
            ctx.lineWidth = 1;
            ctx.stroke();
            const lx = (x1 + x2) / 2 + ox * 0.35;
            const ly = (y1 + y2) / 2 + oy * 0.35;
            ctx.save();
            ctx.font = '10px sans-serif';
            ctx.fillStyle = '#8a716e';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(label, lx, ly - 8);
            ctx.restore();
        },
        onTouchStart(e) {
            const layout = this._layout;
            if (!layout || !layout.positions.length)
                return;
            const touch = e.changedTouches[0];
            this._touchMode = 'pending';
            this._touchStartX = touch.clientX;
            this._touchStartY = touch.clientY;
            this._panStartX = this._panX || 0;
            this._panStartY = this._panY || 0;
            const rect = this._rect;
            if (!rect || !rect.width) {
                wx.createSelectorQuery()
                    .in(this)
                    .select('#relGraphCanvas')
                    .boundingClientRect((r) => {
                    ;
                    this._rect = r;
                    this.hitTest(touch.clientX, touch.clientY, r, layout, true);
                })
                    .exec();
                return;
            }
            this.hitTest(touch.clientX, touch.clientY, rect, layout, true);
        },
        onTouchMove(e) {
            if (this._touchMode === 'tap')
                return;
            const touch = e.changedTouches[0];
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
            const layout = this._layout;
            const w = this._w;
            const h = this._h;
            if (!layout || !w || !h)
                return;
            const query = wx.createSelectorQuery().in(this);
            query
                .select('#relGraphCanvas')
                .fields({ node: true, size: true })
                .exec((res) => {
                const info = res && res[0];
                if (!(info === null || info === void 0 ? void 0 : info.node))
                    return;
                const canvas = info.node;
                const dpr = this._dpr || 1;
                const ctx = canvas.getContext('2d');
                ctx.setTransform(1, 0, 0, 1, 0, 0);
                ctx.scale(dpr, dpr);
                this.paint(ctx, w, h, layout);
            });
        },
        onTouchEnd(e) {
            if (this._touchMode === 'pan')
                return;
            const layout = this._layout;
            if (!layout || this._touchMode !== 'tap')
                return;
            const touch = e.changedTouches[0];
            const rect = this._rect;
            if (rect)
                this.hitTest(touch.clientX, touch.clientY, rect, layout, false);
        },
        hitTest(clientX, clientY, rect, layout, onStart) {
            const w = this._w;
            const h = this._h;
            const s = this._zoomScale || 1;
            const panX = this._panX || 0;
            const panY = this._panY || 0;
            let lx = ((clientX - rect.left) / rect.width) * w;
            let ly = ((clientY - rect.top) / rect.height) * h;
            const scale = s && Number.isFinite(s) ? s : 1;
            lx = (lx - w / 2 - panX) / scale + w / 2;
            ly = (ly - h / 2 - panY) / scale + h / 2;
            let best = null;
            let bestD = 1e9;
            for (const p of layout.positions) {
                const d = Math.hypot(p.x - lx, p.y - ly);
                if (d < p.r + 12 && d < bestD) {
                    bestD = d;
                    best = p;
                }
            }
            if (onStart) {
                ;
                this._touchMode = best ? 'tap' : 'pending';
                return;
            }
            if (best) {
                this.triggerEvent('nodeTap', { key: best.key, targetBoxId: best.targetBoxId });
            }
        },
    },
});
