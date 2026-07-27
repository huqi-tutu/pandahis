"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.mergePersistPayload = exports.hasRestorableViewport = exports.stripViewportFields = exports.mergeRemoteHomeState = exports.updateCollapsedForCiv = exports.collapsedForCiv = void 0;
function cleanKeys(value) { return Array.isArray(value) ? value.map(key => String(key || '').trim()).filter(Boolean) : null; }
function cleanCivId(value) { return String(value || '').trim(); }
function validTimestamp(value) { return typeof value === 'string' && value.trim() && Number.isFinite(Date.parse(value)) ? value.trim() : ''; }
function isRecord(value) { return Boolean(value) && typeof value === 'object' && !Array.isArray(value); }
function cleanCollapsedMap(value) { if (!isRecord(value))
    return {}; return Object.entries(value).reduce((r, [rawId, rawKeys]) => { const id = cleanCivId(rawId), keys = cleanKeys(rawKeys); return id && keys ? { ...r, [id]: keys } : r; }, {}); }
function cleanStampMap(value) { if (!isRecord(value))
    return {}; return Object.entries(value).reduce((r, [rawId, rawStamp]) => { const id = cleanCivId(rawId), stamp = validTimestamp(rawStamp); return id && stamp ? { ...r, [id]: stamp } : r; }, {}); }
function sanitizedMaps(state) { return { keys: cleanCollapsedMap(state === null || state === void 0 ? void 0 : state.collapsedDynastyKeysByCiv), stamps: cleanStampMap(state === null || state === void 0 ? void 0 : state.collapsedDynastyUpdatedAtByCiv) }; }
function mergeCollapsedMaps(local, remote) { const l = sanitizedMaps(local), r = sanitizedMaps(remote); return [...new Set([...Object.keys(r.keys), ...Object.keys(r.stamps)])].reduce((m, id) => { const ls = l.stamps[id] || '', rs = r.stamps[id] || ''; if (ls && (!rs || rs < ls))
    return m; return { collapsedDynastyKeysByCiv: Object.prototype.hasOwnProperty.call(r.keys, id) ? { ...m.collapsedDynastyKeysByCiv, [id]: r.keys[id] } : m.collapsedDynastyKeysByCiv, collapsedDynastyUpdatedAtByCiv: rs ? { ...m.collapsedDynastyUpdatedAtByCiv, [id]: rs } : m.collapsedDynastyUpdatedAtByCiv }; }, { collapsedDynastyKeysByCiv: l.keys, collapsedDynastyUpdatedAtByCiv: l.stamps }); }
function collapsedForCiv(state, civId) { if (!state)
    return null; const id = cleanCivId(civId); if (!id)
    return null; const by = cleanCollapsedMap(state.collapsedDynastyKeysByCiv); if (Object.prototype.hasOwnProperty.call(by, id))
    return by[id]; const legacy = cleanKeys(state.collapsedDynastyKeys); return cleanCivId(state.civId) === id && legacy ? legacy : null; }
exports.collapsedForCiv = collapsedForCiv;
function updateCollapsedForCiv(state, civId, keys, updatedAt) { const prev = state || {}, maps = sanitizedMaps(prev), id = cleanCivId(civId), cleaned = cleanKeys(keys), stamp = validTimestamp(updatedAt); if (!id || !cleaned || !stamp)
    return { ...prev, collapsedDynastyKeysByCiv: maps.keys, collapsedDynastyUpdatedAtByCiv: maps.stamps }; return { ...prev, collapsedDynastyKeysByCiv: { ...maps.keys, [id]: cleaned }, collapsedDynastyUpdatedAtByCiv: { ...maps.stamps, [id]: stamp } }; }
exports.updateCollapsedForCiv = updateCollapsedForCiv;
function mergeRemoteHomeState(local, remote) { if (!local && !remote)
    return null; if (!remote)
    return local ? { ...local, ...mergeCollapsedMaps(local, {}) } : null; const base = local || {}, id = cleanCivId(remote.civId), rs = validTimestamp(remote.updatedAt), ls = id ? (sanitizedMaps(base).stamps[id] || '') : ''; const merged = { ...base, ...remote, ...mergeCollapsedMaps(base, remote) }, rkeys = cleanKeys(remote.collapsedDynastyKeys); if (!id || !rs || !rkeys || (ls && rs < ls)) {
    const lkeys = id ? collapsedForCiv(base, id) : null;
    return lkeys ? { ...merged, ...updateCollapsedForCiv(merged, id, lkeys, ls), collapsedDynastyKeys: lkeys } : merged;
} return updateCollapsedForCiv(merged, id, rkeys, rs); }
exports.mergeRemoteHomeState = mergeRemoteHomeState;
function stripViewportFields(state) {
    if (!state)
        return null;
    return { ...state, lastDynastyKey: '', lastScrollTopPx: null, lastNavActiveIdx: null };
}
exports.stripViewportFields = stripViewportFields;
/** 登录用户离开首页时是否有可恢复的视口（五帝顶 = scrollTop 0，不算可恢复偏移） */
function hasRestorableViewport(state) {
    if (!state)
        return false;
    const scroll = state.lastScrollTopPx;
    if (typeof scroll === 'number' && scroll > 0)
        return true;
    if (scroll === 0)
        return false;
    return Boolean(String(state.lastDynastyKey || '').trim());
}
exports.hasRestorableViewport = hasRestorableViewport;
function mergePersistPayload(existing, next) {
    const prev = existing || {};
    const cur = next || {};
    const prevMaps = sanitizedMaps(prev);
    const curMaps = sanitizedMaps(cur);
    const prevScroll = typeof prev.lastScrollTopPx === 'number' && prev.lastScrollTopPx > 0 ? prev.lastScrollTopPx : 0;
    const curScroll = typeof cur.lastScrollTopPx === 'number' ? Math.max(0, cur.lastScrollTopPx) : 0;
    const prevNav = typeof prev.lastNavActiveIdx === 'number' && prev.lastNavActiveIdx >= 0 ? prev.lastNavActiveIdx : null;
    const curNav = typeof cur.lastNavActiveIdx === 'number' && cur.lastNavActiveIdx >= 0 ? cur.lastNavActiveIdx : null;
    const prevDynasty = String(prev.lastDynastyKey || '').trim();
    const curDynasty = String(cur.lastDynastyKey || '').trim();
    const atTop = curScroll <= 0;
    const lastScrollTopPx = typeof cur.lastScrollTopPx === 'number' ? curScroll : null;
    const lastDynastyKey = atTop ? '' : (curScroll > 0 && curDynasty ? curDynasty : curDynasty || prevDynasty);
    const lastNavActiveIdx = atTop ? (curNav != null ? curNav : null) : (curNav != null ? curNav : prevNav);
    return {
        ...cur,
        collapsedDynastyKeysByCiv: { ...prevMaps.keys, ...curMaps.keys },
        collapsedDynastyUpdatedAtByCiv: { ...prevMaps.stamps, ...curMaps.stamps },
        lastScrollTopPx,
        lastNavActiveIdx,
        lastDynastyKey,
    };
}
exports.mergePersistPayload = mergePersistPayload;
