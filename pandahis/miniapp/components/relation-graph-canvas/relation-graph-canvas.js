const BG = '#F8F6F2';
const CENTER_FILL = '#B85C48';
const CENTER_STROKE = 'rgba(140, 72, 58, 0.72)';
const CENTER_TEXT = '#FAF8F5';
const CATEGORY_FILL = {
    家庭: 'rgba(250, 246, 242, 0.95)',
    同僚: 'rgba(248, 246, 244, 0.95)',
    师从: 'rgba(246, 250, 248, 0.95)',
    外敌: 'rgba(250, 244, 244, 0.95)',
};
const CATEGORY_STROKE = {
    家庭: 'rgba(162, 115, 79, 0.38)',
    同僚: 'rgba(127, 176, 105, 0.38)',
    师从: 'rgba(99, 137, 156, 0.38)',
    外敌: 'rgba(180, 100, 100, 0.35)',
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
    师从: 'rgba(99, 137, 156, 0.45)',
    外敌: 'rgba(180, 100, 100, 0.42)',
    other: 'rgba(120, 110, 105, 0.38)',
};
const SECTOR_ANGLE = {
    家庭: -Math.PI / 2,
    师从: Math.PI,
    同僚: 0,
    外敌: Math.PI / 2,
};
const CATEGORY_ORDER = ['家庭', '师从', '同僚', '外敌'];
const CENTER_R = 28;
const PERSON_R = 22;
const NODE_GAP = 10;
const CAT_FONT = 11;
const REL_LABEL_H = 13;
const REL_LABEL_FONT = 7;
const CENTER_TO_CAT = 118;
const LINK_L1 = 100;
const LINK_DEEP = 82;
const MIN_FAN = 0.18;
const NODE_D = PERSON_R * 2 + NODE_GAP;
const WEDGE = {
    家庭: Math.PI * 0.88,
    师从: Math.PI * 0.62,
    同僚: Math.PI * 0.62,
    外敌: Math.PI * 0.62,
};
function normalizeGroupName(raw) {
    const g = (raw || '').trim();
    if (g === '君臣')
        return '同僚';
    if (g === '敌对')
        return '外敌';
    return g;
}
function parseExtraGroup(extraJson) {
    if (!extraJson)
        return '';
    try {
        const o = JSON.parse(extraJson);
        if (o.isCategoryNode)
            return normalizeGroupName(String(o.关系类别 || ''));
        const raw = String(o.关系类别 || o.group || o.category || o.cat || '');
        const m = normalizeGroupName(raw).match(/家庭|同僚|师从|外敌/);
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
function isExpandNode(meta, name) {
    const n = (name || (meta === null || meta === void 0 ? void 0 : meta.name) || '').trim();
    return /展开全部|展开更多|\+(\d+)/.test(n) || (meta === null || meta === void 0 ? void 0 : meta.type) === 'expand';
}
function childrenOf(parentKey, edges) {
    return (edges || [])
        .filter((e) => e.fromKey === parentKey)
        .map((e) => e.toKey)
        .sort();
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
function polar(cx, cy, angle, dist) {
    return { x: cx + Math.cos(angle) * dist, y: cy + Math.sin(angle) * dist };
}
/** 节点碰撞半径（含安全间距） */
function collisionRadius(p) {
    if (p.isCenter || p.isCategory)
        return Math.max(p.boxW, p.boxH) / 2 + 4;
    return p.circleR + NODE_GAP / 2;
}
function nodesOverlap(a, b) {
    if (a.key === b.key)
        return false;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const minDist = collisionRadius(a) + collisionRadius(b);
    return dx * dx + dy * dy < minDist * minDist;
}
function findFirstOverlap(positions) {
    for (let i = 0; i < positions.length; i++) {
        for (let j = i + 1; j < positions.length; j++) {
            if (nodesOverlap(positions[i], positions[j]))
                return [positions[i], positions[j]];
        }
    }
    return null;
}
function buildChildrenMap(edges) {
    const m = new Map();
    for (const e of edges || []) {
        if (!m.has(e.fromKey))
            m.set(e.fromKey, []);
        m.get(e.fromKey).push(e.toKey);
    }
    for (const [k, list] of m)
        m.set(k, [...list].sort());
    return m;
}
function moveSubtree(rootKey, dx, dy, childrenMap, posByKey) {
    const stack = [rootKey];
    const seen = new Set();
    while (stack.length) {
        const k = stack.pop();
        if (seen.has(k))
            continue;
        seen.add(k);
        const p = posByKey.get(k);
        if (!p)
            continue;
        p.x += dx;
        p.y += dy;
        if (!p.isCenter)
            p.minR = Math.max(p.minR, radialOf(p.x, p.y) - 4);
        for (const c of childrenMap.get(k) || [])
            stack.push(c);
    }
}
/** 沿父→子方向把整棵子树外推（只向外，不往中心撤） */
function pushSubtreeOutward(nodeKey, delta, parentMap, posByKey, childrenMap) {
    const parentKey = parentMap.get(nodeKey);
    if (!parentKey)
        return;
    const parent = posByKey.get(parentKey);
    const node = posByKey.get(nodeKey);
    if (!parent || !node)
        return;
    const angle = Math.atan2(node.y - parent.y, node.x - parent.x);
    moveSubtree(nodeKey, Math.cos(angle) * delta, Math.sin(angle) * delta, childrenMap, posByKey);
}
/** 固定逻辑：检测到重叠就外推较深子树，直到无重叠或达上限 */
function ensureNoNodeOverlap(positions, parentMap, childrenMap, maxPass = 160) {
    const posByKey = new Map(positions.map((p) => [p.key, p]));
    for (let pass = 0; pass < maxPass; pass++) {
        const pair = findFirstOverlap(positions);
        if (!pair)
            return;
        const [a, b] = pair;
        if (a.depth === b.depth) {
            pushSubtreeOutward(a.key, 6, parentMap, posByKey, childrenMap);
            pushSubtreeOutward(b.key, 6, parentMap, posByKey, childrenMap);
        }
        else {
            const mover = a.depth > b.depth ? a : b;
            pushSubtreeOutward(mover.key, 8, parentMap, posByKey, childrenMap);
        }
    }
}
/** 在角度 sector 内放 n 个兄弟，求满足 NODE_D 的最短连线 */
function minLinkForSector(sectorRad, slotCount, base) {
    if (slotCount <= 1)
        return base;
    const half = sectorRad / slotCount / 2;
    const need = NODE_D / (2 * Math.sin(Math.max(half, 0.05)));
    return Math.max(base, need);
}
function subtreeWeight(key, edges, nodeMap, cache = new Map()) {
    if (cache.has(key))
        return cache.get(key);
    const kids = childrenOf(key, edges).filter((k) => {
        const m = nodeMap.get(k);
        return m && !isCategoryNode(m);
    });
    if (!kids.length) {
        cache.set(key, 1);
        return 1;
    }
    const w = kids.reduce((sum, k) => sum + subtreeWeight(k, edges, nodeMap, cache), 0);
    cache.set(key, Math.max(w, 1));
    return cache.get(key);
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
function categoryBox(name) {
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
        isCenter,
        isExpandNode: !!flags.isExpand,
        isPerson: !isCenter && !isCategory,
        circleR,
        boxW,
        boxH,
        minR: isCenter ? 0 : Math.max(0, radialOf(x, y) - 4),
    });
}
/**
 * 思维导图核心：每个节点独占一段角度 [angleStart, angleEnd]，
 * 子节点在该段内再切分；连线长度由几何公式预先算好，保证兄弟间距 >= NODE_D。
 */
function placeSubtree(key, hubX, hubY, angleStart, angleEnd, linkLen, depth, group, edges, nodeMap, posMap) {
    const meta = nodeMap.get(key);
    if (!meta)
        return;
    const name = ((meta.name != null && String(meta.name).trim()) || key).trim();
    const midAngle = (angleStart + angleEnd) / 2;
    const pos = polar(hubX, hubY, midAngle, linkLen);
    addPos(posMap, meta, pos.x, pos.y, depth, group, {
        isExpand: isExpandNode(meta, name),
    });
    const kids = childrenOf(key, edges).filter((k) => {
        const m = nodeMap.get(k);
        return m && !isCategoryNode(m);
    });
    if (!kids.length)
        return;
    const sector = Math.max(angleEnd - angleStart, MIN_FAN);
    const weights = kids.map((k) => subtreeWeight(k, edges, nodeMap));
    const total = weights.reduce((a, b) => a + b, 0) || kids.length;
    const nextLink = minLinkForSector(sector, kids.length, LINK_DEEP);
    let cursor = angleStart;
    kids.forEach((kid, i) => {
        const slice = (weights[i] / total) * sector;
        const a0 = cursor;
        const a1 = cursor + slice;
        cursor += slice;
        placeSubtree(kid, pos.x, pos.y, a0, a1, nextLink, depth + 1, group, edges, nodeMap, posMap);
    });
}
function layoutCluster(catMeta, edges, nodeMap, posMap) {
    var _a, _b;
    const g = normalizeGroupName(String(catMeta.name || ''));
    const base = (_a = SECTOR_ANGLE[g]) !== null && _a !== void 0 ? _a : -Math.PI / 2;
    const wedge = (_b = WEDGE[g]) !== null && _b !== void 0 ? _b : Math.PI * 0.5;
    const catPos = polar(0, 0, base, CENTER_TO_CAT);
    addPos(posMap, catMeta, catPos.x, catPos.y, 1, g, { isCategory: true });
    const topKids = childrenOf(catMeta.key, edges).filter((k) => {
        const m = nodeMap.get(k);
        return m && !isCategoryNode(m);
    });
    if (!topKids.length)
        return;
    const weights = topKids.map((k) => subtreeWeight(k, edges, nodeMap));
    const total = weights.reduce((a, b) => a + b, 0) || topKids.length;
    const start = base - wedge / 2;
    let cursor = start;
    topKids.forEach((kid, i) => {
        const slice = (weights[i] / total) * wedge;
        const a0 = cursor;
        const a1 = cursor + slice;
        cursor += slice;
        const link = minLinkForSector(slice, 1, LINK_L1);
        placeSubtree(kid, catPos.x, catPos.y, a0, a1, link, 2, g, edges, nodeMap, posMap);
    });
}
function layoutMindMap(nodes, edges, centerKey) {
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const posMap = new Map();
    const centerMeta = nodeMap.get(centerKey);
    if (!centerMeta) {
        return { positions: [], edgeList: [], bounds: { minX: -1, minY: -1, maxX: 1, maxY: 1 }, centerKey };
    }
    addPos(posMap, centerMeta, 0, 0, 0, '', { isCenter: true });
    const categoryNodes = CATEGORY_ORDER.map((g) => nodes.find((n) => isCategoryNode(n) && normalizeGroupName(String(n.name || '')) === g)).filter((n) => n != null);
    for (const cat of categoryNodes) {
        layoutCluster(cat, edges, nodeMap, posMap);
    }
    for (const n of nodes) {
        if (posMap.has(n.key))
            continue;
        addPos(posMap, n, 160, 160, 2, nodeGroup(n), {});
    }
    const positions = nodes.map((n) => posMap.get(n.key)).filter((p) => p != null);
    const parentMap = buildParentMap(centerKey, edges);
    const childrenMap = buildChildrenMap(edges);
    ensureNoNodeOverlap(positions, parentMap, childrenMap);
    const edgeList = buildEdgeList(positions, edges, nodeMap);
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
        edges.sort((ea, eb) => {
            const ta = byKey.get(ea.toKey);
            const tb = byKey.get(eb.toKey);
            if (!from || !ta || !tb)
                return 0;
            return Math.atan2(ta.y - from.y, ta.x - from.x) - Math.atan2(tb.y - from.y, tb.x - from.x);
        });
        edges.forEach((e, idx) => {
            const { w, h } = measureRelLabel(e.label);
            e.labelW = w;
            e.labelH = h;
            const dx = e.x2 - e.x1;
            const dy = e.y2 - e.y1;
            const len = Math.hypot(dx, dy) || 1;
            const ux = dx / len;
            const uy = dy / len;
            const n = edges.length;
            const baseT = n === 1 ? 0.5 : 0.34 + (idx / Math.max(1, n - 1)) * 0.32;
            const tCandidates = [baseT, baseT - 0.06, baseT + 0.06, baseT - 0.12, baseT + 0.12, 0.5];
            let found = false;
            for (const t of tCandidates) {
                if (t < 0.28 || t > 0.72)
                    continue;
                const lx = e.x1 + ux * len * t;
                const ly = e.y1 + uy * len * t;
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
                e.labelX = e.x1 + ux * len * baseT;
                e.labelY = e.y1 + uy * len * baseT;
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
    if (a.isCenter && b.isCategory)
        return '';
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
    if (from.isCategory || from.isCenter) {
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
            const layout = this._layout;
            if (!layout) {
                ;
                this._panX = 0;
                this._panY = 0;
                return;
            }
            const s = this._zoomScale || 1;
            const bcx = (layout.bounds.minX + layout.bounds.maxX) / 2;
            const bcy = (layout.bounds.minY + layout.bounds.maxY) / 2;
            this._panX = -bcx * s;
            this._panY = -bcy * s;
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
                this._zoomScale = 1;
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
                ctx.lineTo(e.x2, e.y2);
                ctx.strokeStyle = active ? e.color : 'rgba(180, 172, 165, 0.12)';
                ctx.lineWidth = highlighted ? 1.5 : 1;
                ctx.setLineDash([4, 4]);
                ctx.lineCap = 'round';
                ctx.stroke();
                ctx.setLineDash([]);
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
            if (p.isCategory) {
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
                const pa = (a.isCenter ? 3 : 0) + (a.isCategory ? 2 : 0);
                const pb = (b.isCenter ? 3 : 0) + (b.isCategory ? 2 : 0);
                return pa - pb;
            });
            for (let i = ordered.length - 1; i >= 0; i--) {
                const p = ordered[i];
                if (p.isCategory || p.isCenter) {
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
            if (!hit || hit.isCategory) {
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
