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
        rendering: false,
    },
    observers: {
        visible(v) {
            if (v) {
                void this.renderAndShare();
            }
            else {
                this.setData({ rendering: false });
            }
        },
    },
    methods: {
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
        async waitForCanvas() {
            // canvas 挂载后稍等一帧再取 node，避免 wx:if 刚为 true 时查不到
            await new Promise((resolve) => setTimeout(resolve, 32));
            return new Promise((resolve) => {
                this.createSelectorQuery()
                    .select('#sharePosterCanvas')
                    .fields({ node: true, size: true })
                    .exec((res) => {
                    var _a;
                    const canvas = (_a = res === null || res === void 0 ? void 0 : res[0]) === null || _a === void 0 ? void 0 : _a.node;
                    resolve(canvas !== null && canvas !== void 0 ? canvas : null);
                });
            });
        },
        async renderAndShare() {
            if (this.data.rendering)
                return;
            this.setData({ rendering: true });
            try {
                const canvas = await this.waitForCanvas();
                if (!canvas) {
                    throw new Error('canvas 初始化失败');
                }
                const posterPath = await (0, share_poster_canvas_1.renderSharePosterToCanvas)(canvas, this.buildPayload());
                this.setData({ rendering: false });
                this.triggerEvent('ready', { posterPath });
                // 直接调起微信原生图片分享菜单（含发送给朋友 / 朋友圈 / 收藏 / 保存 / 贴图）
                (0, share_poster_canvas_1.openPosterShareMenu)(posterPath);
                // 关闭页面侧状态，避免残留自定义浮层
                this.triggerEvent('close');
            }
            catch (err) {
                this.setData({ rendering: false });
                const msg = err instanceof Error ? err.message : '海报生成失败';
                wx.showToast({ title: msg || '海报生成失败', icon: 'none' });
                this.triggerEvent('close');
            }
        },
    },
});
