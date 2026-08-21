export type NoteHighlightInput = {
  id: number
  selectedText: string
}

export type HighlightSeg = {
  text: string
  bold?: boolean
  highlight?: boolean
  noteId?: number
  anchorId?: string
  focus?: boolean
}

export function findHighlightMarks(plain: string, highlights: NoteHighlightInput[]): number[] {
  const marks = new Array(plain.length).fill(0)
  for (const h of highlights) {
    const needle = String(h.selectedText || '')
    if (!needle || !h.id) continue
    let from = 0
    while (from <= plain.length - needle.length) {
      const i = plain.indexOf(needle, from)
      if (i < 0) break
      for (let k = i; k < i + needle.length; k += 1) marks[k] = h.id
      from = i + 1
    }
  }
  return marks
}

export function applyHighlightsToPlain(
  plain: string,
  highlights: NoteHighlightInput[],
  focusNoteId?: number | null
): HighlightSeg[] {
  if (!plain) return []
  const marks = findHighlightMarks(plain, highlights)
  const segs: HighlightSeg[] = []
  let i = 0
  while (i < plain.length) {
    const noteId = marks[i] || 0
    let j = i + 1
    while (j < plain.length && (marks[j] || 0) === noteId) j += 1
    const text = plain.slice(i, j)
    if (noteId > 0) {
      segs.push({
        text,
        highlight: true,
        noteId,
        anchorId: `note-hl-${noteId}`,
        focus: !!focusNoteId && noteId === focusNoteId,
      })
    } else {
      segs.push({ text })
    }
    i = j
  }
  return segs
}

export function applyHighlightsToSegs(
  segs: Array<{ text: string; bold?: boolean }>,
  highlights: NoteHighlightInput[],
  focusNoteId?: number | null
): HighlightSeg[] {
  if (!segs.length) return []
  const plain = segs.map((s) => s.text).join('')
  if (!highlights.length) {
    return segs.map((s) => ({ text: s.text, bold: !!s.bold }))
  }
  const marks = findHighlightMarks(plain, highlights)
  const out: HighlightSeg[] = []
  let offset = 0
  for (const seg of segs) {
    const text = seg.text || ''
    let i = 0
    while (i < text.length) {
      const global = offset + i
      const noteId = marks[global] || 0
      let j = i + 1
      while (j < text.length && (marks[offset + j] || 0) === noteId) j += 1
      const slice = text.slice(i, j)
      if (noteId > 0) {
        out.push({
          text: slice,
          bold: !!seg.bold,
          highlight: true,
          noteId,
          anchorId: `note-hl-${noteId}`,
          focus: !!focusNoteId && noteId === focusNoteId,
        })
      } else {
        out.push({ text: slice, bold: !!seg.bold })
      }
      i = j
    }
    offset += text.length
  }
  return out
}

export function highlightAnchorId(noteId: number): string {
  return `note-hl-${noteId}`
}
