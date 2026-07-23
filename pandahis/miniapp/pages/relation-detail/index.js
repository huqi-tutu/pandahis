"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const api_1 = require("../../native-utils/api");
const encode_path_segment_1 = require("../../native-utils/encode-path-segment");
const router_1 = require("../../native-utils/router");
Page({
    data: {
        name: '',
        info: null,
        color: '#4A3F3F',
        headerPadPx: 88,
    },
    async onLoad(query) {
        try {
            const sys = wx.getSystemInfoSync();
            const navPx = 88 * (sys.windowWidth / 750);
            this.setData({ headerPadPx: (sys.statusBarHeight || 20) + navPx });
        }
        catch {
            this.setData({ headerPadPx: 88 });
        }
        const boxId = query.boxId;
        const nodeKey = query.nodeKey || query.name;
        if (!boxId || !nodeKey)
            return;
        const name = decodeURIComponent(nodeKey);
        this.setData({ name });
        try {
            const enc = (0, encode_path_segment_1.encodePathSegment)(boxId);
            const key = encodeURIComponent(nodeKey);
            const res = await (0, api_1.request)(`/boxes/${enc}/graph/nodes/${key}`);
            const d = res.data || {};
            this.setData({
                info: {
                    name: d.name || name,
                    category: d.category || '',
                    role: d.role || '',
                    level: d.level || '',
                    lineage: d.lineage || '',
                    summary: d.summary || '',
                    targetBoxId: d.targetBoxId,
                },
            });
        }
        catch {
            this.setData({
                info: {
                    name,
                    category: '关系',
                    role: '',
                    level: '',
                    lineage: '',
                    summary: `暂无 ${name} 的详细关系数据。`,
                },
            });
        }
    },
    goTargetBox() {
        var _a;
        const id = (_a = this.data.info) === null || _a === void 0 ? void 0 : _a.targetBoxId;
        if (!id)
            return;
        (0, router_1.navigateTo)(router_1.ROUTES.boxDetail, { boxId: id });
    },
});
