"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const share_poster_canvas_1 = require("../../native-utils/share-poster-canvas");
Component({
    properties: {
        visible: {
            type: Boolean,
            value: false,
        },
        quoteText: {
            type: String,
            value: '',
        },
        userName: {
            type: String,
            value: '历史读者',
        },
        userAvatarUrl: {
            type: String,
            value: '',
        },
        sourceLine1: {
            type: String,
            value: '',
        },
        sourceLine2: {
            type: String,
            value: '',
        },
        excerptDate: {
            type: String,
            value: '',
        },
    },
    data: {
        posterPath: '',
        rendering: false,
        renderError: '',
    },
    observers: {
        visible(v) {
            if (v) {
                void this.renderPoster();
            }
            else {
                this.setData({ posterPath: '', renderError: '' });
            }
        },
    },
    methods: {
        noop() { },
        onClose() {
            this.triggerEvent('close');
        },
        buildPayload() {
            return {
                quoteText: this.properties.quoteText,
                userName: this.properties.userName,
                userAvatarUrl: this.properties.userAvatarUrl,
                sourceLine1: this.properties.sourceLine1,
                sourceLine2: this.properties.sourceLine2,
                excerptDate: this.properties.excerptDate,
            };
        },
        async renderPoster() {
            if (this.data.rendering)
                return;
            this.setData({ rendering: true, posterPath: '', renderError: '' });
            try {
                const query = this.createSelectorQuery();
                const node = await new Promise((resolve) => {
                    query
                        .select('#sharePosterCanvas')
                        .fields({ node: true, size: true })
                        .exec((res) => { var _a; return resolve((_a = res === null || res === void 0 ? void 0 : res[0]) !== null && _a !== void 0 ? _a : null); });
                });
                const canvas = node === null || node === void 0 ? void 0 : node.node;
                if (!canvas) {
                    throw new Error('canvas 初始化失败');
                }
                const posterPath = await (0, share_poster_canvas_1.renderSharePosterToCanvas)(canvas, this.buildPayload());
                this.setData({ posterPath, rendering: false, renderError: '' });
                this.triggerEvent('ready', { posterPath });
            }
            catch (err) {
                const msg = err instanceof Error ? err.message : '海报生成失败';
                this.setData({ rendering: false, renderError: msg });
                wx.showToast({ title: '海报生成失败', icon: 'none' });
            }
        },
        ensurePosterReady() {
            const path = this.data.posterPath;
            if (!path) {
                wx.showToast({ title: '海报生成中，请稍候', icon: 'none' });
                return null;
            }
            return path;
        },
        async onSave() {
            const path = this.ensurePosterReady();
            if (!path)
                return;
            try {
                await (0, share_poster_canvas_1.savePosterToAlbum)(path);
                wx.showToast({ title: '已保存到相册', icon: 'success' });
            }
            catch {
                wx.showToast({ title: '保存失败', icon: 'none' });
            }
        },
        onShareFriend() {
            const path = this.ensurePosterReady();
            if (!path)
                return;
            (0, share_poster_canvas_1.openPosterShareMenu)(path);
        },
        onShareTimeline() {
            const path = this.ensurePosterReady();
            if (!path)
                return;
            (0, share_poster_canvas_1.openPosterShareMenu)(path);
        },
    },
});
