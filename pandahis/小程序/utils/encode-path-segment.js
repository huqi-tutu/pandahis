function encodePathSegment(fromQuery) {
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

module.exports = { encodePathSegment }
