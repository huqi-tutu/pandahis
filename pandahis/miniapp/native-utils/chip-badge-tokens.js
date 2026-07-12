"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.chipBadgeToken = exports.CHIP_BADGE_TOKENS = void 0;
exports.CHIP_BADGE_TOKENS = {
    junji: { bg: '#FAF1DD', text: '#B88932' },
    zongqi: { bg: '#F6EAEA', text: '#9A6666' },
    wenchen: { bg: '#F3EDE3', text: '#9A7A45' },
    wujiang: { bg: '#F4EADF', text: '#94643D' },
    shilue: { bg: '#EAF4F7', text: '#5E8A94' },
    dianzhi: { bg: '#E8EFEC', text: '#5E7A70' },
    lunzhu: { bg: '#F0EBF5', text: '#7A668F' },
    huanguan: { bg: '#F1ECF6', text: '#7D6F92' },
    shuzhong: { bg: '#FAF2EA', text: '#A88762' },
    fanzhu: { bg: '#E8EFEC', text: '#5E7A70' },
};
function chipBadgeToken(categoryKey) {
    const key = String(categoryKey || '').trim();
    return exports.CHIP_BADGE_TOKENS[key] || { bg: '#F2F0EC', text: '#7A756C' };
}
exports.chipBadgeToken = chipBadgeToken;
