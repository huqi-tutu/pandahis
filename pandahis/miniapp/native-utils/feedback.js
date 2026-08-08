"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.submitFeedback = exports.uploadFeedbackImage = exports.FEEDBACK_DAILY_LIMIT = exports.FEEDBACK_IMAGE_MAX = exports.FEEDBACK_CONTENT_MAX = exports.FEEDBACK_TYPES = void 0;
const api_1 = require("./api");
const compress_image_1 = require("./compress-image");
exports.FEEDBACK_TYPES = [
    { value: 'feature', label: '功能反馈' },
    { value: 'content', label: '内容反馈' },
    { value: 'partnership', label: '交流合作' },
    { value: 'other', label: '其他' },
];
exports.FEEDBACK_CONTENT_MAX = 1000;
exports.FEEDBACK_IMAGE_MAX = 3;
exports.FEEDBACK_DAILY_LIMIT = 5;
async function uploadFeedbackImage(localPath) {
    var _a;
    const compressed = await (0, compress_image_1.compressImageUnder1MB)(localPath);
    const res = await (0, api_1.uploadFile)('/feedback/images', compressed, { name: 'file' });
    const url = (_a = res.data) === null || _a === void 0 ? void 0 : _a.url;
    if (!url)
        throw new Error('上传失败');
    return url;
}
exports.uploadFeedbackImage = uploadFeedbackImage;
async function submitFeedback(payload) {
    const res = await (0, api_1.request)('/feedback', {
        method: 'POST',
        auth: true,
        data: {
            feedbackType: payload.feedbackType,
            content: payload.content,
            imageUrls: payload.imageUrls,
        },
    });
    return res.data;
}
exports.submitFeedback = submitFeedback;
