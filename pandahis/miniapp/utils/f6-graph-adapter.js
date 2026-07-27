"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.strokeForRelation = exports.toF6GraphData = exports.computeDepths = exports.buildParentMap = exports.mapRelationType = exports.MAX_RENDER_DEPTH = void 0;
/**
 * 将后端 /boxes/:id/graph 数据转为 @antv/f6-wx RadialLayout 所需结构。
 * MIT @antv/f6-wx — 本地布局，无云端 API。
 */
const relation_mindmap_layout_1 = require("./relation-mindmap-layout");
exports.MAX_RENDER_DEPTH = 4;
const STROKE = {
    center: 'rgba(140, 72, 58, 0.55)',
    family: 'rgba(162, 115, 79, 0.55)',
    colleague: 'rgba(127, 176, 105, 0.55)',
    enemy: 'rgba(180, 100, 100, 0.55)',
    teacher: 'rgba(99, 137, 156, 0.55)',
    other: 'rgba(120, 110, 105, 0.45)',
};
function parseExtra(extraJson) {
    if (!extraJson)
        return {};
    try {
        return JSON.parse(extraJson);
    }
    catch {
        return {};
    }
}
function normalizeCategory(raw) {
    const g = (raw || '').trim();
    if (g === '君臣')
        return '同僚';
    if (g === '敌对')
        return '外敌';
    return g;
}
function isCategoryNode(node) {
    if (node.type === 'category')
        return true;
    if (String(node.key || '').startsWith('cat_'))
        return true;
    const extra = parseExtra(node.extraJson);
    return extra.isCategoryNode === true;
}
function mapRelationType(node, centerKey) {
    if (node.key === centerKey)
        return 'center';
    const extra = parseExtra(node.extraJson);
    const cat = normalizeCategory(String(extra['关系类别'] || extra.group || extra.category || ''));
    if (isCategoryNode(node)) {
        if (cat.includes('家庭') || node.name === '家庭')
            return 'family';
        if (cat.includes('同僚') || node.name === '同僚')
            return 'colleague';
        if (cat.includes('外敌') || cat.includes('敌对') || node.name === '外敌')
            return 'enemy';
        if (cat.includes('师从') || node.name === '师从')
            return 'teacher';
        return 'other';
    }
    if (cat.includes('家庭'))
        return 'family';
    if (cat.includes('同僚'))
        return 'colleague';
    if (cat.includes('外敌') || cat.includes('敌对'))
        return 'enemy';
    if (cat.includes('师从'))
        return 'teacher';
    return 'other';
}
exports.mapRelationType = mapRelationType;
function buildParentMap(centerKey, edges) {
    const adj = new Map();
    for (const e of edges || []) {
        if (!adj.has(e.fromKey))
            adj.set(e.fromKey, []);
        adj.get(e.fromKey).push(e.toKey);
    }
    const parent = new Map();
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
exports.buildParentMap = buildParentMap;
function computeDepths(centerKey, edges) {
    const adj = new Map();
    for (const e of edges || []) {
        if (!adj.has(e.fromKey))
            adj.set(e.fromKey, []);
        adj.get(e.fromKey).push(e.toKey);
    }
    const depth = new Map();
    depth.set(centerKey, 0);
    const q = [centerKey];
    while (q.length) {
        const u = q.shift();
        for (const v of adj.get(u) || []) {
            if (depth.has(v))
                continue;
            depth.set(v, (depth.get(u) || 0) + 1);
            q.push(v);
        }
    }
    return depth;
}
exports.computeDepths = computeDepths;
function nodeVisible(key, depthMap, parentMap, expandedKeys) {
    const d = depthMap.get(key);
    if (d === undefined)
        return false;
    if (d <= exports.MAX_RENDER_DEPTH)
        return true;
    if (d !== exports.MAX_RENDER_DEPTH + 1)
        return false;
    const parent = parentMap.get(key);
    if (!parent)
        return false;
    return (depthMap.get(parent) === exports.MAX_RENDER_DEPTH && expandedKeys.has(parent));
}
function toF6GraphData(payload, expandedKeys = new Set(), viewport) {
    var _a, _b;
    const nodes = payload.nodes || [];
    const edges = payload.edges || [];
    const centerId = payload.centerNodeKey || ((_a = nodes[0]) === null || _a === void 0 ? void 0 : _a.key) || '';
    if (!centerId)
        return { nodes: [], edges: [], centerId: '', hiddenCount: 0 };
    const depthMap = computeDepths(centerId, edges);
    const parentMap = buildParentMap(centerId, edges);
    const nodeByKey = new Map(nodes.map((n) => [n.key, n]));
    let hiddenCount = 0;
    for (const n of nodes) {
        const d = depthMap.get(n.key);
        if (d !== undefined && d > exports.MAX_RENDER_DEPTH && !nodeVisible(n.key, depthMap, parentMap, expandedKeys)) {
            hiddenCount++;
        }
    }
    const visibleIds = new Set();
    for (const n of nodes) {
        if (nodeVisible(n.key, depthMap, parentMap, expandedKeys))
            visibleIds.add(n.key);
    }
    const f6Nodes = [];
    for (const id of visibleIds) {
        const n = nodeByKey.get(id);
        if (!n)
            continue;
        const depth = (_b = depthMap.get(id)) !== null && _b !== void 0 ? _b : 0;
        const relationType = mapRelationType(n, centerId);
        const name = (n.name || n.key).trim();
        const childBeyond = (edges || []).some((e) => { var _a; return e.fromKey === id && ((_a = depthMap.get(e.toKey)) !== null && _a !== void 0 ? _a : 999) > exports.MAX_RENDER_DEPTH; });
        const hasHiddenChildren = depth === exports.MAX_RENDER_DEPTH && childBeyond;
        const collapsed = hasHiddenChildren && !expandedKeys.has(id);
        const label = collapsed ? `${name} ▸` : expandedKeys.has(id) && hasHiddenChildren ? `${name} ▾` : name;
        const size = relationType === 'center' ? 64 : isCategoryNode(n) ? 52 : 46;
        const style = relationType === 'center'
            ? { fill: '#B85C48', stroke: 'rgba(140, 72, 58, 0.85)', lineWidth: 2 }
            : { fill: '#FAF8F5', stroke: STROKE[relationType], lineWidth: 1.5 };
        f6Nodes.push({
            id,
            label,
            depth,
            relationType,
            targetBoxId: n.targetBoxId,
            size,
            hasHiddenChildren,
            collapsed,
            style,
            labelCfg: {
                style: {
                    fontSize: relationType === 'center' ? 13 : 11,
                    fill: relationType === 'center' ? '#FAF8F5' : '#343A40',
                    fontWeight: relationType === 'center' ? 600 : 400,
                },
            },
        });
    }
    const f6Edges = [];
    const edgesBySource = new Map();
    for (const e of edges || []) {
        if (!visibleIds.has(e.fromKey) || !visibleIds.has(e.toKey))
            continue;
        const target = nodeByKey.get(e.toKey);
        const relationType = target ? mapRelationType(target, centerId) : 'other';
        const label = (e.label || '').trim();
        const edge = {
            source: e.fromKey,
            target: e.toKey,
            label: label || undefined,
            type: 'quadratic',
            style: {
                stroke: STROKE[relationType],
                lineWidth: 1.5,
                lineDash: [4, 4],
                endArrow: false,
            },
        };
        f6Edges.push(edge);
        if (!edgesBySource.has(e.fromKey))
            edgesBySource.set(e.fromKey, []);
        edgesBySource.get(e.fromKey).push(edge);
    }
    for (const group of edgesBySource.values()) {
        group.sort((a, b) => a.target.localeCompare(b.target));
        group.forEach((edge, idx) => {
            if (!edge.label)
                return;
            const n = group.length;
            const refY = n <= 1 ? 0 : -10 + (idx / Math.max(1, n - 1)) * 20;
            edge.labelCfg = {
                autoRotate: true,
                refY,
                style: {
                    fontSize: 9,
                    fill: '#FAF8F5',
                    background: {
                        fill: 'rgba(108, 117, 125, 0.88)',
                        padding: [2, 5, 2, 5],
                        radius: 4,
                    },
                },
            };
        });
    }
    const layoutNodes = nodes.filter((n) => visibleIds.has(n.key));
    const layoutEdges = (edges || []).filter((e) => visibleIds.has(e.fromKey) && visibleIds.has(e.toKey));
    const positions = (0, relation_mindmap_layout_1.computeMindmapPositions)(centerId, layoutNodes, layoutEdges, viewport);
    for (const node of f6Nodes) {
        const p = positions.get(node.id);
        if (p) {
            node.x = p.x;
            node.y = p.y;
        }
    }
    return { nodes: f6Nodes, edges: f6Edges, centerId, hiddenCount };
}
exports.toF6GraphData = toF6GraphData;
function strokeForRelation(relationType) {
    return STROKE[relationType] || STROKE.other;
}
exports.strokeForRelation = strokeForRelation;
