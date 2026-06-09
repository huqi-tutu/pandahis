/**
 * 史略详情朗读：优先微信同声传译插件 TTS + InnerAudioContext 原生播放；
 * 插件不可用时回退服务端合成 MP3。
 */

import { request } from './api'

export type NarrationState = 'idle' | 'loading' | 'playing' | 'paused'

/** 微信同声传译插件（需在公众平台添加插件 wx069ba97219f66d99） */
type WechatSIPlugin = {
  textToSpeech: (opts: {
    lang: string
    content: string
    tts?: boolean
    success?: (res: { filename: string; retcode?: number }) => void
    fail?: (res: { retcode?: number; msg?: string }) => void
  }) => void
}

const CHUNK_MAX = 180
const TEXT_MAX = 6000

let audio: WechatMiniprogram.InnerAudioContext | null = null
let chunks: string[] = []
let chunkIndex = 0
let aborted = false
let state: NarrationState = 'idle'
let onStateChange: ((s: NarrationState) => void) | null = null
let onProgressChange: ((p: { progress: number; current: string; duration: string }) => void) | null = null
let wechatSIChecked = false
let wechatSIAvailable = false

function formatMmSs(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s < 10 ? '0' : ''}${s}`
}

function emitProgress(currentSec = 0, durationSec = 0) {
  const dur = durationSec > 0 ? durationSec : 1
  const chunkPart = chunks.length ? chunkIndex / chunks.length : 0
  const innerPart = Math.min(1, currentSec / dur) / (chunks.length || 1)
  const progress = Math.min(100, Math.round((chunkPart + innerPart) * 100))
  onProgressChange?.({
    progress,
    current: formatMmSs(currentSec),
    duration: formatMmSs(durationSec),
  })
}

function setState(next: NarrationState) {
  state = next
  onStateChange?.(next)
}

function friendlyTtsError(raw: string): string {
  const msg = String(raw || '')
  if (/REQUEST_FAIL|timeout|connect/i.test(msg)) {
    return '无法连接朗读服务，请检查网络或稍后重试'
  }
  if (/插件|WechatSI|requirePlugin/i.test(msg)) {
    return '请在微信公众平台为小程序添加「微信同声传译」插件后重试'
  }
  if (/INTERNAL_ERROR|语音合成|-20003/i.test(msg)) {
    return '语音合成失败，请缩短内容或稍后重试'
  }
  return msg.length > 32 ? `${msg.slice(0, 30)}…` : msg || '朗读失败'
}

function checkWechatSI(): boolean {
  if (wechatSIChecked) return wechatSIAvailable
  wechatSIChecked = true
  try {
    const plugin = requirePlugin('WechatSI') as WechatSIPlugin
    wechatSIAvailable = Boolean(plugin && typeof plugin.textToSpeech === 'function')
  } catch {
    wechatSIAvailable = false
  }
  return wechatSIAvailable
}

function textToSpeechNative(content: string): Promise<string> {
  return new Promise((resolve, reject) => {
    let plugin: WechatSIPlugin
    try {
      plugin = requirePlugin('WechatSI') as WechatSIPlugin
    } catch (e) {
      reject(new Error('未加载微信同声传译插件'))
      return
    }
    plugin.textToSpeech({
      lang: 'zh_CN',
      tts: true,
      content,
      success: (res) => {
        const file = res?.filename
        if (file) resolve(file)
        else reject(new Error(`语音合成失败(${res?.retcode ?? 'unknown'})`))
      },
      fail: (res) => {
        reject(new Error(res?.msg || `语音合成失败(${res?.retcode ?? 'fail'})`))
      },
    })
  })
}

function writeMp3TempFile(base64: string): Promise<string> {
  const fs = wx.getFileSystemManager()
  const path = `${wx.env.USER_DATA_PATH}/tts_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.mp3`
  return new Promise((resolve, reject) => {
    fs.writeFile({
      filePath: path,
      data: base64,
      encoding: 'base64',
      success: () => resolve(path),
      fail: (err) => reject(new Error(err?.errMsg || '写入语音文件失败')),
    })
  })
}

async function textToSpeechBackend(content: string): Promise<string> {
  const res = await request<{ audioBase64: string; mimeType?: string }>('/narration/synthesize', {
    method: 'POST',
    data: { text: content },
  })
  const b64 = res.data?.audioBase64
  if (!b64) throw new Error('语音合成结果为空')
  return writeMp3TempFile(b64)
}

async function synthesizeChunk(content: string): Promise<string> {
  if (checkWechatSI()) {
    try {
      return await textToSpeechNative(content)
    } catch {
      /* 插件失败时回退服务端 */
    }
  }
  return textToSpeechBackend(content)
}

/** 按句号/换行切分，单段不超过 CHUNK_MAX 字 */
export function chunkTextForTts(text: string, maxLen = CHUNK_MAX): string[] {
  const normalized = String(text || '')
    .replace(/\r\n/g, '\n')
    .replace(/[#*_`>\[\]()]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!normalized) return []

  const parts: string[] = []
  let seg = ''
  for (const ch of normalized) {
    seg += ch
    if ('。！？；\n'.includes(ch)) {
      const t = seg.trim()
      if (t) parts.push(t)
      seg = ''
    }
  }
  const tail = seg.trim()
  if (tail) parts.push(tail)

  const out: string[] = []
  let buf = ''
  const flush = () => {
    if (buf.trim()) out.push(buf.trim())
    buf = ''
  }
  for (const part of parts) {
    if (part.length > maxLen) {
      flush()
      for (let i = 0; i < part.length; i += maxLen) {
        out.push(part.slice(i, i + maxLen))
      }
      continue
    }
    if (buf.length + part.length <= maxLen) {
      buf += part
    } else {
      flush()
      buf = part
    }
  }
  flush()
  return out
}

export function buildBoxNarrationScript(opts: {
  title?: string
  meta?: string
  paragraphs?: string[]
  blurb?: string | null
}): string {
  const parts: string[] = []
  const title = String(opts.title || '').trim()
  if (title) parts.push(title)
  const meta = String(opts.meta || '')
    .replace(/\s*·\s*/g, '，')
    .replace(/\s*—\s*/g, '至')
    .trim()
  if (meta) parts.push(meta)
  const paras = (opts.paragraphs || []).map((p) => String(p || '').trim()).filter(Boolean)
  if (paras.length) parts.push(...paras)
  else {
    const blurb = String(opts.blurb || '').trim()
    if (blurb) parts.push(blurb)
  }
  let text = parts.join('。')
  if (text && !/[。！？]$/.test(text)) text += '。'
  if (text.length > TEXT_MAX) text = `${text.slice(0, TEXT_MAX)}……`
  return text
}

function destroyAudio() {
  if (!audio) return
  try {
    audio.stop()
    audio.destroy()
  } catch {
    /* ignore */
  }
  audio = null
}

function ensureAudio() {
  if (audio) return
  audio = wx.createInnerAudioContext()
  audio.obeyMuteSwitch = false
  audio.autoplay = false

  audio.onEnded(() => {
    if (aborted) return
    chunkIndex += 1
    void playNextChunk()
  })

  audio.onTimeUpdate(() => {
    if (aborted || !audio) return
    emitProgress(audio.currentTime || 0, audio.duration || 0)
  })

  audio.onError((err) => {
    if (aborted) return
    console.error('[narration] play error', err)
    stopNarration()
    wx.showToast({ title: '播放失败', icon: 'none' })
  })
}

function playFile(filename: string) {
  ensureAudio()
  if (!audio || aborted) return

  const playNow = () => {
    if (aborted || !audio) return
    setState('playing')
    try {
      audio.play()
    } catch (e) {
      console.error('[narration] play()', e)
      stopNarration()
      wx.showToast({ title: '播放失败', icon: 'none' })
    }
  }

  audio.offCanplay?.()
  audio.onCanplay(playNow)
  audio.src = filename

  // 部分机型 onCanplay 不触发，兜底直接 play
  setTimeout(() => {
    if (!aborted && state === 'loading' && audio) {
      playNow()
    }
  }, 400)
}

async function playNextChunk() {
  if (aborted) return
  if (chunkIndex >= chunks.length) {
    stopNarration()
    return
  }
  setState('loading')
  const content = chunks[chunkIndex]
  try {
    const filename = await synthesizeChunk(content)
    if (aborted) return
    playFile(filename)
  } catch (e) {
    stopNarration()
    const raw = e instanceof Error ? e.message : String(e)
    throw new Error(friendlyTtsError(raw))
  }
}

export function getNarrationState(): NarrationState {
  return state
}

export function stopNarration() {
  aborted = true
  chunks = []
  chunkIndex = 0
  destroyAudio()
  onProgressChange = null
  setState('idle')
}

export function pauseNarration() {
  if (!audio || state !== 'playing') return
  try {
    audio.pause()
  } catch {
    /* ignore */
  }
  setState('paused')
}

export function resumeNarration() {
  if (!audio || state !== 'paused') return
  try {
    audio.play()
  } catch {
    /* ignore */
  }
  setState('playing')
}

export async function startNarration(
  text: string,
  stateCb: (s: NarrationState) => void,
  progressCb?: (p: { progress: number; current: string; duration: string }) => void
): Promise<void> {
  stopNarration()
  aborted = false
  onStateChange = stateCb
  onProgressChange = progressCb || null

  chunks = chunkTextForTts(text)
  if (!chunks.length) throw new Error('暂无正文可朗读')

  chunkIndex = 0
  setState('loading')
  await playNextChunk()
}

export function toggleNarrationPlayback(): NarrationState {
  if (state === 'playing') {
    pauseNarration()
  } else if (state === 'paused') {
    resumeNarration()
  }
  return state
}
