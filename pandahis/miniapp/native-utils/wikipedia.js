"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.lookupWikipedia = void 0;
const api_1 = require("./api");
async function lookupWikipedia(query, offset = 0, limit = 3) {
    const q = String(query || '').trim();
    if (!q) {
        return {
            query: '',
            found: false,
            resolvedTitle: null,
            paragraphs: [],
            offset: 0,
            nextOffset: null,
            hasMore: false,
            totalParagraphs: 0,
        };
    }
    const path = `/wikipedia/lookup?q=${encodeURIComponent(q)}`
        + `&offset=${Math.max(0, offset)}`
        + `&limit=${Math.max(1, Math.min(8, limit))}`;
    const res = await (0, api_1.request)(path);
    return res.data;
}
exports.lookupWikipedia = lookupWikipedia;
