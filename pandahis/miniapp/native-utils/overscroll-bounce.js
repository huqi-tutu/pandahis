"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.measureScrollOverflow = void 0;
/** 判断内容是否超出 scroll-view 可视区（容差 2px） */
function measureScrollOverflow(page, scrollSelector, contentSelector) {
    return new Promise((resolve) => {
        wx.createSelectorQuery()
            .in(page)
            .select(scrollSelector)
            .boundingClientRect()
            .select(contentSelector)
            .boundingClientRect()
            .exec((res) => {
            const viewport = res[0];
            const content = res[1];
            if (!(viewport === null || viewport === void 0 ? void 0 : viewport.height) || !(content === null || content === void 0 ? void 0 : content.height)) {
                resolve(false);
                return;
            }
            resolve(content.height > viewport.height + 2);
        });
    });
}
exports.measureScrollOverflow = measureScrollOverflow;
