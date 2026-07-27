"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createRemoteStateSaveQueue = void 0;
function createRemoteStateSaveQueue(send) {
    let active = false, disposed = false;
    let latest;
    let idleResolvers = [];
    const resolveIdle = () => { if (active || latest !== undefined)
        return; const rs = idleResolvers; idleResolvers = []; rs.forEach(r => r()); };
    const drain = () => { if (active || disposed || latest === undefined) {
        resolveIdle();
        return;
    } const snapshot = latest; latest = undefined; active = true; let operation; try {
        operation = Promise.resolve(send(snapshot));
    }
    catch {
        operation = Promise.resolve();
    } operation.catch(() => undefined).then(() => { active = false; drain(); }); };
    return { enqueue(snapshot) { if (disposed)
            return; latest = snapshot; drain(); }, idle() { return !active && latest === undefined ? Promise.resolve() : new Promise(r => idleResolvers.push(r)); }, dispose() { disposed = true; latest = undefined; resolveIdle(); } };
}
exports.createRemoteStateSaveQueue = createRemoteStateSaveQueue;
