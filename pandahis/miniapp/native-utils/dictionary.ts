import { request } from './api'

export type DictionaryEntry = {
  character: string
  pinyin: string | null
}

export type DictionaryLookupResult = {
  query: string
  entries: DictionaryEntry[]
}

export async function lookupDictionary(query: string): Promise<DictionaryLookupResult> {
  const q = String(query || '').trim()
  if (!q) {
    return { query: '', entries: [] }
  }
  const res = await request<DictionaryLookupResult>(`/dictionary/lookup?q=${encodeURIComponent(q)}`)
  return res.data
}
