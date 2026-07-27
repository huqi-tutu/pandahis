declare module '@antv/f6-wx' {
  const F6: {
    Graph: new (cfg: Record<string, unknown>) => {
      data: (d: unknown) => void
      render: () => void
      destroy: () => void
      emitEvent: (e: unknown) => void
      on: (evt: string, fn: (e: unknown) => void) => void
      off: (evt: string, fn?: (e: unknown) => void) => void
      changeData: (d: unknown) => void
      fitView: (padding?: number) => void
      zoom: (ratio: number, point?: { x: number; y: number }) => void
      getZoom: () => number
    }
    registerLayout: (name: string, layout: unknown) => void
  }
  export default F6
}

declare module '@antv/f6-wx/extends/layout/radialLayout' {
  const radialLayout: unknown
  export default radialLayout
}

declare module '@antv/f6-wx/canvas/canvas' {
  // 小程序组件路径占位
}
