"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.highlightAnchorId = exports.applyHighlightsToSegs = exports.applyHighlightsToPlain = exports.findHighlightMarks = void 0;
function findHighlightMarks(plain, highlights) {
    const marks = new Array(plain.length).fill(0);
    for (const h of highlights) {
        const needle = String(h.selectedText || '');
        if (!needle || !h.id)
            continue;
        let from = 0;
        while (from <= plain.length - needle.length) {
            const i = plain.indexOf(needle, from);
            if (i < 0)
                break;
            for (let k = i; k < i + needle.length; k += 1)
                marks[k] = h.id;
            from = i + 1;
        }
    }
    return marks;
}
exports.findHighlightMarks = findHighlightMarks;
function applyHighlightsToPlain(plain, highlights, focusNoteId) {
    if (!plain)
        return [];
    const marks = findHighlightMarks(plain, highlights);
    const segs = [];
    let i = 0;
    while (i < plain.length) {
        const noteId = marks[i] || 0;
        let j = i + 1;
        while (j < plain.length && (marks[j] || 0) === noteId)
            j += 1;
        const text = plain.slice(i, j);
        if (noteId > 0) {
            segs.push({
                text,
                highlight: true,
                noteId,
                anchorId: `note-hl-${noteId}`,
                focus: !!focusNoteId && noteId === focusNoteId,
            });
        }
        else {
            segs.push({ text });
        }
        i = j;
    }
    return segs;
}
exports.applyHighlightsToPlain = applyHighlightsToPlain;
function applyHighlightsToSegs(segs, highlights, focusNoteId) {
    if (!segs.length)
        return [];
    const plain = segs.map((s) => s.text).join('');
    if (!highlights.length) {
        return segs.map((s) => ({ text: s.text, bold: !!s.bold }));
    }
    const marks = findHighlightMarks(plain, highlights);
    const out = [];
    let offset = 0;
    for (const seg of segs) {
        const text = seg.text || '';
        let i = 0;
        while (i < text.length) {
            const global = offset + i;
            const noteId = marks[global] || 0;
            let j = i + 1;
            while (j < text.length && (marks[offset + j] || 0) === noteId)
                j += 1;
            const slice = text.slice(i, j);
            if (noteId > 0) {
                out.push({
                    text: slice,
                    bold: !!seg.bold,
                    highlight: true,
                    noteId,
                    anchorId: `note-hl-${noteId}`,
                    focus: !!focusNoteId && noteId === focusNoteId,
                });
            }
            else {
                out.push({ text: slice, bold: !!seg.bold });
            }
            i = j;
        }
        offset += text.length;
    }
    return out;
}
exports.applyHighlightsToSegs = applyHighlightsToSegs;
function highlightAnchorId(noteId) {
    return `note-hl-${noteId}`;
}
exports.highlightAnchorId = highlightAnchorId;
