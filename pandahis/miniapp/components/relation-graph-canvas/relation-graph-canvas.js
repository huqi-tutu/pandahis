const BRANCH = ['#EDEAE6', '#F5EAE4', '#EDEAE6', '#F5EAE4'];
const CENTER_FILL = '#F5EAE4';
const CENTER_STROKE = '#D4B098';
const CATEGORY_FILL = {
    家庭: 'rgba(250, 246, 242, 0.75)',
    同僚: 'rgba(248, 246, 244, 0.75)',
    师从: 'rgba(246, 250, 248, 0.75)',
    外敌: 'rgba(250, 244, 244, 0.75)',
};
const CATEGORY_STROKE = 'rgba(212, 176, 152, 0.38)';
const CATEGORY_TEXT = '#9A8A82';
const SECTOR_BASE = {
    家庭: -Math.PI / 2,
    师从: Math.PI,
    同僚: 0,
    外敌: Math.PI / 2,
};
function normalizeGroupName(raw) {
    const g = (raw || '').trim();
    if (g === '君臣')
        return '同僚';
    if (g === '敌对')
        return '外敌';
    return g;
}
function inferGroupFromLabel(label) {
    const l = label || '';
    if (/父|母|妻|子|女|配偶|家庭|兄|弟|姐|妹/.test(l))
        return '家庭';
    if (/师|医|道|问|徒|弟子/.test(l))
        return '师从';
    if (/臣|官|同僚|相|史|乐|牧|君王|政敌/.test(l))
        return '同僚';
    if (/敌|战|逐|伐|对手|反|阪泉|涿鹿|外敌/.test(l))
        return '外敌';
    return 'other';
}
function parseExtraGroup(extraJson) {
    if (!extraJson)
        return '';
    try {
        const o = JSON.parse(extraJson);
        if (o.isCategoryNode) {
            return normalizeGroupName(String(o.关系类别 || ''));
        }
        const raw = String(o.关系类别 || o.group || o.category || o.cat || '');
        const normalized = normalizeGroupName(raw);
        const m = normalized.match(/家庭|同僚|师从|外敌/);
        return m ? m[0] : '';
    }
    catch {
        return '';
    }
}
function isCategoryNode(meta) {
    if (!meta)
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
function assignNodeGroups(root, nodes, edges, depthMap) {
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const groupOf = new Map();
    groupOf.set(root, '');
    for (const n of nodes) {
        if (isCategoryNode(n)) {
            const g = normalizeGroupName(String(n.name || '')) || parseExtraGroup(n.extraJson);
            if (g)
                groupOf.set(n.key, g);
            continue;
        }
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
                stroke = '#92ADA4';
            }
            else {
                const pk = findParentKey(key, edges, depthMap);
                const parent = pk ? posMap.get(pk) : null;
                color = parent ? tint(parent.color, 0.12) : BRANCH[i % BRANCH.length];
                stroke = '#D4B098';
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
function estimatedCenterR(minDim) {
    const scale = minDim / 800;
    return Math.max(36, 45 * scale);
}
function estimatedCategoryHalfH(minDim) {
    const scale = minDim / 800;
    return Math.max(13, 16 * scale);
}
/** 中心 → 分类：给分类外圈扇形留出空间 */
function categoryRingDistance(minDim, fanLeaves = 1) {
    const base = estimatedCenterR(minDim) + estimatedCategoryHalfH(minDim) + 32;
    return base + Math.min(48, Math.max(0, fanLeaves - 1) * 10);
}
function edgeRadiusAlong(p, ux, uy) {
    if (p.isCategory && p.pillW) {
        const hw = p.pillW / 2;
        const hh = p.r;
        const ax = Math.abs(ux);
        const ay = Math.abs(uy);
        let best = Infinity;
        if (ax > 1e-6) {
            const t = hw / ax;
            if (ay * t <= hh + 0.5)
                best = Math.min(best, t);
        }
        if (ay > 1e-6) {
            const t = hh / ay;
            if (ax * t <= hw + 0.5)
                best = Math.min(best, t);
        }
        return Number.isFinite(best) ? best : Math.max(hw, hh);
    }
    const strokeHalf = p.depth === 0 ? 0.75 : 0.5;
    return p.r + strokeHalf;
}
function childrenOf(parentKey, edges) {
    return (edges || []).filter((e) => e.fromKey === parentKey).map((e) => e.toKey);
}
/** 子树叶子节点数（决定扇区占角） */
function countLeaves(key, edges, nodeMap) {
    const kids = childrenOf(key, edges).filter((k) => !isCategoryNode(nodeMap.get(k)));
    if (!kids.length)
        return 1;
    return kids.reduce((sum, k) => sum + countLeaves(k, edges, nodeMap), 0);
}
function parentExtentAlong(parent, ux, uy) {
    if (parent.isCategory && parent.pillW) {
        return edgeRadiusAlong(parent, ux, uy);
    }
    return parent.r;
}
/**
 * 参考样式：子节点绕父节点做外向弧形扇区排布（中心→分类→人物）。
 * 每个孩子落在以父为圆心、固定步长的圆弧上，角度按叶子权重分配且保证弦长间距。
 */
function layoutOrbitSubtree(parentKey, depth, posMap, nodeMap, edges, cx, cy) {
    const parent = posMap.get(parentKey);
    if (!parent)
        return;
    const kids = childrenOf(parentKey, edges).filter((k) => !isCategoryNode(nodeMap.get(k)));
    if (!kids.length)
        return;
    const outA = Math.atan2(parent.y - cy, parent.x - cx);
    const leafCounts = kids.map((k) => countLeaves(k, edges, nodeMap));
    const radii = kids.map((k) => { var _a, _b; return (_b = (_a = posMap.get(k)) === null || _a === void 0 ? void 0 : _a.r) !== null && _b !== void 0 ? _b : 18; });
    const maxChildR = Math.max(...radii, 18);
    const gap = parent.isCategory ? 38 : 34;
    const parentExt = parentExtentAlong(parent, Math.cos(outA), Math.sin(outA));
    const step = parentExt + maxChildR + gap;
    // 相邻孩子最小圆心距 → 最小夹角
    const minSep = maxChildR * 2 + 36;
    const minAngle = 2 * Math.asin(Math.min(0.92, minSep / (2 * Math.max(step, minSep))));
    const angleSpans = leafCounts.map((leaves) => Math.max(minAngle, leaves * minAngle * 0.9));
    const totalSpan = angleSpans.reduce((a, b) => a + b, 0);
    // 扇区以父节点外向角为中轴，略收拢避免跨入邻类
    const maxSpan = parent.isCategory ? Math.PI * 0.95 : Math.PI * 0.75;
    const scale = totalSpan > maxSpan ? maxSpan / totalSpan : 1;
    let cursor = outA - (totalSpan * scale) / 2;
    kids.forEach((childKey, i) => {
        var _a, _b, _c, _d;
        const meta = nodeMap.get(childKey);
        if (!meta)
            return;
        const span = angleSpans[i] * scale;
        const ang = cursor + span / 2;
        cursor += span;
        const childR = radii[i];
        const childStep = parentExtentAlong(parent, Math.cos(ang), Math.sin(ang)) + childR + gap;
        const x = parent.x + childStep * Math.cos(ang);
        const y = parent.y + childStep * Math.sin(ang);
        const existing = posMap.get(childKey);
        const fullName = ((meta.name != null && String(meta.name).trim()) || childKey).trim();
        posMap.set(childKey, {
            key: childKey,
            x,
            y,
            r: childR,
            fullName,
            lines: (_a = existing === null || existing === void 0 ? void 0 : existing.lines) !== null && _a !== void 0 ? _a : [fullName],
            fontSize: (_b = existing === null || existing === void 0 ? void 0 : existing.fontSize) !== null && _b !== void 0 ? _b : 11,
            type: meta.type || 'person',
            depth,
            color: (_c = existing === null || existing === void 0 ? void 0 : existing.color) !== null && _c !== void 0 ? _c : BRANCH[i % BRANCH.length],
            stroke: (_d = existing === null || existing === void 0 ? void 0 : existing.stroke) !== null && _d !== void 0 ? _d : '#D4B098',
            targetBoxId: meta.targetBoxId,
        });
        layoutOrbitSubtree(childKey, depth + 1, posMap, nodeMap, edges, cx, cy);
    });
}
/** 分离重叠：人物↔人物、人物↔分类 */
function separateOverlappingPersons(positions, centerKey, cx, cy) {
    const persons = positions.filter((p) => !p.isCategory && p.key !== centerKey);
    const obstacles = positions.filter((p) => p.isCategory || p.key === centerKey);
    for (let pass = 0; pass < 16; pass++) {
        let moved = false;
        for (let i = 0; i < persons.length; i++) {
            for (let j = i + 1; j < persons.length; j++) {
                const a = persons[i];
                const b = persons[j];
                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dist = Math.hypot(dx, dy);
                const minDist = a.r + b.r + 26;
                if (dist >= minDist)
                    continue;
                const push = dist < 1e-4 ? minDist / 2 : (minDist - dist) / 2 + 1;
                if (dist < 1e-4) {
                    const ang = Math.atan2(a.y - cy, a.x - cx) + Math.PI / 2;
                    a.x -= Math.cos(ang) * push;
                    a.y -= Math.sin(ang) * push;
                    b.x += Math.cos(ang) * push;
                    b.y += Math.sin(ang) * push;
                }
                else {
                    const ux = dx / dist;
                    const uy = dy / dist;
                    a.x -= ux * push;
                    a.y -= uy * push;
                    b.x += ux * push;
                    b.y += uy * push;
                }
                moved = true;
            }
        }
        for (const p of persons) {
            for (const obs of obstacles) {
                const dx = p.x - obs.x;
                const dy = p.y - obs.y;
                const dist = Math.hypot(dx, dy);
                const obsR = obs.isCategory && obs.pillW ? Math.max(obs.pillW / 2, obs.r) + 6 : obs.r + 8;
                const minDist = p.r + obsR + 18;
                if (dist >= minDist)
                    continue;
                const push = dist < 1e-4 ? minDist : minDist - dist + 1;
                if (dist < 1e-4) {
                    const ang = Math.atan2(obs.y - cy, obs.x - cx);
                    p.x = obs.x + Math.cos(ang) * minDist;
                    p.y = obs.y + Math.sin(ang) * minDist;
                }
                else {
                    p.x += (dx / dist) * push;
                    p.y += (dy / dist) * push;
                }
                moved = true;
            }
        }
        if (!moved)
            break;
    }
}
/** 节点定尺寸后，按真实半径重新绕分类弧形排布 */
function reflowCompactCategoryTree(positions, nodes, edges, centerKey, w, h, minDim) {
    var _a;
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const posMap = new Map(positions.map((p) => [p.key, p]));
    const center = posMap.get(centerKey);
    if (!center)
        return;
    const cx = w / 2;
    const cy = h / 2;
    for (const p of positions) {
        if (!p.isCategory)
            continue;
        const g = normalizeGroupName(p.fullName);
        const ang = (_a = SECTOR_BASE[g]) !== null && _a !== void 0 ? _a : Math.atan2(p.y - cy, p.x - cx);
        const leaves = countLeaves(p.key, edges, nodeMap);
        const ring = categoryRingDistance(minDim, leaves);
        p.x = cx + ring * Math.cos(ang);
        p.y = cy + ring * Math.sin(ang);
    }
    for (const p of positions) {
        if (p.isCategory || p.key === centerKey)
            continue;
        posMap.delete(p.key);
    }
    for (const p of positions) {
        if (!p.isCategory)
            continue;
        layoutOrbitSubtree(p.key, 2, posMap, nodeMap, edges, cx, cy);
    }
    for (const p of positions) {
        if (p.isCategory || p.key === centerKey)
            continue;
        const u = posMap.get(p.key);
        if (!u)
            continue;
        p.x = u.x;
        p.y = u.y;
    }
    separateOverlappingPersons(positions, centerKey, cx, cy);
}
function labelBoxHitsNode(lx, ly, hw, hh, nodes) {
    for (const n of nodes) {
        const nr = n.isCategory && n.pillW ? Math.max(n.pillW / 2, n.r) : n.r;
        const dx = Math.abs(lx - n.x);
        const dy = Math.abs(ly - n.y);
        // 余量收紧：允许标签贴线，只避开圆内文字区
        if (dx < hw + nr + 3 && dy < hh + nr + 3)
            return true;
    }
    return false;
}
function labelBoxHitsLabel(lx, ly, hw, hh, others) {
    for (const o of others) {
        if (Math.abs(lx - o.x) < hw + o.hw + 3 && Math.abs(ly - o.y) < hh + o.hh + 3)
            return true;
    }
    return false;
}
function layoutEdgeLabels(ctx, edgeList, positions) {
    ctx.font = '8px sans-serif';
    const nodes = positions;
    const placed = [];
    const labelH = 5;
    // 同文案交替左右，但优先小偏移贴线
    const labelSide = new Map();
    for (const e of edgeList) {
        if (!e.label)
            continue;
        const dx = e.x2 - e.x1;
        const dy = e.y2 - e.y1;
        const len = e.len || Math.hypot(dx, dy) || 1;
        if (len < 26) {
            e.label = '';
            continue;
        }
        const ux = dx / len;
        const uy = dy / len;
        const perpX = -uy;
        const perpY = ux;
        const tw = ctx.measureText(e.label).width;
        const hw = tw / 2 + 2;
        const side = labelSide.get(e.label) || 1;
        labelSide.set(e.label, -side);
        // 先贴线中段，偏移从小到大；归属优先于避让
        const alongTs = [0.5, 0.45, 0.55, 0.4, 0.6];
        const offsets = [7, 9, 11, 13, 16, 20, 24].flatMap((v) => [v * side, -v * side]);
        let found = false;
        for (const t of alongTs) {
            for (const off of offsets) {
                const lx = e.x1 + ux * len * t + perpX * off;
                const ly = e.y1 + uy * len * t + perpY * off;
                if (labelBoxHitsNode(lx, ly, hw, labelH, nodes))
                    continue;
                if (labelBoxHitsLabel(lx, ly, hw, labelH, placed))
                    continue;
                e.labelX = lx;
                e.labelY = ly;
                placed.push({ x: lx, y: ly, hw, hh: labelH });
                found = true;
                break;
            }
            if (found)
                break;
        }
        if (!found) {
            // 贴线兜底：中点旁 8px，保证仍能看出归属哪条边
            e.labelX = e.x1 + ux * len * 0.5 + perpX * 8 * side;
            e.labelY = e.y1 + uy * len * 0.5 + perpY * 8 * side;
            placed.push({ x: e.labelX, y: e.labelY, hw, hh: labelH });
        }
    }
}
function layoutCategoryTree(nodes, edges, centerKey, w, h) {
    var _a;
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const cx = w / 2;
    const cy = h / 2;
    const minDim = Math.min(w, h);
    const posMap = new Map();
    const depthMap = bfsDepth(centerKey, buildAdj(nodes, edges));
    const rootMeta = nodeMap.get(centerKey);
    if (!rootMeta)
        return { positions: [], depthMap, groupBoxes: [], useSectorLayout: true };
    posMap.set(centerKey, {
        key: centerKey,
        x: cx,
        y: cy,
        r: 22,
        fullName: ((rootMeta.name != null && String(rootMeta.name).trim()) || centerKey).trim(),
        lines: [],
        fontSize: 14,
        type: rootMeta.type || 'event',
        depth: 0,
        color: CENTER_FILL,
        stroke: CENTER_STROKE,
        targetBoxId: rootMeta.targetBoxId,
    });
    const categoryNodes = nodes.filter((n) => isCategoryNode(n));
    for (const meta of categoryNodes) {
        const g = normalizeGroupName(String(meta.name || ''));
        const ang = (_a = SECTOR_BASE[g]) !== null && _a !== void 0 ? _a : -Math.PI / 2;
        const fullName = ((meta.name != null && String(meta.name).trim()) || meta.key).trim();
        const leaves = countLeaves(meta.key, edges, nodeMap);
        const catRing = categoryRingDistance(minDim, leaves);
        posMap.set(meta.key, {
            key: meta.key,
            x: cx + catRing * Math.cos(ang),
            y: cy + catRing * Math.sin(ang),
            r: 16,
            fullName,
            lines: [fullName],
            fontSize: 12,
            type: 'category',
            depth: 1,
            color: CATEGORY_FILL[g] || '#EDEAE6',
            stroke: CATEGORY_STROKE,
            targetBoxId: meta.targetBoxId,
            isCategory: true,
            pillW: Math.max(58, fullName.length * 14 + 24),
        });
    }
    for (const meta of categoryNodes) {
        layoutOrbitSubtree(meta.key, 2, posMap, nodeMap, edges, cx, cy);
    }
    const positions = nodes.map((n) => posMap.get(n.key)).filter((p) => p != null);
    return { positions, depthMap, groupBoxes: [], useSectorLayout: true };
}
function layoutSectorGrouped(nodes, edges, centerKey, w, h) {
    var _a, _b;
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const adj = buildAdj(nodes, edges);
    let root = centerKey && nodeMap.has(centerKey) ? centerKey : ((_a = nodes[0]) === null || _a === void 0 ? void 0 : _a.key) || '';
    if (!root)
        return { positions: [], depthMap: new Map(), groupBoxes: [], useSectorLayout: false };
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
        const meta = nodeMap.get(key);
        const g = isCategoryNode(meta)
            ? normalizeGroupName(String((meta === null || meta === void 0 ? void 0 : meta.name) || '')) || groupOf.get(key) || 'other'
            : groupOf.get(key) || 'other';
        if (!byGroup.has(g))
            byGroup.set(g, []);
        byGroup.get(g).push(key);
    }
    const hasCategoryNodes = (byDepth.get(1) || []).some((k) => isCategoryNode(nodeMap.get(k)));
    const placeInSector = (keys, baseAngle, spread, dist) => {
        keys.forEach((key, i) => {
            const meta = nodeMap.get(key);
            const cat = isCategoryNode(meta);
            const n = keys.length;
            const t = n <= 1 ? 0.5 : i / Math.max(n - 1, 1);
            const ang = baseAngle - spread / 2 + t * spread;
            const jitter = cat ? 0 : ((hashCode(key) % 9) - 4) * 0.008 * minDim;
            let x = cx + (dist + jitter) * Math.cos(ang);
            let y = cy + (dist + jitter) * Math.sin(ang);
            x = clamp(x, 52, w - 52);
            y = clamp(y, 52, h - 52);
            const fullName = ((meta.name != null && String(meta.name).trim()) || key).trim();
            const groupName = normalizeGroupName(fullName) || groupOf.get(key) || 'other';
            posMap.set(key, {
                key,
                x,
                y,
                r: cat ? 16 : 22,
                fullName,
                lines: [fullName],
                fontSize: cat ? 12 : 11,
                type: meta.type || 'node',
                depth: 1,
                color: cat ? CATEGORY_FILL[groupName] || '#EDEAE6' : BRANCH[i % BRANCH.length],
                stroke: cat ? CATEGORY_STROKE : '#92ADA4',
                targetBoxId: meta.targetBoxId,
                isCategory: cat,
                pillW: cat ? Math.max(58, fullName.length * 14 + 24) : undefined,
            });
        });
    };
    const groupNames = ['家庭', '师从', '同僚', '外敌', 'other'];
    for (const g of groupNames) {
        const keys = byGroup.get(g) || [];
        if (!keys.length)
            continue;
        const base = (_b = SECTOR_BASE[g]) !== null && _b !== void 0 ? _b : -Math.PI / 2 + (groupNames.indexOf(g) / groupNames.length) * Math.PI * 2;
        const spread = hasCategoryNodes && keys.length === 1 ? 0 : g === 'other' ? Math.PI * 0.55 : Math.PI / 2.6;
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
                stroke: '#D4B098',
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
            color: '#F5EAE4',
            stroke: '#D4B098',
            targetBoxId: meta.targetBoxId,
        });
    }
    const positions = nodes.map((n) => posMap.get(n.key)).filter((p) => p != null);
    const groupBoxes = [];
    if (!hasCategoryNodes) {
        for (const g of ['家庭', '师从', '同僚', '外敌']) {
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
    }
    return { positions, depthMap, groupBoxes, useSectorLayout: true };
}
function applyFixedNodeSizes(positions, minDim) {
    const scale = minDim / 800;
    for (const p of positions) {
        if (p.depth === 0) {
            p.r = Math.max(36, 45 * scale);
            p.fontSize = 14;
        }
        else if (p.isCategory) {
            p.r = Math.max(13, 15 * scale);
            p.fontSize = 11;
            p.pillW = Math.max(52, p.fullName.length * 13 + 20);
        }
        else if (p.depth === 1) {
            p.r = Math.max(20, 24 * scale);
            p.fontSize = 11;
        }
        else {
            p.r = Math.max(16, 20 * scale);
            p.fontSize = 11;
        }
        if (!p.isCategory) {
            p.lines = [p.fullName.length > 5 && p.r < 22 ? p.fullName.slice(0, 4) + '…' : p.fullName];
        }
    }
}
function chooseLayout(nodes, edges, centerKey, w, h) {
    var _a;
    const hasCategoryNodes = nodes.some((n) => isCategoryNode(n));
    if (hasCategoryNodes) {
        return layoutCategoryTree(nodes, edges, centerKey, w, h);
    }
    const adj = buildAdj(nodes, edges);
    const root = centerKey && nodes.some((n) => n.key === centerKey) ? centerKey : ((_a = nodes[0]) === null || _a === void 0 ? void 0 : _a.key) || '';
    const depthMap = root ? bfsDepth(root, adj) : new Map();
    const groupOf = assignNodeGroups(root, nodes, edges, depthMap);
    if (countNamedGroups(groupOf) >= 2) {
        return layoutSectorGrouped(nodes, edges, centerKey, w, h);
    }
    const { positions, depthMap: dm } = layoutRadial(nodes, edges, centerKey, w, h);
    return { positions, depthMap: dm, groupBoxes: [], useSectorLayout: false };
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
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len;
        const uy = dy / len;
        const ra = edgeRadiusAlong(a, ux, uy);
        const rb = edgeRadiusAlong(b, -ux, -uy);
        const isCenterToCat = a.depth === 0 && b.isCategory;
        out.push({
            x1: a.x + ux * ra,
            y1: a.y + uy * ra,
            x2: b.x - ux * rb,
            y2: b.y - uy * rb,
            label: isCenterToCat ? '' : (e.label || '关联').slice(0, 16),
            color: isCenterToCat ? 'rgba(180, 160, 150, 0.75)' : 'rgba(190, 170, 160, 0.8)',
            len: Math.hypot(b.x - ux * rb - (a.x + ux * ra), b.y - uy * rb - (a.y + uy * ra)),
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
            this._zoomScale = Math.min(2.5, +(cur * 1.18).toFixed(4));
            this.paintCached();
            // 缩放过程不向页面抛事件，避免父页 setData 清掉 canvas 造成跳动
        },
        zoomOut() {
            const cur = this._zoomScale || 1;
            this._zoomScale = Math.max(0.52, +(cur / 1.18).toFixed(4));
            this.paintCached();
        },
        resetZoom() {
            ;
            this._zoomScale = 1;
            this._panX = 0;
            this._panY = 0;
            this.paintCached();
        },
        getZoomScale() {
            return this._zoomScale || 1;
        },
        /**
         * 仅重绘变换：不改布局、不 setData、不改 canvas.width（改 width 会清屏闪烁）。
         */
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
                const hasCategoryNodes = nodes.some((n) => isCategoryNode(n));
                const { positions, groupBoxes, useSectorLayout } = chooseLayout(nodes, edges, centerKey, w, h);
                const minDim = Math.min(w, h);
                if (useSectorLayout) {
                    applyFixedNodeSizes(positions, minDim);
                    if (hasCategoryNodes) {
                        reflowCompactCategoryTree(positions, nodes, edges, centerKey, w, h, minDim);
                    }
                }
                else {
                    sizeNodesForFullText(ctx, positions, minDim);
                    radialReflow(positions, w / 2, h / 2, w, h, minDim);
                }
                const edgeList = buildEdgeList(positions, edges);
                layoutEdgeLabels(ctx, edgeList, positions);
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
                ctx.fillStyle = '#F8F6F2';
                ctx.strokeStyle = '#EDEAE6';
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
                ctx.fillStyle = '#8A8A8A';
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
            // 保持浅色底（白/米色），不跟参考图黑底
            ctx.fillStyle = '#F8F6F2';
            ctx.fillRect(0, 0, w, h);
            // 以画布视口正中心为锚点缩放：先移到中心 → scale → 移回
            ctx.translate(w / 2, h / 2);
            ctx.translate(panX, panY);
            ctx.scale(s, s);
            ctx.translate(-w / 2, -h / 2);
            if ((_a = layout.groupBoxes) === null || _a === void 0 ? void 0 : _a.length) {
                this.drawGroupBoxes(ctx, layout.groupBoxes);
            }
            for (const e of layout.edgeList) {
                this.drawBezierEdge(ctx, e);
            }
            for (const p of layout.positions) {
                if (p.isCategory && p.pillW) {
                    const hw = p.pillW / 2;
                    const hh = p.r;
                    const rx = 6;
                    ctx.beginPath();
                    ctx.moveTo(p.x - hw + rx, p.y - hh);
                    ctx.lineTo(p.x + hw - rx, p.y - hh);
                    ctx.quadraticCurveTo(p.x + hw, p.y - hh, p.x + hw, p.y - hh + rx);
                    ctx.lineTo(p.x + hw, p.y + hh - rx);
                    ctx.quadraticCurveTo(p.x + hw, p.y + hh, p.x + hw - rx, p.y + hh);
                    ctx.lineTo(p.x - hw + rx, p.y + hh);
                    ctx.quadraticCurveTo(p.x - hw, p.y + hh, p.x - hw, p.y + hh - rx);
                    ctx.lineTo(p.x - hw, p.y - hh + rx);
                    ctx.quadraticCurveTo(p.x - hw, p.y - hh, p.x - hw + rx, p.y - hh);
                    ctx.closePath();
                    ctx.fillStyle = p.color;
                    ctx.strokeStyle = p.stroke;
                    ctx.lineWidth = 1;
                    ctx.setLineDash([4, 3]);
                    ctx.fill();
                    ctx.stroke();
                    ctx.setLineDash([]);
                }
                else {
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                    ctx.fillStyle = p.color;
                    ctx.strokeStyle = p.stroke;
                    ctx.lineWidth = p.depth === 0 ? 1.5 : 1;
                    ctx.fill();
                    ctx.stroke();
                }
                ctx.fillStyle = p.isCategory ? CATEGORY_TEXT : '#262626';
                const fontWeight = p.depth === 0 ? '600' : p.isCategory ? '500' : '400';
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
        drawBezierEdge(ctx, e) {
            const { x1, y1, x2, y2, color: stroke, label } = e;
            // 参考样式：细虚线直线
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.strokeStyle = stroke;
            ctx.lineWidth = 1;
            ctx.lineCap = 'round';
            ctx.setLineDash([3.5, 3.5]);
            ctx.stroke();
            ctx.setLineDash([]);
            if (!label || e.labelX == null || e.labelY == null)
                return;
            ctx.save();
            ctx.font = '8px sans-serif';
            ctx.fillStyle = '#A89890';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(label, e.labelX, e.labelY);
            ctx.restore();
        },
        touchDistance(touches) {
            if (touches.length < 2)
                return 0;
            return Math.hypot(touches[1].clientX - touches[0].clientX, touches[1].clientY - touches[0].clientY);
        },
        redrawCanvas() {
            this.paintCached();
        },
        onTouchStart(e) {
            const layout = this._layout;
            if (!layout || !layout.positions.length)
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
                    const ratio = curDist / startDist;
                    const next = clamp((this._pinchStartScale || 1) * ratio, 0.52, 2.5);
                    this._zoomScale = next;
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
            if (this._touchMode === 'pinch') {
                if (e.touches.length >= 2)
                    return;
                this._touchMode = 'pending';
                this.triggerEvent('zoomChange', { scale: this._zoomScale || 1 });
                return;
            }
            if (this._touchMode === 'pan') {
                ;
                this._touchMode = 'pending';
            }
        },
    },
});
