"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isSubCategoryNode = exports.isCategoryNode = exports.normalizeGroupName = exports.parseExtraGroup = exports.layoutMaxRadius = exports.hasNodeOverlap = exports.childWithinParentWedge = exports.computeMindmapPositions = exports.prepareRelationGraph = exports.MAX_PERSONS_PER_HUB = exports.RING_RADIUS = exports.LAYOUT_NODE_R = void 0;
exports.LAYOUT_NODE_R = {
    center: 28,
    category: 2,
    subcategory: 20,
    person: 22,
};
/** 四圈层基准半径 */
exports.RING_RADIUS = [0, 128, 230, 340, 450];
const NODE_GAP = 8;
const MIN_SECTOR = 0.18;
const CATEGORY_ORDER = ['家庭', '同僚', '敌对', '师徒', '好友'];
const VIRT_FRI_HUB = '__virt_fri_hub__';
/** 圈1枢纽在 R1 上的最小弦长（防标签重叠；含胶囊间距） */
const MIN_HUB_CHORD = 64;
/** 每个二级枢纽下直接人物上限（与数据规范一致） */
exports.MAX_PERSONS_PER_HUB = 10;
const TWO_PI = Math.PI * 2;
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
exports.normalizeGroupName = normalizeGroupName;
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
exports.parseExtraGroup = parseExtraGroup;
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
exports.isSubCategoryNode = isSubCategoryNode;
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
exports.isCategoryNode = isCategoryNode;
function childrenOf(parentKey, edges) {
    return (edges || [])
        .filter((e) => e.fromKey === parentKey)
        .map((e) => e.toKey)
        .sort();
}
function personChildren(parentKey, edges, nodeMap) {
    return childrenOf(parentKey, edges).filter((k) => {
        const m = nodeMap.get(k);
        return !!(m && !isCategoryNode(m) && !isSubCategoryNode(m));
    });
}
function polar(cx, cy, angle, dist) {
    return { x: cx + Math.cos(angle) * dist, y: cy + Math.sin(angle) * dist };
}
/** atan2 角是否落在连续角域 [a0,a1]（允许 ±2π 等价表示） */
function angleInWedge(atan2Ang, a0, a1, eps = 0.03) {
    for (const delta of [0, Math.PI * 2, -Math.PI * 2]) {
        const a = atan2Ang + delta;
        if (a >= a0 - eps && a <= a1 + eps)
            return true;
    }
    return false;
}
function clampAngleToWedge(atan2Ang, a0, a1) {
    const lo = a0 + 0.01;
    const hi = a1 - 0.01;
    if (lo >= hi)
        return (a0 + a1) / 2;
    let best = atan2Ang;
    let bestDist = Infinity;
    for (const delta of [0, Math.PI * 2, -Math.PI * 2]) {
        const a = atan2Ang + delta;
        const clamped = Math.min(hi, Math.max(lo, a));
        const dist = Math.abs(a - clamped);
        if (dist < bestDist) {
            bestDist = dist;
            best = clamped;
        }
    }
    return best;
}
function categoryBox(name, compact = false) {
    if (compact)
        return { w: Math.max(48, name.length * 10 + 18), h: 26 };
    return { w: Math.max(56, name.length * 11 + 22), h: 30 };
}
/** 人物胶囊尺寸（与画布圆角矩形观感对齐，供碰撞/弦长计算） */
function estimatePersonBox(name) {
    const len = Math.max(1, Array.from(name || '').length);
    return { w: Math.max(40, Math.min(76, len * 11 + 14)), h: 28 };
}
function personMinAngle(name, ringR) {
    const box = estimatePersonBox(name);
    const chord = box.w + NODE_GAP;
    return 2 * Math.asin(Math.min(0.95, chord / (2 * Math.max(ringR, 40))));
}
function fitNodeScale(count, sectorRad, ringR, baseR) {
    if (count <= 1)
        return 1;
    const half = sectorRad / count / 2;
    const chord = 2 * ringR * Math.sin(Math.max(half, 0.02));
    const need = baseR * 2 + NODE_GAP;
    if (chord >= need)
        return 1;
    return Math.max(0.42, chord / need);
}
/** 子树权重：叶=1；内部节点=1+Σ子 */
function subtreeWeight(key, edges, nodeMap, cache) {
    if (cache.has(key))
        return cache.get(key);
    const kids = personChildren(key, edges, nodeMap);
    if (!kids.length) {
        cache.set(key, 1);
        return 1;
    }
    const w = 1 + kids.reduce((s, k) => s + subtreeWeight(k, edges, nodeMap, cache), 0);
    cache.set(key, w);
    return w;
}
/** 一级分类扇区权重：ring2 + 0.55*ring3 + 0.35*ring4 */
function categorySectorWeight(catKey, edges, nodeMap) {
    let ring2 = 0;
    let ring3 = 0;
    let ring4 = 0;
    let hubCount = 0;
    for (const subKey of childrenOf(catKey, edges)) {
        const sub = nodeMap.get(subKey);
        if (!sub || isCategoryNode(sub))
            continue;
        if (isSubCategoryNode(sub)) {
            hubCount += 1;
            for (const p2 of personChildren(subKey, edges, nodeMap)) {
                ring2 += 1;
                for (const p3 of personChildren(p2, edges, nodeMap)) {
                    ring3 += 1;
                    ring4 += personChildren(p3, edges, nodeMap).length;
                }
            }
        }
        else {
            ring2 += 1;
            for (const p3 of personChildren(subKey, edges, nodeMap)) {
                ring3 += 1;
                ring4 += personChildren(p3, edges, nodeMap).length;
            }
        }
    }
    const w = Math.max(1, ring2 + 0.55 * ring3 + 0.35 * ring4);
    return { w, ring2, ring3, ring4, hubCount };
}
function hubMinAngle(hubName, ringR) {
    const box = categoryBox(hubName, true);
    const chord = Math.max(MIN_HUB_CHORD, box.w + NODE_GAP * 1.5);
    return 2 * Math.asin(Math.min(0.95, chord / (2 * ringR)));
}
/** 两枢纽中心在 R1 上的最小角距（按各自盒宽） */
function hubPairMinDelta(boxWa, boxWb, ringR) {
    const chord = boxWa / 2 + boxWb / 2 + NODE_GAP * 1.25;
    return 2 * Math.asin(Math.min(0.95, chord / (2 * ringR)));
}
/**
 * 按权重分配弧长，并保证每段 ≥ minSpan（从富余段借）。
 * @param totalAngle 可分配总弧长（可小于 2π，以便枢纽间留缝）
 */
function allocateSpansByWeight(weights, minSpans, totalAngle = TWO_PI) {
    const n = weights.length;
    if (!n)
        return [];
    const budget = Math.max(totalAngle, 0.01);
    const ws = weights.map((w) => Math.max(w, 0.01));
    const wSum = ws.reduce((s, w) => s + w, 0);
    const minSum = minSpans.reduce((s, m) => s + m, 0);
    if (minSum >= budget * 0.999) {
        return minSpans.map((m) => (m / minSum) * budget);
    }
    let spans = ws.map((w) => (w / wSum) * budget);
    for (let iter = 0; iter < 16; iter++) {
        let deficit = 0;
        const surplus = spans.map((s, i) => Math.max(0, s - minSpans[i]));
        for (let i = 0; i < n; i++) {
            if (spans[i] + 1e-9 < minSpans[i])
                deficit += minSpans[i] - spans[i];
        }
        if (deficit < 1e-8)
            break;
        const surplusSum = surplus.reduce((a, b) => a + b, 0);
        if (surplusSum < 1e-8) {
            const rem = budget - minSum;
            return minSpans.map((m, i) => m + rem * (ws[i] / wSum));
        }
        const take = Math.min(deficit, surplusSum);
        for (let i = 0; i < n; i++) {
            if (spans[i] < minSpans[i]) {
                spans[i] = minSpans[i];
            }
            else if (surplus[i] > 0) {
                spans[i] -= take * (surplus[i] / surplusSum);
            }
        }
    }
    const sum = spans.reduce((a, b) => a + b, 0) || 1;
    return spans.map((s) => (s / sum) * budget);
}
/** 同辈等分角域 */
function splitEvenly(count, a0, a1) {
    if (count <= 0)
        return [];
    return splitByWeights(Array.from({ length: count }, () => 1), a0, a1);
}
/** 同辈在半径 r 上不重叠所需的最小角向跨度 */
function angularSpanNeeded(kids, ringR, nodeMap) {
    if (!kids.length)
        return 0;
    return kids.reduce((s, k) => {
        var _a;
        const name = String(((_a = nodeMap.get(k)) === null || _a === void 0 ? void 0 : _a.name) || k);
        return s + personMinAngle(name, ringR);
    }, 0);
}
/**
 * 在「上限角域」内紧凑同圆均分：
 * - 全体同半径
 * - 跨度 = min(不重叠所需, 上限扇区)，不强制占满
 * - 块中心尽量靠近 preferMid（通常为父节点角度）
 */
function placeCompactSameRing(kids, ceilA0, ceilA1, preferMid, childRingIndex, childDepth, _parentR, edges, nodeMap, posMap, weightCache) {
    if (!kids.length || childRingIndex > 4)
        return;
    const ceilSpan = Math.max(ceilA1 - ceilA0, 0.06);
    // 同层级固定落在基准圆上，只用角向跨度解决拥挤
    const ringR = exports.RING_RADIUS[Math.min(childRingIndex, exports.RING_RADIUS.length - 1)];
    const needSpan = angularSpanNeeded(kids, ringR, nodeMap);
    const span = Math.min(Math.max(needSpan, kids.length * 0.05), ceilSpan);
    let mid = preferMid;
    for (const d of [0, TWO_PI, -TWO_PI]) {
        const m = preferMid + d;
        if (m >= ceilA0 - 0.2 && m <= ceilA1 + 0.2) {
            mid = m;
            break;
        }
    }
    mid = clampAngleToWedge(mid, ceilA0, ceilA1);
    let b0 = mid - span / 2;
    let b1 = mid + span / 2;
    if (b0 < ceilA0) {
        b1 += ceilA0 - b0;
        b0 = ceilA0;
    }
    if (b1 > ceilA1) {
        b0 -= b1 - ceilA1;
        b1 = ceilA1;
    }
    b0 = Math.max(ceilA0, b0);
    b1 = Math.min(ceilA1, Math.max(b0 + 0.04, b1));
    const slices = splitEvenly(kids.length, b0, b1);
    kids.forEach((kid, i) => {
        placePersonBranch(kid, slices[i].s0, slices[i].s1, childRingIndex, childDepth, edges, nodeMap, posMap, weightCache, ringR, { lockRadius: true });
    });
}
/** 沿边向上找到二级枢纽，取其扇区作为更深圈层的角向上限 */
function findAncestorHubPos(personKey, edges, nodeMap, posMap) {
    const parentOf = new Map();
    for (const e of edges) {
        if (!parentOf.has(e.toKey))
            parentOf.set(e.toKey, e.fromKey);
    }
    let cur = personKey;
    const seen = new Set();
    while (cur && !seen.has(cur)) {
        seen.add(cur);
        const p = parentOf.get(cur);
        if (!p)
            break;
        const meta = nodeMap.get(p);
        if (meta && isSubCategoryNode(meta))
            return posMap.get(p) || null;
        cur = p;
    }
    return null;
}
/**
 * 圈4：同圆紧凑均分。
 * 角向上限优先用所属二级枢纽扇区（而非圈3 父节点的窄楔），
 * 避免「子击角域太窄 → 三孙辈叠牌」。
 */
function placeEvenChildren(kids, a0, a1, childRingIndex, childDepth, parentR, edges, nodeMap, posMap, weightCache, preferMid, ceilA0, ceilA1) {
    placeCompactSameRing(kids, ceilA0 !== null && ceilA0 !== void 0 ? ceilA0 : a0, ceilA1 !== null && ceilA1 !== void 0 ? ceilA1 : a1, preferMid !== null && preferMid !== void 0 ? preferMid : (a0 + a1) / 2, childRingIndex, childDepth, parentR, edges, nodeMap, posMap, weightCache);
}
function hubGroupName(hubMeta) {
    return (parseExtraGroup(hubMeta.extraJson) ||
        normalizeGroupName(String(hubMeta.name || '')) ||
        'other');
}
/**
 * 圈1 全局重排（保持一级分类连续扇区）：
 * 一级扇区 ∝ 圈2 总人数 → 二级枢纽在一级内按圈2 占比 → 圈2 在枢纽内均分
 * → 圈3 按父节点分支紧凑同圆放置，上限为一级扇区。
 */
function relayoutRing1Globally(edges, nodeMap, posMap, weightCache) {
    const hubs = [...posMap.values()].filter((p) => { var _a; return p.isSubCategory && ((_a = p.ringIndex) !== null && _a !== void 0 ? _a : 0) === 1; });
    if (!hubs.length)
        return;
    const r1 = exports.RING_RADIUS[1];
    const packs = hubs
        .map((h) => {
        const meta = nodeMap.get(h.key);
        if (!meta)
            return null;
        const people = personChildren(h.key, edges, nodeMap);
        return {
            hub: h,
            meta,
            group: hubGroupName(meta),
            people,
            ring2: Math.max(people.length, 1),
        };
    })
        .filter((x) => x != null);
    // 按一级分类顺序聚合并保持连续扇区
    const groups = CATEGORY_ORDER.map((g) => ({
        group: g,
        hubs: packs.filter((p) => p.group === g),
    })).filter((g) => g.hubs.length > 0);
    // 未识别分类的枢纽附在末尾
    const known = new Set(groups.flatMap((g) => g.hubs.map((h) => h.hub.key)));
    const orphan = packs.filter((p) => !known.has(p.hub.key));
    if (orphan.length)
        groups.push({ group: 'other', hubs: orphan });
    const catRing2 = groups.map((g) => g.hubs.reduce((s, h) => s + h.ring2, 0));
    const catMin = groups.map((g) => Math.max(0.2, g.hubs.reduce((s, h) => s + hubMinAngle(String(h.meta.name || ''), r1) * 0.45, 0)));
    const catGap = Math.min(0.04, (TWO_PI * 0.05) / Math.max(groups.length, 1));
    const catSpans = allocateSpansByWeight(catRing2, catMin, TWO_PI - catGap * groups.length);
    for (const h of hubs) {
        for (const d of collectDescendants(h.key, edges)) {
            if (d === h.key)
                continue;
            posMap.delete(d);
        }
    }
    let cursor = -Math.PI / 2;
    const categoryWedges = [];
    groups.forEach((g, gi) => {
        const cat0 = cursor;
        const cat1 = cursor + catSpans[gi];
        cursor = cat1 + catGap;
        const hubGap = Math.min(0.035, ((cat1 - cat0) * 0.08) / Math.max(g.hubs.length, 1));
        const hubMins = g.hubs.map((h) => hubMinAngle(String(h.meta.name || ''), r1) * 0.48);
        const hubWeights = g.hubs.map((h) => h.ring2);
        const hubSpans = allocateSpansByWeight(hubWeights, hubMins, Math.max(cat1 - cat0 - hubGap * g.hubs.length, 0.08));
        let hCursor = cat0;
        const hubKeys = [];
        g.hubs.forEach((hp, hi) => {
            const s0 = hCursor;
            const s1 = hCursor + hubSpans[hi];
            hCursor = s1 + hubGap;
            const mid = (s0 + s1) / 2;
            const pt = polar(0, 0, mid, r1);
            addPos(posMap, hp.meta, pt.x, pt.y, 1, { isSubCategory: true }, {
                a0: s0,
                a1: s1,
                ringIndex: 1,
            });
            hubKeys.push(hp.hub.key);
            if (!hp.people.length)
                return;
            const span = Math.max(s1 - s0, 0.06);
            const edgePad = Math.min(0.035, span * 0.1);
            const inner0 = s0 + edgePad;
            const inner1 = Math.max(inner0 + 0.04, s1 - edgePad);
            const pSlices = splitEvenly(hp.people.length, inner0, inner1);
            // 只落圈2（固定 R2），圈3 留到一级扇区统一均分
            hp.people.forEach((p, j) => {
                placePersonBranch(p, pSlices[j].s0, pSlices[j].s1, 2, 2, edges, nodeMap, posMap, weightCache, exports.RING_RADIUS[2], { skipChildren: true, lockRadius: true });
            });
        });
        categoryWedges.push({ group: g.group, a0: cat0, a1: cat1, hubKeys });
    });
    placeRing3ByCategorySectors(categoryWedges, edges, nodeMap, posMap, weightCache);
}
/**
 * 圈3：按圈2 父节点分支分组；
 * 每组同圆、紧凑均分，中心靠近父节点；跨度上限为一级扇区（不强制占满）。
 * 多组在一级扇区内互不重叠地排开。
 */
function placeRing3ByCategorySectors(categoryWedges, edges, nodeMap, posMap, weightCache) {
    for (const cat of categoryWedges) {
        const pad = Math.min(0.03, (cat.a1 - cat.a0) * 0.06);
        const ceilA0 = cat.a0 + pad;
        const ceilA1 = Math.max(ceilA0 + 0.05, cat.a1 - pad);
        const ceilSpan = ceilA1 - ceilA0;
        const branches = [];
        for (const hubKey of cat.hubKeys) {
            for (const p2 of personChildren(hubKey, edges, nodeMap)) {
                const kids = personChildren(p2, edges, nodeMap).filter((k) => !posMap.has(k));
                if (!kids.length)
                    continue;
                const parent = posMap.get(p2);
                let mid = parent ? Math.atan2(parent.y, parent.x) : (ceilA0 + ceilA1) / 2;
                mid = clampAngleToWedge(mid, ceilA0, ceilA1);
                branches.push({ parentKey: p2, kids, mid });
            }
        }
        if (!branches.length)
            continue;
        branches.sort((a, b) => a.mid - b.mid);
        // 圈3 全体固定在 RING_RADIUS[3]
        const ringR = exports.RING_RADIUS[3];
        // 各分支紧凑跨度（够摆开即可；总和超出一级上限时等比压缩）
        const spans = branches.map((b) => Math.min(angularSpanNeeded(b.kids, ringR, nodeMap), ceilSpan));
        const totalNeed = spans.reduce((s, x) => s + x, 0);
        const scale = totalNeed > ceilSpan ? ceilSpan / totalNeed : 1;
        const useSpans = spans.map((s) => Math.max(s * scale, 0.05));
        const blocks = branches.map((b, i) => {
            const span = useSpans[i];
            return { kids: b.kids, mid: b.mid, span, b0: b.mid - span / 2, b1: b.mid + span / 2 };
        });
        for (let pass = 0; pass < 24; pass++) {
            let moved = false;
            // 夹进一级扇区
            for (const bl of blocks) {
                if (bl.b0 < ceilA0) {
                    bl.b1 += ceilA0 - bl.b0;
                    bl.b0 = ceilA0;
                    moved = true;
                }
                if (bl.b1 > ceilA1) {
                    bl.b0 -= bl.b1 - ceilA1;
                    bl.b1 = ceilA1;
                    moved = true;
                }
                bl.b0 = Math.max(ceilA0, bl.b0);
                bl.b1 = Math.min(ceilA1, bl.b1);
                if (bl.b1 - bl.b0 < bl.span * 0.98) {
                    // 被夹扁时尽量恢复跨度
                    const mid = (bl.b0 + bl.b1) / 2;
                    bl.b0 = Math.max(ceilA0, mid - bl.span / 2);
                    bl.b1 = Math.min(ceilA1, bl.b0 + bl.span);
                    bl.b0 = Math.max(ceilA0, bl.b1 - bl.span);
                }
            }
            for (let i = 0; i < blocks.length - 1; i++) {
                const a = blocks[i];
                const b = blocks[i + 1];
                if (a.b1 <= b.b0 + 1e-4)
                    continue;
                const overlap = a.b1 - b.b0;
                const push = overlap / 2 + 0.008;
                a.b0 -= push;
                a.b1 -= push;
                b.b0 += push;
                b.b1 += push;
                moved = true;
            }
            if (!moved)
                break;
        }
        // 再次夹紧
        for (const bl of blocks) {
            if (bl.b0 < ceilA0) {
                bl.b1 += ceilA0 - bl.b0;
                bl.b0 = ceilA0;
            }
            if (bl.b1 > ceilA1) {
                bl.b0 -= bl.b1 - ceilA1;
                bl.b1 = ceilA1;
            }
            bl.b0 = Math.max(ceilA0, Math.min(bl.b0, ceilA1 - 0.04));
            bl.b1 = Math.max(bl.b0 + 0.04, Math.min(bl.b1, ceilA1));
            const slices = splitEvenly(bl.kids.length, bl.b0, bl.b1);
            bl.kids.forEach((kid, j) => {
                placePersonBranch(kid, slices[j].s0, slices[j].s1, 3, 3, edges, nodeMap, posMap, weightCache, ringR, { lockRadius: true });
            });
        }
    }
}
/** 从当前枢纽角域反推一级扇区，并重挂圈3 */
function replaceRing3FromHubWedges(edges, nodeMap, posMap, weightCache) {
    const hubs = [...posMap.values()].filter((p) => isRing1Hub(p) && p.a0 != null && p.a1 != null);
    const byGroup = new Map();
    for (const h of hubs) {
        const meta = nodeMap.get(h.key);
        if (!meta)
            continue;
        const g = hubGroupName(meta);
        const list = byGroup.get(g) || [];
        list.push(h);
        byGroup.set(g, list);
    }
    const wedges = [];
    for (const [group, list] of byGroup) {
        const a0 = Math.min(...list.map((h) => h.a0));
        const a1 = Math.max(...list.map((h) => h.a1));
        // 清掉旧圈3/圈4 再挂
        for (const h of list) {
            for (const p2 of personChildren(h.key, edges, nodeMap)) {
                for (const p3 of personChildren(p2, edges, nodeMap)) {
                    for (const d of collectDescendants(p3, edges))
                        posMap.delete(d);
                }
            }
        }
        wedges.push({ group, a0, a1, hubKeys: list.map((h) => h.key) });
    }
    placeRing3ByCategorySectors(wedges, edges, nodeMap, posMap, weightCache);
}
function rotatePosBy(p, delta) {
    if (!delta)
        return;
    const ang = Math.atan2(p.y, p.x) + delta;
    const r = Math.hypot(p.x, p.y) || 1;
    p.x = Math.cos(ang) * r;
    p.y = Math.sin(ang) * r;
    if (p.a0 != null)
        p.a0 += delta;
    if (p.a1 != null)
        p.a1 += delta;
}
/** 旋转枢纽及其已布局子孙（角向整体平移） */
function rotateHubBranch(hubKey, delta, edges, posMap) {
    if (!delta)
        return;
    for (const k of collectDescendants(hubKey, edges)) {
        const p = posMap.get(k);
        if (!p || p.isCategory)
            continue;
        rotatePosBy(p, delta);
    }
}
/**
 * 圈1 硬校验：相邻胶囊角距不足则角向推开（含首尾环绕），
 * 并同步旋转该枢纽下全部人物，避免「胶囊挪了、线还挂在原地」。
 */
function enforceRing1HardSeparation(edges, posMap, maxPass = 40) {
    const hubs = [...posMap.values()].filter((p) => { var _a; return p.isSubCategory && ((_a = p.ringIndex) !== null && _a !== void 0 ? _a : 0) === 1; });
    if (hubs.length <= 1)
        return;
    const r1 = exports.RING_RADIUS[1];
    for (let pass = 0; pass < maxPass; pass++) {
        hubs.sort((a, b) => Math.atan2(a.y, a.x) - Math.atan2(b.y, b.x));
        let moved = false;
        for (let i = 0; i < hubs.length; i++) {
            const a = hubs[i];
            const b = hubs[(i + 1) % hubs.length];
            let angA = Math.atan2(a.y, a.x);
            let angB = Math.atan2(b.y, b.x);
            if (i === hubs.length - 1)
                angB += TWO_PI;
            const delta = angB - angA;
            const need = hubPairMinDelta(a.boxW, b.boxW, r1);
            if (delta >= need - 1e-4)
                continue;
            const push = (need - delta) / 2;
            rotateHubBranch(a.key, -push, edges, posMap);
            rotateHubBranch(b.key, push, edges, posMap);
            // 强制落在 R1（旋转后半径不变，这里保险）
            const na = Math.atan2(a.y, a.x);
            const nb = Math.atan2(b.y, b.x);
            a.x = Math.cos(na) * r1;
            a.y = Math.sin(na) * r1;
            b.x = Math.cos(nb) * r1;
            b.y = Math.sin(nb) * r1;
            moved = true;
        }
        if (!moved)
            break;
    }
}
function addPos(posMap, meta, x, y, depth, flags, opts = {}) {
    var _a;
    const fullName = ((meta.name != null && String(meta.name).trim()) || meta.key).trim();
    const isCenter = !!flags.isCenter;
    const isCategory = !!flags.isCategory;
    const isSubCategory = !!flags.isSubCategory;
    const scale = (_a = opts.scale) !== null && _a !== void 0 ? _a : 1;
    let circleR = exports.LAYOUT_NODE_R.person * scale;
    let boxW = exports.LAYOUT_NODE_R.person * 2 * scale;
    let boxH = Math.max(26, exports.LAYOUT_NODE_R.person * 1.2) * scale;
    if (isCenter) {
        circleR = exports.LAYOUT_NODE_R.center;
        boxW = exports.LAYOUT_NODE_R.center * 2;
        boxH = exports.LAYOUT_NODE_R.center * 2;
    }
    else if (isCategory) {
        circleR = exports.LAYOUT_NODE_R.category;
        boxW = 4;
        boxH = 4;
    }
    else if (isSubCategory) {
        const box = categoryBox(fullName, true);
        boxW = box.w;
        boxH = box.h;
        circleR = Math.max(box.w, box.h) / 2;
    }
    else {
        const box = estimatePersonBox(fullName);
        boxW = box.w * scale;
        boxH = box.h * scale;
        circleR = Math.max(boxW, boxH) / 2;
    }
    posMap.set(meta.key, {
        key: meta.key,
        x,
        y,
        depth,
        isCenter,
        isCategory,
        isSubCategory,
        circleR,
        boxW,
        boxH,
        minR: isCenter || isCategory ? 0 : Math.hypot(x, y),
        scale,
        a0: opts.a0,
        a1: opts.a1,
        ringIndex: opts.ringIndex,
    });
}
/** 收集 key 及其全部后代 */
function collectDescendants(root, edges) {
    const out = [];
    const stack = [root];
    const seen = new Set();
    while (stack.length) {
        const u = stack.pop();
        if (seen.has(u))
            continue;
        seen.add(u);
        out.push(u);
        for (const c of childrenOf(u, edges))
            stack.push(c);
    }
    return out;
}
/**
 * 每个二级枢纽（及旧数据直挂一级分类）下直接人物截断为 max 人，
 * 并删除被截人物及其子孙，避免撑爆图谱。
 */
function capDirectPeoplePerHub(nodes, edges, max = exports.MAX_PERSONS_PER_HUB) {
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const drop = new Set();
    // 截断时保持边的出现顺序（勿按 key 排序，避免 m10 排在 m2 前）
    const kidsInOrder = (parentKey) => edges.filter((e) => e.fromKey === parentKey).map((e) => e.toKey);
    for (const hub of nodes) {
        let people = [];
        if (isSubCategoryNode(hub)) {
            people = kidsInOrder(hub.key).filter((k) => {
                const m = nodeMap.get(k);
                return !!(m && !isCategoryNode(m) && !isSubCategoryNode(m));
            });
        }
        else if (isCategoryNode(hub)) {
            people = kidsInOrder(hub.key).filter((k) => {
                const m = nodeMap.get(k);
                return !!(m && !isCategoryNode(m) && !isSubCategoryNode(m));
            });
        }
        else {
            continue;
        }
        if (people.length <= max)
            continue;
        const keep = new Set(people.slice(0, max));
        for (const p of people) {
            if (keep.has(p))
                continue;
            for (const d of collectDescendants(p, edges))
                drop.add(d);
        }
    }
    if (!drop.size)
        return { nodes, edges };
    const nextNodes = nodes.filter((n) => !drop.has(n.key));
    const nextEdges = edges.filter((e) => !drop.has(e.fromKey) && !drop.has(e.toKey));
    return { nodes: nextNodes, edges: nextEdges };
}
function ensureFriendHub(nodes, edges) {
    const catFri = nodes.find((n) => isCategoryNode(n) && normalizeGroupName(String(n.name || '')) === '好友');
    if (!catFri)
        return { nodes, edges };
    const kids = childrenOf(catFri.key, edges);
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const hasHub = kids.some((k) => {
        const m = nodeMap.get(k);
        return !!(m && isSubCategoryNode(m));
    });
    const directPeople = kids.filter((k) => {
        const m = nodeMap.get(k);
        return !!(m && !isCategoryNode(m) && !isSubCategoryNode(m));
    });
    if (hasHub || !directPeople.length)
        return { nodes, edges };
    if (nodes.some((n) => n.key === VIRT_FRI_HUB))
        return { nodes, edges };
    const hub = {
        key: VIRT_FRI_HUB,
        name: '好友',
        type: 'subcategory',
        extraJson: JSON.stringify({
            isSubCategoryNode: true,
            节点类型: '二级分类',
            关系类别: '好友',
        }),
    };
    const nextNodes = [...nodes, hub];
    const nextEdges = [];
    for (const e of edges) {
        if (e.fromKey === catFri.key && directPeople.includes(e.toKey))
            continue;
        nextEdges.push(e);
    }
    nextEdges.push({ fromKey: catFri.key, toKey: VIRT_FRI_HUB, label: '' });
    for (const pk of directPeople) {
        const old = edges.find((e) => e.fromKey === catFri.key && e.toKey === pk);
        nextEdges.push({ fromKey: VIRT_FRI_HUB, toKey: pk, label: (old === null || old === void 0 ? void 0 : old.label) || '' });
    }
    return { nodes: nextNodes, edges: nextEdges };
}
function splitByWeights(weights, a0, a1) {
    const span = Math.max(a1 - a0, MIN_SECTOR * 0.5);
    const total = weights.reduce((s, w) => s + w, 0) || weights.length;
    let cursor = a0;
    return weights.map((w) => {
        const slice = (Math.max(w, 0.01) / total) * span;
        const s0 = cursor;
        const s1 = cursor + slice;
        cursor = s1;
        return { s0, s1 };
    });
}
/** 在父角域内放置人物；默认子女在本角域内均分（圈3 可由一级扇区统一挂载） */
function placePersonBranch(key, a0, a1, ringIndex, depth, edges, nodeMap, posMap, weightCache, ringROverride, opts) {
    var _a, _b;
    const meta = nodeMap.get(key);
    if (!meta || posMap.has(key))
        return;
    const sector = Math.max(a1 - a0, 0.06);
    const fullName = ((meta.name != null && String(meta.name).trim()) || meta.key).trim();
    // 同层级固定基准圆；拥挤靠角域均分 + 缩牌，禁止单点径向外扩
    const ringR = ringROverride !== null && ringROverride !== void 0 ? ringROverride : exports.RING_RADIUS[Math.min(ringIndex, exports.RING_RADIUS.length - 1)];
    const box = estimatePersonBox(fullName);
    let scale = fitNodeScale(1, sector, ringR, box.w / 2);
    scale = Math.max(0.82, Math.min(1, scale));
    const mid = (a0 + a1) / 2;
    const pt = polar(0, 0, mid, ringR);
    addPos(posMap, meta, pt.x, pt.y, depth, { isSubCategory: false }, { scale, a0, a1, ringIndex });
    if (opts === null || opts === void 0 ? void 0 : opts.skipChildren)
        return;
    const kids = personChildren(key, edges, nodeMap);
    if (!kids.length || ringIndex >= 4)
        return;
    // 圈4：角向上限用二级枢纽扇区（够摆开），中心仍靠近本父节点
    const hubPos = findAncestorHubPos(key, edges, nodeMap, posMap);
    const ceilA0 = (_a = hubPos === null || hubPos === void 0 ? void 0 : hubPos.a0) !== null && _a !== void 0 ? _a : a0;
    const ceilA1 = (_b = hubPos === null || hubPos === void 0 ? void 0 : hubPos.a1) !== null && _b !== void 0 ? _b : a1;
    placeEvenChildren(kids, a0, a1, ringIndex + 1, depth + 1, ringR, edges, nodeMap, posMap, weightCache, mid, ceilA0, ceilA1);
}
function layoutCategorySector(catMeta, angleStart, angleEnd, edges, nodeMap, posMap, weightCache) {
    addPos(posMap, catMeta, 0, 0, 0, { isCategory: true });
    const topKids = childrenOf(catMeta.key, edges).filter((k) => {
        const m = nodeMap.get(k);
        return m && !isCategoryNode(m);
    });
    if (!topKids.length)
        return;
    let sector = Math.max(angleEnd - angleStart, MIN_SECTOR);
    // 初值按圈2 人数定顺序；最终由 relayoutRing1Globally 全圆周按圈2 占比定稿
    const hubEntries = topKids.map((k) => {
        const m = nodeMap.get(k);
        if (isSubCategoryNode(m)) {
            const people = personChildren(k, edges, nodeMap);
            return { key: k, meta: m, isHub: true, people, w: Math.max(people.length, 1) };
        }
        return { key: k, meta: m, isHub: false, people: [k], w: 1 };
    });
    const wSum = hubEntries.reduce((s, h) => s + h.w, 0) || hubEntries.length;
    let spans = hubEntries.map((h) => (h.w / wSum) * sector);
    const spanSum = spans.reduce((s, x) => s + x, 0) || 1;
    spans = spans.map((x) => (x / spanSum) * sector);
    let cAng = angleStart;
    const slices = spans.map((len) => {
        const s0 = cAng;
        const s1 = cAng + len;
        cAng = s1;
        return { s0, s1 };
    });
    hubEntries.forEach((entry, i) => {
        const { s0, s1 } = slices[i];
        if (entry.isHub) {
            const mid = (s0 + s1) / 2;
            const pt = polar(0, 0, mid, exports.RING_RADIUS[1]);
            addPos(posMap, entry.meta, pt.x, pt.y, 1, { isSubCategory: true }, {
                a0: s0,
                a1: s1,
                ringIndex: 1,
            });
            if (!entry.people.length)
                return;
            const pSlices = splitEvenly(entry.people.length, s0, s1);
            entry.people.forEach((p, j) => {
                placePersonBranch(p, pSlices[j].s0, pSlices[j].s1, 2, 2, edges, nodeMap, posMap, weightCache, exports.RING_RADIUS[2], { lockRadius: true });
            });
        }
        else {
            placePersonBranch(entry.key, s0, s1, 2, 2, edges, nodeMap, posMap, weightCache, exports.RING_RADIUS[2], { lockRadius: true });
        }
    });
}
function collisionRadius(p) {
    if (p.isSubCategory)
        return Math.max(p.boxW, p.boxH) / 2 + NODE_GAP * 0.4;
    return Math.max(p.boxW, p.boxH) / 2 + NODE_GAP * 0.35;
}
function isRing1Hub(p) {
    var _a;
    return !!p.isSubCategory && ((_a = p.ringIndex) !== null && _a !== void 0 ? _a : 0) === 1;
}
/** 将人物夹回自身角域（防止任何推挤造成跨分类） */
function clampPersonsToWedges(posMap) {
    var _a;
    for (const p of posMap.values()) {
        if (p.isCenter || p.isCategory || isRing1Hub(p))
            continue;
        if (p.a0 == null || p.a1 == null)
            continue;
        const ri = Math.min(Math.max((_a = p.ringIndex) !== null && _a !== void 0 ? _a : 2, 1), exports.RING_RADIUS.length - 1);
        const r = exports.RING_RADIUS[ri];
        const ang = clampAngleToWedge(Math.atan2(p.y, p.x), p.a0, p.a1);
        p.x = Math.cos(ang) * r;
        p.y = Math.sin(ang) * r;
    }
}
/** 全图按 ringIndex 吸附到基准圆：同层级必须共圆 */
function snapAllToCanonicalRings(posMap) {
    var _a;
    for (const p of posMap.values()) {
        if (p.isCenter || p.isCategory) {
            p.x = 0;
            p.y = 0;
            continue;
        }
        const ri = Math.min(Math.max((_a = p.ringIndex) !== null && _a !== void 0 ? _a : (p.isSubCategory ? 1 : 2), 1), exports.RING_RADIUS.length - 1);
        const targetR = exports.RING_RADIUS[ri];
        const ang = Math.atan2(p.y, p.x);
        p.x = Math.cos(ang) * targetR;
        p.y = Math.sin(ang) * targetR;
    }
}
/** 同父同辈拉回同一基准圆半径 */
function unifySiblingRingRadii(edges, nodeMap, posMap) {
    var _a;
    for (const meta of nodeMap.values()) {
        if (isCategoryNode(meta) || isSubCategoryNode(meta))
            continue;
        const kids = personChildren(meta.key, edges, nodeMap)
            .map((k) => posMap.get(k))
            .filter((p) => p != null && !p.isSubCategory);
        if (kids.length < 2)
            continue;
        const ring = (_a = kids[0].ringIndex) !== null && _a !== void 0 ? _a : 0;
        if (ring < 2)
            continue;
        if (!kids.every((p) => { var _a; return ((_a = p.ringIndex) !== null && _a !== void 0 ? _a : 0) === ring; }))
            continue;
        const targetR = exports.RING_RADIUS[Math.min(ring, exports.RING_RADIUS.length - 1)];
        for (const p of kids) {
            const ang = Math.atan2(p.y, p.x);
            p.x = Math.cos(ang) * targetR;
            p.y = Math.sin(ang) * targetR;
        }
    }
}
/**
 * 圈2/圈3 硬校验：仅在同一父角域内重排或外扩半径。
 * 绝不跨枢纽角向推开（那会打穿分类扇区）。
 */
function enforceRing2HardSeparation(edges, nodeMap, posMap, weightCache) {
    var _a, _b, _c, _d;
    const hubs = [...posMap.values()].filter((p) => isRing1Hub(p));
    for (const hub of hubs) {
        if (hub.a0 == null || hub.a1 == null)
            continue;
        const people = personChildren(hub.key, edges, nodeMap).filter((k) => posMap.has(k));
        if (!people.length)
            continue;
        const nodes = people.map((k) => posMap.get(k)).filter(Boolean);
        let needFix = false;
        if (nodes.length >= 2) {
            nodes.sort((a, b) => Math.atan2(a.y, a.x) - Math.atan2(b.y, b.x));
            for (let i = 0; i < nodes.length - 1; i++) {
                const a = nodes[i];
                const b = nodes[i + 1];
                const dist = Math.hypot(a.x - b.x, a.y - b.y);
                if (dist < (collisionRadius(a) + collisionRadius(b)) * 0.98) {
                    needFix = true;
                    break;
                }
            }
        }
        // 子女叠牌：父节点楔形内圈3 人物重叠则整枝重挂
        for (const pk of people) {
            const kids = personChildren(pk, edges, nodeMap).filter((k) => posMap.has(k));
            if (kids.length < 2)
                continue;
            const kn = kids.map((k) => posMap.get(k)).filter(Boolean);
            kn.sort((a, b) => Math.atan2(a.y, a.x) - Math.atan2(b.y, b.x));
            for (let i = 0; i < kn.length - 1; i++) {
                const dist = Math.hypot(kn[i].x - kn[i + 1].x, kn[i].y - kn[i + 1].y);
                if (dist < (collisionRadius(kn[i]) + collisionRadius(kn[i + 1])) * 0.98) {
                    needFix = true;
                    break;
                }
            }
            if (needFix)
                break;
        }
        if (!needFix)
            continue;
        for (const pk of people) {
            for (const d of collectDescendants(pk, edges))
                posMap.delete(d);
        }
        const span = Math.max(hub.a1 - hub.a0, 0.06);
        const edgePad = Math.min(0.04, span * 0.1);
        const inner0 = hub.a0 + edgePad;
        const inner1 = Math.max(inner0 + 0.04, hub.a1 - edgePad);
        const pSlices = splitEvenly(people.length, inner0, inner1);
        people.forEach((p, j) => {
            placePersonBranch(p, pSlices[j].s0, pSlices[j].s1, 2, 2, edges, nodeMap, posMap, weightCache, exports.RING_RADIUS[2], { skipChildren: true, lockRadius: true });
        });
    }
    // 圈2 重挂后，圈3 仍按一级扇区均分
    replaceRing3FromHubWedges(edges, nodeMap, posMap, weightCache);
    // 跨枢纽：只向各自扇区中心角向收回（保持基准圆半径，绝不径向飞圈）
    const persons = [...posMap.values()].filter((p) => !p.isCenter && !p.isCategory && !p.isSubCategory);
    for (let pass = 0; pass < 48; pass++) {
        let moved = false;
        for (let i = 0; i < persons.length; i++) {
            for (let j = i + 1; j < persons.length; j++) {
                const a = persons[i];
                const b = persons[j];
                if (((_a = a.ringIndex) !== null && _a !== void 0 ? _a : 0) !== ((_b = b.ringIndex) !== null && _b !== void 0 ? _b : 0))
                    continue;
                const dist = Math.hypot(a.x - b.x, a.y - b.y) || 0.01;
                const need = collisionRadius(a) + collisionRadius(b);
                if (dist >= need * 0.98)
                    continue;
                const sameWedge = a.a0 != null &&
                    b.a0 != null &&
                    Math.abs(a.a0 - b.a0) < 1e-6 &&
                    Math.abs(((_c = a.a1) !== null && _c !== void 0 ? _c : 0) - ((_d = b.a1) !== null && _d !== void 0 ? _d : 0)) < 1e-6;
                if (sameWedge)
                    continue;
                const pullIn = (p) => {
                    var _a;
                    if (p.a0 == null || p.a1 == null)
                        return false;
                    const mid = (p.a0 + p.a1) / 2;
                    let ang = Math.atan2(p.y, p.x);
                    for (const d of [0, TWO_PI, -TWO_PI]) {
                        const a2 = ang + d;
                        if (a2 >= p.a0 - 0.2 && a2 <= p.a1 + 0.2) {
                            ang = a2;
                            break;
                        }
                    }
                    const next = ang + (mid - ang) * 0.4;
                    const clamped = clampAngleToWedge(next, p.a0, p.a1);
                    const ri = Math.min(Math.max((_a = p.ringIndex) !== null && _a !== void 0 ? _a : 2, 1), exports.RING_RADIUS.length - 1);
                    const r = exports.RING_RADIUS[ri];
                    if (Math.abs(clamped - ang) < 1e-4)
                        return false;
                    p.x = Math.cos(clamped) * r;
                    p.y = Math.sin(clamped) * r;
                    return true;
                };
                const movedA = pullIn(a);
                const movedB = pullIn(b);
                if (movedA || movedB)
                    moved = true;
            }
        }
        if (!moved)
            break;
    }
    snapAllToCanonicalRings(posMap);
    clampPersonsToWedges(posMap);
}
function resolveNodeOverlaps(positions, maxPass = 80) {
    var _a, _b, _c;
    // 圈1 二级胶囊由全局扇区硬约束定位；人物只做角向推开并锁在基准圆
    const list = positions.filter((p) => !p.isCenter && !p.isCategory && !isRing1Hub(p));
    for (let pass = 0; pass < maxPass; pass++) {
        let moved = false;
        for (let i = 0; i < list.length; i++) {
            for (let j = i + 1; j < list.length; j++) {
                const a = list[i];
                const b = list[j];
                const ri = (_a = a.ringIndex) !== null && _a !== void 0 ? _a : 0;
                const rj = (_b = b.ringIndex) !== null && _b !== void 0 ? _b : 0;
                if (Math.abs(ri - rj) > 1)
                    continue;
                const dist = Math.hypot(b.x - a.x, b.y - a.y) || 0.01;
                const need = collisionRadius(a) + collisionRadius(b);
                if (dist >= need)
                    continue;
                const push = (need - dist) / 2 + 0.5;
                for (const [p, sign] of [
                    [a, -1],
                    [b, 1],
                ]) {
                    let ang = Math.atan2(p.y, p.x);
                    const ring = Math.min(Math.max((_c = p.ringIndex) !== null && _c !== void 0 ? _c : 2, 1), exports.RING_RADIUS.length - 1);
                    const r = exports.RING_RADIUS[ring];
                    ang += sign * (push / Math.max(r, 40));
                    if (p.a0 != null && p.a1 != null) {
                        ang = clampAngleToWedge(ang, p.a0, p.a1);
                    }
                    p.x = Math.cos(ang) * r;
                    p.y = Math.sin(ang) * r;
                    moved = true;
                }
            }
        }
        if (!moved)
            break;
    }
}
function buildPosList(centerKey, nodesIn, edgesIn) {
    const withHub = ensureFriendHub(nodesIn, edgesIn);
    const { nodes, edges } = capDirectPeoplePerHub(withHub.nodes, withHub.edges);
    const nodeMap = new Map(nodes.map((n) => [n.key, n]));
    const posMap = new Map();
    const weightCache = new Map();
    const centerMeta = nodeMap.get(centerKey);
    if (!centerMeta)
        return [];
    addPos(posMap, centerMeta, 0, 0, 0, { isCenter: true });
    const categoryNodes = CATEGORY_ORDER.map((g) => nodes.find((n) => isCategoryNode(n) && normalizeGroupName(String(n.name || '')) === g)).filter((n) => n != null);
    // 一级分类初值扇区也按圈2 人数占比（与二级规则一致；最终枢纽仍全局重排）
    const catWeights = categoryNodes.map((c) => {
        const stats = categorySectorWeight(c.key, edges, nodeMap);
        return { cat: c, w: Math.max(stats.ring2, stats.hubCount, 1), hubCount: stats.hubCount };
    });
    const totalW = catWeights.reduce((s, x) => s + x.w, 0) || categoryNodes.length;
    let cursor = -Math.PI / 2;
    for (const item of catWeights) {
        const span = (item.w / totalW) * Math.PI * 2;
        const pad = Math.min(0.04, span * 0.08);
        layoutCategorySector(item.cat, cursor + pad / 2, cursor + span - pad / 2, edges, nodeMap, posMap, weightCache);
        cursor += span;
    }
    // 跨一级类别重排圈1，消灭「老师/父母」这类扇区接缝重叠
    relayoutRing1Globally(edges, nodeMap, posMap, weightCache);
    enforceRing1HardSeparation(edges, posMap);
    for (const n of nodes) {
        if (posMap.has(n.key))
            continue;
        if (isCategoryNode(n)) {
            addPos(posMap, n, 0, 0, 0, { isCategory: true });
            continue;
        }
        const pt = polar(0, 0, cursor, exports.RING_RADIUS[2]);
        addPos(posMap, n, pt.x, pt.y, 2, { isSubCategory: isSubCategoryNode(n) }, { ringIndex: 2 });
        cursor += 0.2;
    }
    resolveNodeOverlaps([...posMap.values()]);
    enforceRing2HardSeparation(edges, nodeMap, posMap, weightCache);
    resolveNodeOverlaps([...posMap.values()]);
    enforceRing1HardSeparation(edges, posMap);
    // 枢纽旋转后必须夹回角域，杜绝跨分类交错
    clampPersonsToWedges(posMap);
    // 碰撞后恢复同父同辈/同层级「同一圆」
    unifySiblingRingRadii(edges, nodeMap, posMap);
    snapAllToCanonicalRings(posMap);
    clampPersonsToWedges(posMap);
    const keys = new Set(nodesIn.map((n) => n.key));
    if (posMap.has(VIRT_FRI_HUB))
        keys.add(VIRT_FRI_HUB);
    return [...keys]
        .map((k) => posMap.get(k))
        .filter((p) => p != null);
}
function prepareRelationGraph(centerKey, nodes, edges) {
    const withHub = ensureFriendHub(nodes, edges);
    const prepared = capDirectPeoplePerHub(withHub.nodes, withHub.edges, exports.MAX_PERSONS_PER_HUB);
    const posList = buildPosList(centerKey, prepared.nodes, prepared.edges);
    const positions = new Map();
    for (const p of posList)
        positions.set(p.key, { x: p.x, y: p.y });
    return { nodes: prepared.nodes, edges: prepared.edges, positions };
}
exports.prepareRelationGraph = prepareRelationGraph;
function computeMindmapPositions(centerKey, nodes, edges, _viewport) {
    return prepareRelationGraph(centerKey, nodes, edges).positions;
}
exports.computeMindmapPositions = computeMindmapPositions;
/** 子节点是否落在父节点角域内（测试用） */
function childWithinParentWedge(centerKey, nodes, edges, parentKey, childKey) {
    const prepared = ensureFriendHub(nodes, edges);
    const posList = buildPosList(centerKey, prepared.nodes, prepared.edges);
    const parent = posList.find((p) => p.key === parentKey);
    const child = posList.find((p) => p.key === childKey);
    if (!parent || !child)
        return false;
    if (parent.a0 == null || parent.a1 == null)
        return true;
    const ang = Math.atan2(child.y, child.x);
    return angleInWedge(ang, parent.a0, parent.a1, 0.04);
}
exports.childWithinParentWedge = childWithinParentWedge;
function hasNodeOverlap(centerKey, nodes, edges) {
    const prepared = ensureFriendHub(nodes, edges);
    const positions = buildPosList(centerKey, prepared.nodes, prepared.edges);
    for (let i = 0; i < positions.length; i++) {
        for (let j = i + 1; j < positions.length; j++) {
            const a = positions[i];
            const b = positions[j];
            if (a.isCategory || b.isCategory)
                continue;
            if (a.isCenter || b.isCenter)
                continue;
            const ra = collisionRadius(a);
            const rb = collisionRadius(b);
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            if (dx * dx + dy * dy < (ra + rb) * (ra + rb) * 0.92)
                return true;
        }
    }
    return false;
}
exports.hasNodeOverlap = hasNodeOverlap;
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
