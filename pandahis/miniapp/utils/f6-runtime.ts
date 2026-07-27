/**
 * @antv/f6-wx MIT — 小程序 npm 兼容加载（require 无 .default）
 */

export type F6GraphInstance = {
  data: (d: unknown) => void
  render: () => void
  destroy: () => void
  emitEvent: (e: unknown) => void
  on: (evt: string, fn: (e: unknown) => void) => void
  changeData: (d: unknown) => void
  fitView: (padding?: number) => void
  zoom: (ratio: number, point?: { x: number; y: number }) => void
  zoomTo?: (ratio: number, point?: { x: number; y: number }) => void
  updateLayout?: (cfg: unknown) => void
  getZoom: () => number
}

export type F6Runtime = {
  Graph: new (cfg: Record<string, unknown>) => F6GraphInstance
  registerLayout: (name: string, layout: unknown) => void
}

function pickF6Module(mod: unknown): F6Runtime {
  const m = mod as F6Runtime & { default?: F6Runtime }
  if (m?.Graph && typeof m.registerLayout === 'function') return m
  if (m?.default?.Graph && typeof m.default.registerLayout === 'function') return m.default
  throw new Error('@antv/f6-wx 未正确加载，请在微信开发者工具执行「工具 → 构建 NPM」')
}

/** layout 扩展导出为构造函数，与 F6 主包不同 */
function pickLayoutModule(mod: unknown): unknown {
  if (typeof mod === 'function') return mod
  const m = mod as { default?: unknown }
  if (typeof m?.default === 'function') return m.default
  return mod
}

let cached: F6Runtime | null = null

/** 延迟加载 F6，避免首页启动时因 npm 导出差异崩溃 */
export function getF6Runtime(): F6Runtime {
  if (cached) return cached

  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const f6Mod = require('@antv/f6-wx')
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const radialMod = require('@antv/f6-wx/extends/layout/radialLayout')

  const F6 = pickF6Module(f6Mod)
  const radialLayout = pickLayoutModule(radialMod)

  F6.registerLayout('radial', radialLayout)
  cached = F6
  return F6
}

export function readCanvasMetrics(): { windowWidth: number; pixelRatio: number } {
  try {
    const win = wx.getWindowInfo()
    return {
      windowWidth: win.windowWidth || 375,
      pixelRatio: win.pixelRatio || 2,
    }
  } catch {
    const sys = wx.getSystemInfoSync()
    return {
      windowWidth: sys.windowWidth || 375,
      pixelRatio: sys.pixelRatio || 2,
    }
  }
}
