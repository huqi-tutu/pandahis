import { lookupDictionary, type DictionaryEntry } from '../../native-utils/dictionary'
import { lookupWikipedia } from '../../native-utils/wikipedia'

type EntryVm = {
  character: string
  pinyin: string
}

const HAN_CHAR_RE = /[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]/
const PINYIN_MAX_CHARS = 4
const WIKI_PAGE_LIMIT = 3

function extractHanChars(text: string): string[] {
  return Array.from(text).filter((ch) => HAN_CHAR_RE.test(ch))
}

function toEntries(result: { entries?: DictionaryEntry[] }, query: string): EntryVm[] {
  const fallbackChars = extractHanChars(query).slice(0, PINYIN_MAX_CHARS)
  const raw = result.entries || []
  if (raw.length > 0) {
    return raw.slice(0, PINYIN_MAX_CHARS).map((entry, index) => ({
      character: String(entry.character || '').trim() || fallbackChars[index] || '',
      pinyin: entry.pinyin || '暂无读音',
    }))
  }
  return fallbackChars.map((ch) => ({ character: ch, pinyin: '暂无读音' }))
}

function formatPinyinError(err: unknown): string {
  const message = err instanceof Error ? err.message : ''
  if (/not found/i.test(message) || message === 'NOT_FOUND') {
    return '读音服务尚未上线到当前环境'
  }
  if (message === 'UNAUTHORIZED') {
    return '需要登录后再查询读音'
  }
  return message || '读音查询失败'
}

function formatWikiError(err: unknown): string {
  const message = err instanceof Error ? err.message : ''
  if (message === 'UNAUTHORIZED') {
    return '需要登录后再查询百科'
  }
  return message || '百科查询失败'
}

function formatPinyinTexts(entries: EntryVm[]) {
  return {
    pinyinCharsText: entries.map((e) => e.character).join(''),
    pinyinReadingsText: entries.map((e) => e.pinyin).join(' '),
  }
}

function resetState(queryDisplay = '') {
  return {
    queryDisplay,
    showPinyin: false,
    pinyinLoading: false,
    pinyinError: '',
    pinyinEntries: [] as EntryVm[],
    pinyinCharsText: '',
    pinyinReadingsText: '',
    wikiLoading: false,
    wikiLoadingMore: false,
    wikiError: '',
    wikiEmpty: false,
    wikiTitle: '',
    wikiParagraphs: [] as string[],
    wikiHasMore: false,
    wikiNextOffset: null as number | null,
  }
}

Component({
  properties: {
    visible: {
      type: Boolean,
      value: false,
    },
    query: {
      type: String,
      value: '',
    },
  },
  data: resetState(),
  observers: {
    'visible, query': function handleVisibleQuery(visible: boolean, query: string) {
      if (!visible) {
        this.setData(resetState())
        this._fetchSeq = (this._fetchSeq || 0) + 1
        return
      }
      const text = String(query || '').trim()
      if (!text) {
        this.setData({
          ...resetState(),
          wikiEmpty: true,
          wikiError: '请先选中要查询的文字',
        })
        return
      }
      this.openLookup(text)
    },
  },
  lifetimes: {
    created() {
      this._fetchSeq = 0
    },
  },
  methods: {
    noop() {},
    onBackdropTap() {
      this.triggerEvent('close')
    },
    onClose() {
      this.triggerEvent('close')
    },
    onWikiScrollToLower() {
      void this.loadMoreWiki()
    },
    openLookup(text: string) {
      const seq = (this._fetchSeq || 0) + 1
      this._fetchSeq = seq

      const hanChars = extractHanChars(text)
      const showPinyin = hanChars.length > 0 && hanChars.length <= PINYIN_MAX_CHARS

      this.setData({
        ...resetState(text),
        showPinyin,
        pinyinLoading: showPinyin,
        wikiLoading: true,
      })

      if (showPinyin) {
        void this.fetchPinyin(text, seq)
      }
      void this.fetchWiki(text, 0, false, seq)
    },
    async fetchPinyin(text: string, seq: number) {
      try {
        const result = await lookupDictionary(text)
        if (seq !== this._fetchSeq) return
        const entries = toEntries(result, text)
        this.setData({
          pinyinLoading: false,
          pinyinEntries: entries,
          ...formatPinyinTexts(entries),
          pinyinError: entries.length === 0 ? '未找到可查询的汉字' : '',
        })
      } catch (err: unknown) {
        if (seq !== this._fetchSeq) return
        this.setData({
          pinyinLoading: false,
          pinyinEntries: [],
          pinyinCharsText: '',
          pinyinReadingsText: '',
          pinyinError: formatPinyinError(err),
        })
      }
    },
    async fetchWiki(text: string, offset: number, append: boolean, seq: number) {
      try {
        const result = await lookupWikipedia(text, offset, WIKI_PAGE_LIMIT)
        if (seq !== this._fetchSeq) return

        if (!result.found) {
          if (append) {
            // 翻页失败时保留已展示段落，避免被空态盖住
            this.setData({
              wikiLoading: false,
              wikiLoadingMore: false,
              wikiEmpty: false,
              wikiHasMore: false,
              wikiNextOffset: null,
            })
            return
          }
          this.setData({
            wikiLoading: false,
            wikiLoadingMore: false,
            wikiEmpty: true,
            wikiError: '',
            wikiTitle: '',
            wikiParagraphs: [],
            wikiHasMore: false,
            wikiNextOffset: null,
          })
          return
        }

        const nextParagraphs = append
          ? this.data.wikiParagraphs.concat(result.paragraphs || [])
          : (result.paragraphs || [])

        this.setData({
          wikiLoading: false,
          wikiLoadingMore: false,
          wikiEmpty: nextParagraphs.length === 0,
          wikiError: '',
          wikiTitle: result.resolvedTitle || this.data.wikiTitle || '',
          wikiParagraphs: nextParagraphs,
          wikiHasMore: !!result.hasMore,
          wikiNextOffset: result.nextOffset,
        })

        // 内容过短滚不动时，自动续载下一段，避免 hasMore 卡住
        if (result.hasMore && nextParagraphs.length < 6) {
          setTimeout(() => {
            if (seq === this._fetchSeq) {
              void this.loadMoreWiki()
            }
          }, 0)
        }
      } catch (err: unknown) {
        if (seq !== this._fetchSeq) return
        if (append) {
          this.setData({
            wikiLoading: false,
            wikiLoadingMore: false,
            wikiEmpty: false,
            wikiHasMore: false,
            wikiNextOffset: null,
          })
          return
        }
        this.setData({
          wikiLoading: false,
          wikiLoadingMore: false,
          wikiEmpty: true,
          wikiError: formatWikiError(err),
          wikiHasMore: false,
        })
      }
    },
    async loadMoreWiki() {
      if (
        this.data.wikiLoading
        || this.data.wikiLoadingMore
        || !this.data.wikiHasMore
        || this.data.wikiNextOffset == null
      ) {
        return
      }
      const text = String(this.data.queryDisplay || '').trim()
      if (!text) return
      const seq = this._fetchSeq || 0
      const offset = this.data.wikiNextOffset
      this.setData({ wikiLoadingMore: true })
      await this.fetchWiki(text, offset, true, seq)
    },
  },
})
