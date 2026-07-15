export type OffscreenHintItem = {
  id: string
  rightRpx: number
  bottomRpx: number
  weight: number
}

export function dedupeHintItems(items: OffscreenHintItem[]): OffscreenHintItem[] {
  return items.reduce<OffscreenHintItem[]>((result, item) => {
    const index = result.findIndex((candidate) => candidate.id === item.id)
    if (index < 0) return [...result, item]
    const current = result[index]
    const merged = {
      ...current,
      rightRpx: Math.max(current.rightRpx, item.rightRpx),
      bottomRpx: Math.max(current.bottomRpx, item.bottomRpx),
      weight: Math.max(current.weight, item.weight),
    }
    return [...result.slice(0, index), merged, ...result.slice(index + 1)]
  }, [])
}

export function countOffscreenRight(
  items: OffscreenHintItem[],
  visibleRightRpx: number,
  toleranceRpx = 16,
): number {
  const boundary = visibleRightRpx + toleranceRpx
  return items.reduce(
    (count, item) => count + (item.rightRpx > boundary ? normalizedWeight(item.weight) : 0),
    0,
  )
}

export function countOffscreenBottom(
  items: OffscreenHintItem[],
  visibleBottomRpx: number,
  toleranceRpx = 16,
): number {
  const boundary = visibleBottomRpx + toleranceRpx
  return items.reduce(
    (count, item) => count + (item.bottomRpx > boundary ? normalizedWeight(item.weight) : 0),
    0,
  )
}

function normalizedWeight(weight: number): number {
  return Number.isFinite(weight) ? Math.max(1, Math.round(weight)) : 1
}
