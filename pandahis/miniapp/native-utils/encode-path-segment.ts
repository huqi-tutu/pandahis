/**
 * 将页面 query 中的 id 安全编码进 REST 路径。
 * navigateTo(buildUrl) 已对 query 做过 encodeURIComponent；部分环境下 onLoad 仍得到带 %XX 的字符串，
 * 若再 encodeURIComponent 会把 % 编成 %25（双重编码），与库中 id 不一致并导致 404/500。
 */
export function encodePathSegment(fromQuery: string): string {
  let s = fromQuery
  for (let i = 0; i < 3; i++) {
    try {
      const d = decodeURIComponent(s)
      if (d === s) break
      s = d
    } catch {
      break
    }
  }
  return encodeURIComponent(s)
}
