"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.lookupDictionary = void 0;
const api_1 = require("./api");
async function lookupDictionary(query) {
    const q = String(query || '').trim();
    if (!q) {
        return { query: '', entries: [] };
    }
    const res = await (0, api_1.request)(`/dictionary/lookup?q=${encodeURIComponent(q)}`);
    return res.data;
}
exports.lookupDictionary = lookupDictionary;
