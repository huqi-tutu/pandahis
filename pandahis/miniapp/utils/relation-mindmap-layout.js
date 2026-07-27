"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.layoutMaxRadius = exports.hasNodeOverlap = exports.computeMindmapPositions = exports.LAYOUT_NODE_R = void 0;
/** 与 F6 defaultNode / toF6GraphData 中的 size 对齐 */
exports.LAYOUT_NODE_R = {
    center: 32,
    category: 26,
    person: 23,
};
const NODE_GAP = 10;
const NODE_D = exports.LAYOUT_NODE_R.person * 2 + NODE_GAP;
const MIN_FAN = 0.16;
const CATEGORY_ORDER = ['家庭', '师从', '同僚', '外敌'];
const SECTOR_ANGLE = {
    家庭: -Math.PI / 2,
    师从: Math.PI,
    同僚: 0,
    外敌: Math.PI / 2,
};
const WEDGE = {
    家庭: Math.PI * 0.9,
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
function analyzeLayoutMetrics(centerKey, nodes, edges) {
    let maxSiblings = 1;
    const seenParents = new Set();
    for (const e of edges || []) {
        if (seenParents.has(e.fromKey))
            continue;
        seenParents.add(e.fromKey);
        const count = childrenOf(e.fromKey, edges).filter((k) => {
            const m = nodes.find((n) => n.key === k);
            return m && !isCategoryNode(m);
        }).length;
        if (count > maxSiblings)
            maxSiblings = count;
    }
    const categoryCount = nodes.filter((n) => isCategoryNode(n)).length;
    return {
        nodeCount: nodes.length,
        maxSiblings,
        categoryCount: Math.max(1, categoryCount),
    };
}
function polar(cx, cy, angle, dist) {
    return { x: cx + Math.cos(angle) * dist, y: cy + Math.sin(angle) * dist };
}
function radialOf(x, y) {
    return Math.hypot(x, y);
}
function categoryBox(name) {
    return { w: Math.max(56, name.length * 11 + 22), h: 30 };
}
function categoryRadius(name) {
    const box = categoryBox(name);
    return Math.max(box.w, box.h) / 2;
}
function collisionRadius(p) {
    if (p.isCenter || p.isCategory)
        return Math.max(p.boxW, p.boxH) / 2 + NODE_GAP * 0.45;
    return p.circleR + NODE_GAP * 0.45;
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
function hasAnyOverlap(positions) {
    return findFirstOverlap(positions) != null;
}
/** 同一扇区内 n 个兄弟不重叠所需的最小弦长 */
function minChordForSector(sectorRad, slotCount) {
    if (slotCount <= 1)
        return NODE_D * 1.04;
    const half = sectorRad / slotCount / 2;
    return NODE_D / (2 * Math.sin(Math.max(half, 0.04)));
}
/** 两节点 hub 之间的最小连线：边缘相切 + 扇区弦长约束 */
function hubLinkLength(fromR, toR, sectorRad, slotCount) {
    const edgeClear = fromR + toR + NODE_GAP * 0.65;
    const chord = minChordForSector(sectorRad, slotCount);
    return Math.max(edgeClear, chord);
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
function resolveOverlaps(positions, parentMap, childrenMap, maxPass = 240) {
    const posByKey = new Map(positions.map((p) => [p.key, p]));
    for (let pass = 0; pass < maxPass; pass++) {
        const pair = findFirstOverlap(positions);
        if (!pair)
            return;
        const [a, b] = pair;
        const delta = pass < 80 ? 4 : 6;
        if (a.depth === b.depth) {
            pushSubtreeOutward(a.key, delta, parentMap, posByKey, childrenMap);
            pushSubtreeOutward(b.key, delta, parentMap, posByKey, childrenMap);
        }
        else {
            const mover = a.depth > b.depth ? a : b;
            pushSubtreeOutward(mover.key, delta + 1, parentMap, posByKey, childrenMap);
        }
    }
}
/**
 * 在不重叠前提下，二分求最小压缩比（缩短连线、缩小画布跨度）。
 */
function compactToMinimumScale(positions, centerKey) {
    if (positions.length <= 1)
        return 1;
    const snapshot = positions.map((p) => ({ x: p.x, y: p.y }));
    const applyScale = (scale) => {
        positions.forEach((p, i) => {
            if (p.key === centerKey || p.isCenter) {
                p.x = 0;
                p.y = 0;
                return;
            }
            p.x = snapshot[i].x * scale;
            p.y = snapshot[i].y * scale;
        });
    };
    if (!hasAnyOverlap(positions)) {
        let lo = 0.22;
        let hi = 1;
        applyScale(hi);
        if (hasAnyOverlap(positions))
            return 1;
        for (let i = 0; i < 18; i++) {
            const mid = (lo + hi) / 2;
            applyScale(mid);
            if (hasAnyOverlap(positions))
                lo = mid;
            else
                hi = mid;
        }
        applyScale(hi);
        return hi;
    }
    return 1;
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
function addPos(posMap, meta, x, y, depth, flags) {
    const fullName = ((meta.name != null && String(meta.name).trim()) || meta.key).trim();
    const isCenter = !!flags.isCenter;
    const isCategory = !!flags.isCategory;
    let circleR = exports.LAYOUT_NODE_R.person;
    let boxW = exports.LAYOUT_NODE_R.person * 2;
    let boxH = exports.LAYOUT_NODE_R.person * 2;
    if (isCenter) {
        circleR = exports.LAYOUT_NODE_R.center;
        boxW = exports.LAYOUT_NODE_R.center * 2;
        boxH = exports.LAYOUT_NODE_R.center * 2;
    }
    else if (isCategory) {
        const box = categoryBox(fullName);
        boxW = box.w;
        boxH = box.h;
        circleR = categoryRadius(fullName);
    }
    posMap.set(meta.key, {
        key: meta.key,
        x,
        y,
        depth,
        isCenter,
        isCategory,
        circleR,
        boxW,
        boxH,
        minR: isCenter ? 0 : Math.max(0, radialOf(x, y) - 4),
    });
}
function placeSubtree(key, hubX, hubY, angleStart, angleEnd, linkLen, depth, edges, nodeMap, posMap) {
    const meta = nodeMap.get(key);
    if (!meta)
        return;
    const midAngle = (angleStart + angleEnd) / 2;
    const pos = polar(hubX, hubY, midAngle, linkLen);
    addPos(posMap, meta, pos.x, pos.y, depth, {});
    const kids = childrenOf(key, edges).filter((k) => {
        const m = nodeMap.get(k);
        return m && !isCategoryNode(m);
    });
    if (!kids.length)
        return;
    const sector = Math.max(angleEnd - angleStart, MIN_FAN);
    const weights = kids.map((k) => subtreeWeight(k, edges, nodeMap));
    const total = weights.reduce((a, b) => a + b, 0) || kids.length;
    const nextLink = hubLinkLength(exports.LAYOUT_NODE_R.person, exports.LAYOUT_NODE_R.person, sector, kids.length);
    let cursor = angleStart;
    kids.forEach((kid, i) => {
        const slice = (weights[i] / total) * sector;
        const a0 = cursor;
        const a1 = cursor + slice;
        cursor += slice;
        placeSubtree(kid, pos.x, pos.y, a0, a1, nextLink, depth + 1, edges, nodeMap, posMap);
    });
}
function layoutCluster(catMeta, edges, nodeMap, posMap, metrics) {
    var _a, _b;
    const g = normalizeGroupName(String(catMeta.name || ''));
    const base = (_a = SECTOR_ANGLE[g]) !== null && _a !== void 0 ? _a : -Math.PI / 2;
    const wedge = (_b = WEDGE[g]) !== null && _b !== void 0 ? _b : Math.PI * 0.5;
    const catName = String(catMeta.name || '');
    const catR = categoryRadius(catName);
    const linkToCat = hubLinkLength(exports.LAYOUT_NODE_R.center, catR, (Math.PI * 2) / metrics.categoryCount, 1);
    const catPos = polar(0, 0, base, linkToCat);
    addPos(posMap, catMeta, catPos.x, catPos.y, 1, { isCategory: true });
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
        const link = hubLinkLength(catR, exports.LAYOUT_NODE_R.person, slice, Math.max(1, topKids.length));
        placeSubtree(kid, catPos.x, catPos.y, a0, a1, link, 2, edges, nodeMap, posMap);
    });
}
function buildPosList(centerKey, nodes, edges) {
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const metrics = analyzeLayoutMetrics(centerKey, nodes, edges);
    const posMap = new Map();
    const centerMeta = nodeMap.get(centerKey);
    if (!centerMeta)
        return [];
    addPos(posMap, centerMeta, 0, 0, 0, { isCenter: true });
    const categoryNodes = CATEGORY_ORDER.map((g) => nodes.find((n) => isCategoryNode(n) && normalizeGroupName(String(n.name || '')) === g)).filter((n) => n != null);
    for (const cat of categoryNodes) {
        layoutCluster(cat, edges, nodeMap, posMap, metrics);
    }
    const orphanDist = hubLinkLength(exports.LAYOUT_NODE_R.center, exports.LAYOUT_NODE_R.person, Math.PI / 4, 1);
    for (const n of nodes) {
        if (posMap.has(n.key))
            continue;
        addPos(posMap, n, orphanDist, orphanDist, 2, {});
    }
    const positions = nodes.map((n) => posMap.get(n.key)).filter((p) => p != null);
    const parentMap = buildParentMap(centerKey, edges);
    const childrenMap = buildChildrenMap(edges);
    resolveOverlaps(positions, parentMap, childrenMap);
    compactToMinimumScale(positions, centerKey);
    return positions;
}
/** 计算以 centerKey 为原点的节点坐标（F6 fitView 会自动居中） */
function computeMindmapPositions(centerKey, nodes, edges, _viewport) {
    const positions = buildPosList(centerKey, nodes, edges);
    const out = new Map();
    for (const p of positions) {
        out.set(p.key, { x: p.x, y: p.y });
    }
    return out;
}
exports.computeMindmapPositions = computeMindmapPositions;
/** 检测布局是否存在节点重叠（测试用） */
function hasNodeOverlap(centerKey, nodes, edges) {
    const positions = buildPosList(centerKey, nodes, edges);
    return hasAnyOverlap(positions);
}
exports.hasNodeOverlap = hasNodeOverlap;
/** 布局紧凑度指标（测试用）：非中心节点到原点的最大距离 */
function layoutMaxRadius(centerKey, nodes, edges) {
    const positions = computeMindmapPositions(centerKey, nodes, edges);
    let maxR = 0;
    for (const [key, p] of positions) {
        if (key === centerKey)
            continue;
        maxR = Math.max(maxR, Math.hypot(p.x, p.y));
    }
    return maxR;
}
exports.layoutMaxRadius = layoutMaxRadius;
