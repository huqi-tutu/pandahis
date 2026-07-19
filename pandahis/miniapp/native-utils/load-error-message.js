"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.formatUserFacingError = exports.formatEmptySwimError = exports.formatDynastyLoadError = void 0;
function formatDynastyLoadError(error, develop) {
    if (!develop) {
        return '朝代数据暂时无法加载，请稍后重试。';
    }
    const message = error instanceof Error
        ? error.message
        : String((error === null || error === void 0 ? void 0 : error.message) || '加载失败');
    return `无法加载朝代数据（${message}）。请确认后端已启动且已导入 historical_dynasty / historical_box 数据。`;
}
exports.formatDynastyLoadError = formatDynastyLoadError;
function formatEmptySwimError(develop) {
    if (!develop) {
        return '该朝代画布暂时无法展示，请稍后重试。';
    }
    return '该朝代画布暂无数据（swim-matrix 泳道为空）。请检查后端 swim-matrix 导入。';
}
exports.formatEmptySwimError = formatEmptySwimError;
function formatUserFacingError(error, develop, fallback = '操作失败，请稍后重试') {
    if (develop && error instanceof Error && error.message.trim()) {
        return error.message.trim();
    }
    return fallback;
}
exports.formatUserFacingError = formatUserFacingError;
