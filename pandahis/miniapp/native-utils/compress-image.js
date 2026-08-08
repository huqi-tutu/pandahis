"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.compressImageUnder1MB = void 0;
const MAX_BYTES = 1024 * 1024;
function getFileSize(filePath) {
    return new Promise((resolve, reject) => {
        wx.getFileSystemManager().getFileInfo({
            filePath,
            success: (res) => resolve(res.size || 0),
            fail: reject,
        });
    });
}
function compressOnce(src, quality) {
    return new Promise((resolve, reject) => {
        wx.compressImage({
            src,
            quality,
            success: (res) => resolve(res.tempFilePath),
            fail: reject,
        });
    });
}
/**
 * 将本地图片压缩到 1MB 以内（相册选图后调用）。
 * 已小于 1MB 则原样返回。
 */
async function compressImageUnder1MB(filePath) {
    let current = filePath;
    let size = await getFileSize(current);
    if (size <= MAX_BYTES)
        return current;
    let quality = 80;
    for (let i = 0; i < 6; i += 1) {
        current = await compressOnce(current, quality);
        size = await getFileSize(current);
        if (size <= MAX_BYTES)
            return current;
        quality = Math.max(20, quality - 15);
    }
    size = await getFileSize(current);
    if (size > MAX_BYTES) {
        throw new Error('图片过大，请换一张较小的图');
    }
    return current;
}
exports.compressImageUnder1MB = compressImageUnder1MB;
