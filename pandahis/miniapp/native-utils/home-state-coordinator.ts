import { HomeStateLike, mergeRemoteHomeState } from './home-state'
export function mergeRemoteLoadResult(latestLocal: HomeStateLike | null | undefined, remote: HomeStateLike | null | undefined, requestGeneration: number, currentGeneration: number) { return { state: mergeRemoteHomeState(latestLocal, remote), shouldApplyUi: requestGeneration === currentGeneration } }
export type ViewportReadToken = { civId: string; generation: number }
export function isViewportReadCurrent(start: ViewportReadToken, current: ViewportReadToken): boolean { return start.civId === current.civId && start.generation === current.generation }
