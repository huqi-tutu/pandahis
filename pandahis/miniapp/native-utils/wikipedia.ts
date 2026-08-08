import { request } from './api'

export type WikipediaLookupResult = {
  query: string
  found: boolean
  resolvedTitle: string | null
  paragraphs: string[]
  offset: number
  nextOffset: number | null
  hasMore: boolean
  totalParagraphs: number
}

export async function lookupWikipedia(
  query: string,
  offset = 0,
  limit = 3,
): Promise<WikipediaLookupResult> {
  const q = String(query || '').trim()
  if (!q) {
    return {
      query: '',
      found: false,
      resolvedTitle: null,
      paragraphs: [],
      offset: 0,
      nextOffset: null,
      hasMore: false,
      totalParagraphs: 0,
    }
  }
  const path =
    `/wikipedia/lookup?q=${encodeURIComponent(q)}`
    + `&offset=${Math.max(0, offset)}`
    + `&limit=${Math.max(1, Math.min(8, limit))}`
  const res = await request<WikipediaLookupResult>(path)
  return res.data
}
