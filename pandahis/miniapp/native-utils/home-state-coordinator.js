"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isViewportReadCurrent = exports.mergeRemoteLoadResult = void 0;
const home_state_1 = require("./home-state");
function mergeRemoteLoadResult(latestLocal, remote, requestGeneration, currentGeneration) { return { state: (0, home_state_1.mergeRemoteHomeState)(latestLocal, remote), shouldApplyUi: requestGeneration === currentGeneration }; }
exports.mergeRemoteLoadResult = mergeRemoteLoadResult;
function isViewportReadCurrent(start, current) { return start.civId === current.civId && start.generation === current.generation; }
exports.isViewportReadCurrent = isViewportReadCurrent;
