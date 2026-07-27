"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * @antv/f6-wx MIT — 本地 RadialLayout，无云端绘图 API
 */
const f6_graph_adapter_1 = require("../../utils/f6-graph-adapter");
const f6_runtime_1 = require("../../utils/f6-runtime");
Component({
    properties: {
        graph: {
            type: Object,
            value: {},
        },
        viewportHeight: {
            type: Number,
            value: 400,
        },
    },
    data: {
        canvasReady: false,
        canvasWidth: 375,
        layoutHeight: 400,
        pixelRatio: 2,
        scaleLabel: '100%',
        hint: '',
    },
    observers: {
        graph(g) {
            var _a;
            if (!((_a = g === null || g === void 0 ? void 0 : g.nodes) === null || _a === void 0 ? void 0 : _a.length)) {
                this.publishHint('暂无关系数据');
                return;
            }
            this.publishHint('');
            if (this._graphReady)
                this.rebuildGraph();
            else
                this.tryInitGraph();
        },
        viewportHeight(h) {
            if (h > 0)
                this.setData({ layoutHeight: h });
        },
    },
    lifetimes: {
        attached() {
            const { windowWidth, pixelRatio } = (0, f6_runtime_1.readCanvasMetrics)();
            const layoutHeight = this.properties.viewportHeight || 400;
            this.setData({
                canvasWidth: windowWidth,
                layoutHeight,
                pixelRatio,
                canvasReady: true,
            });
            this._expandedKeys = new Set();
        },
        detached() {
            this.destroyGraph();
            this._canvasCtx = null;
        },
    },
    methods: {
        publishHint(message) {
            const hint = String(message || '').trim();
            if (hint !== this.data.hint) {
                this.setData({ hint });
            }
            this.triggerEvent('renderHint', { hint });
        },
        formatScale(zoom) {
            return `${Math.round(zoom * 100)}%`;
        },
        destroyGraph() {
            const g = this._graph;
            if (g) {
                try {
                    g.destroy();
                }
                catch {
                    /* ignore */
                }
            }
            ;
            this._graph = null;
            this._graphReady = false;
        },
        buildLayoutData() {
            const payload = (this.properties.graph || {});
            const expandedKeys = this._expandedKeys;
            const canvas = this._canvasCtx;
            const ratio = this.data.pixelRatio || 1;
            return (0, f6_graph_adapter_1.toF6GraphData)(payload, expandedKeys, {
                width: (canvas === null || canvas === void 0 ? void 0 : canvas.width) || this.data.canvasWidth * ratio,
                height: (canvas === null || canvas === void 0 ? void 0 : canvas.height) || this.data.layoutHeight * ratio,
            });
        },
        onCanvasInit(e) {
            const detail = e.detail || {};
            const ctx = detail.ctx;
            const renderer = detail.renderer || 'mini-native';
            const rect = detail.rect || {};
            const ratio = this.data.pixelRatio || 1;
            // f6-canvas 缓冲区 = 逻辑尺寸 × pixelRatio，F6 必须用 rect 物理尺寸
            const width = rect.width || this.data.canvasWidth * ratio;
            const height = rect.height || this.data.layoutHeight * ratio;
            if (!ctx) {
                this.publishHint('画布初始化失败');
                console.warn('[f6-relation-graph] missing canvas ctx');
                return;
            }
            ;
            this._canvasCtx = { ctx, renderer, width, height };
            console.info('[f6-relation-graph] canvas init', width, height, 'ratio', ratio);
            this.tryInitGraph();
        },
        getCanvasCenter() {
            const canvas = this._canvasCtx;
            const ratio = this.data.pixelRatio || 1;
            const width = (canvas === null || canvas === void 0 ? void 0 : canvas.width) || this.data.canvasWidth * ratio;
            const height = (canvas === null || canvas === void 0 ? void 0 : canvas.height) || this.data.layoutHeight * ratio;
            return { x: width / 2, y: height / 2 };
        },
        normalizeViewport(graph) {
            try {
                graph.fitView(32);
                const z = graph.getZoom();
                if (z < 0.22)
                    graph.fitView(40);
                this.setData({ scaleLabel: this.formatScale(graph.getZoom()) });
            }
            catch {
                /* ignore */
            }
        },
        tryInitGraph() {
            var _a;
            const canvas = this._canvasCtx;
            if (!(canvas === null || canvas === void 0 ? void 0 : canvas.ctx))
                return;
            const payload = (this.properties.graph || {});
            if (!((_a = payload.nodes) === null || _a === void 0 ? void 0 : _a.length))
                return;
            const { nodes, edges, centerId } = this.buildLayoutData();
            if (!nodes.length) {
                this.publishHint('暂无关系数据');
                return;
            }
            let F6;
            try {
                F6 = (0, f6_runtime_1.getF6Runtime)();
            }
            catch (err) {
                const msg = (err === null || err === void 0 ? void 0 : err.message) || '关系图谱加载失败';
                this.publishHint(msg);
                console.warn('[f6-relation-graph] getF6Runtime failed', msg);
                return;
            }
            this.destroyGraph();
            const { ctx, renderer, width, height } = canvas;
            try {
                const graph = new F6.Graph({
                    context: ctx,
                    renderer,
                    width,
                    height,
                    fitView: false,
                    modes: {
                        default: ['drag-canvas', 'zoom-canvas'],
                    },
                    defaultNode: {
                        type: 'circle',
                        size: 48,
                        labelCfg: {
                            position: 'center',
                            style: { fontSize: 11, fill: '#343A40' },
                        },
                    },
                    defaultEdge: {
                        type: 'quadratic',
                        style: {
                            lineWidth: 1.5,
                            lineDash: [4, 4],
                            endArrow: false,
                        },
                        labelCfg: {
                            autoRotate: true,
                            refY: 0,
                            style: {
                                fontSize: 9,
                                fill: '#FAF8F5',
                                background: {
                                    fill: 'rgba(108, 117, 125, 0.88)',
                                    padding: [2, 5, 2, 5],
                                    radius: 4,
                                },
                            },
                        },
                    },
                });
                graph.data({ nodes, edges });
                graph.render();
                this.normalizeViewport(graph);
                graph.on('node:tap', (evt) => {
                    var _a, _b, _c, _d;
                    const model = ((_b = (_a = evt === null || evt === void 0 ? void 0 : evt.item) === null || _a === void 0 ? void 0 : _a.getModel) === null || _b === void 0 ? void 0 : _b.call(_a)) || ((_d = (_c = evt === null || evt === void 0 ? void 0 : evt.item) === null || _c === void 0 ? void 0 : _c.get) === null || _d === void 0 ? void 0 : _d.call(_c, 'model'));
                    if (!(model === null || model === void 0 ? void 0 : model.id))
                        return;
                    const expandedKeys = this._expandedKeys;
                    if (model.hasHiddenChildren) {
                        if (expandedKeys.has(model.id))
                            expandedKeys.delete(model.id);
                        else
                            expandedKeys.add(model.id);
                        this.rebuildGraph();
                        return;
                    }
                    this.triggerEvent('nodeTap', {
                        key: model.id,
                        targetBoxId: model.targetBoxId,
                        nodeType: model.relationType,
                    });
                });
                graph.on('viewportchange', () => {
                    try {
                        const z = graph.getZoom();
                        const label = this.formatScale(z);
                        if (label !== this.data.scaleLabel) {
                            this.setData({ scaleLabel: label });
                            this.triggerEvent('zoomChange', { scale: z });
                        }
                    }
                    catch {
                        /* ignore */
                    }
                });
                this._graph = graph;
                this._graphReady = true;
                this.publishHint('');
                console.info('[f6-relation-graph] render ok nodes=', nodes.length);
            }
            catch (err) {
                const msg = (err === null || err === void 0 ? void 0 : err.message) || '关系图谱渲染失败';
                this.publishHint(msg);
                console.warn('[f6-relation-graph] render failed', err);
            }
        },
        rebuildGraph() {
            const graph = this._graph;
            if (!graph)
                return;
            const { nodes, edges } = this.buildLayoutData();
            if (!nodes.length)
                return;
            graph.changeData({ nodes, edges });
            graph.render();
            this.normalizeViewport(graph);
        },
        onCanvasTouch(e) {
            const graph = this._graph;
            graph === null || graph === void 0 ? void 0 : graph.emitEvent(e.detail);
        },
        onZoomIn() {
            const graph = this._graph;
            if (!graph)
                return;
            const center = this.getCanvasCenter();
            graph.zoom(1.18, center);
            this.setData({ scaleLabel: this.formatScale(graph.getZoom()) });
        },
        onZoomOut() {
            const graph = this._graph;
            if (!graph)
                return;
            const center = this.getCanvasCenter();
            graph.zoom(1 / 1.18, center);
            this.setData({ scaleLabel: this.formatScale(graph.getZoom()) });
        },
        zoomIn() {
            this.onZoomIn();
        },
        zoomOut() {
            this.onZoomOut();
        },
        resetZoom() {
            const graph = this._graph;
            if (!graph)
                return;
            graph.fitView(24);
            this.setData({ scaleLabel: this.formatScale(graph.getZoom()) });
        },
        getZoomScale() {
            var _a;
            const graph = this._graph;
            return ((_a = graph === null || graph === void 0 ? void 0 : graph.getZoom) === null || _a === void 0 ? void 0 : _a.call(graph)) || 1;
        },
        paintCached() {
            /* F6 自绘，保留接口兼容 box-detail 缩放栏 */
        },
    },
});
