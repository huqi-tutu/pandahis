/** 摘录分享海报 · Canvas 2D 绘制（参考微信读书深色摘录卡） */

export type SharePosterPayload = {
  quoteText: string
  userName: string
  userAvatarUrl?: string
  sourceLine1?: string
  sourceLine2?: string
  excerptDate?: string
  brandName?: string
  qrImagePath?: string
}

const POSTER_W = 750
const POSTER_H = 1150
const DPR = 2

const COLORS = {
  bg: '#2A2420',
  quote: '#D4C19C',
  name: '#E8DFD0',
  meta: '#9A8E82',
  divider: 'rgba(255,255,255,0.14)',
  qrBg: '#F5F0E8',
  avatarFallback: '#4A3F3F',
}

const QR_IMAGE_PATH = '/images/miniapp-qrcode.png'
const BRAND_SLOGAN = '时间・空间・文明'

function formatExcerptDate(input?: string): string {
  if (input) return input
  const now = new Date()
  return `${now.getFullYear()}/${now.getMonth() + 1}/${now.getDate()}`
}

/** 远程头像先下载到本地，避免 canvas 绘制外链失败 */
async function resolveLocalImageSrc(src: string): Promise<string> {
  const url = String(src || '').trim()
  if (!url) return ''
  if (!(url.startsWith('http://') || url.startsWith('https://'))) return url
  return new Promise((resolve) => {
    wx.downloadFile({
      url,
      success: (res) => {
        resolve(res.statusCode === 200 && res.tempFilePath ? res.tempFilePath : '')
      },
      fail: () => resolve(''),
    })
  })
}

function loadCanvasImage(canvas: WechatMiniprogram.Canvas, src: string): Promise<WechatMiniprogram.Image | null> {
  return new Promise(async (resolve) => {
    const localSrc = await resolveLocalImageSrc(src)
    if (!localSrc) {
      resolve(null)
      return
    }
    const img = canvas.createImage()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = localSrc
  })
}

function wrapTextLines(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  maxLines: number,
): string[] {
  const source = String(text || '').trim()
  if (!source) return ['']
  const lines: string[] = []
  let current = ''
  for (const ch of source) {
    const next = current + ch
    if (ctx.measureText(next).width > maxWidth && current) {
      lines.push(current)
      current = ch
      if (lines.length >= maxLines) break
    } else {
      current = next
    }
  }
  if (lines.length < maxLines && current) lines.push(current)
  if (lines.length >= maxLines && lines.join('').length < source.length) {
    const last = lines[maxLines - 1]
    let trimmed = last
    while (trimmed.length > 1 && ctx.measureText(`${trimmed}…`).width > maxWidth) {
      trimmed = trimmed.slice(0, -1)
    }
    lines[maxLines - 1] = `${trimmed}…`
  }
  return lines
}

function drawRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  const radius = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.arcTo(x + w, y, x + w, y + h, radius)
  ctx.arcTo(x + w, y + h, x, y + h, radius)
  ctx.arcTo(x, y + h, x, y, radius)
  ctx.arcTo(x, y, x + w, y, radius)
  ctx.closePath()
}

function drawAvatarFallback(ctx: CanvasRenderingContext2D, x: number, y: number, size: number, name: string) {
  ctx.save()
  ctx.beginPath()
  ctx.arc(x + size / 2, y + size / 2, size / 2, 0, Math.PI * 2)
  ctx.fillStyle = COLORS.avatarFallback
  ctx.fill()
  ctx.fillStyle = '#FFFFFF'
  ctx.font = `600 ${Math.round(size * 0.42)}px "PingFang SC", sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText((name || '读').charAt(0), x + size / 2, y + size / 2 + 1)
  ctx.restore()
}

function drawQrPlaceholder(ctx: CanvasRenderingContext2D, x: number, y: number, size: number) {
  drawRoundRect(ctx, x, y, size, size, 12)
  ctx.fillStyle = COLORS.qrBg
  ctx.fill()
  ctx.strokeStyle = 'rgba(74,63,63,0.18)'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.fillStyle = COLORS.avatarFallback
  ctx.font = '600 22px "PingFang SC", sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('扫码阅读', x + size / 2, y + size / 2)
}

export async function renderSharePosterToCanvas(
  canvas: WechatMiniprogram.Canvas,
  payload: SharePosterPayload,
): Promise<string> {
  const quoteText = String(payload.quoteText || '').trim()
  const userName = String(payload.userName || '历史读者').trim() || '历史读者'
  const sourceLine1 = String(payload.sourceLine1 || '').trim()
  const sourceLine2 = String(payload.sourceLine2 || '').trim()
  const excerptDate = formatExcerptDate(payload.excerptDate)
  const brandName = String(payload.brandName || '历史图谱').trim() || '历史图谱'

  canvas.width = POSTER_W * DPR
  canvas.height = POSTER_H * DPR

  const ctx = canvas.getContext('2d') as unknown as CanvasRenderingContext2D
  ctx.scale(DPR, DPR)

  ctx.fillStyle = COLORS.bg
  ctx.fillRect(0, 0, POSTER_W, POSTER_H)

  const pad = 56
  const avatarSize = 96
  let cursorY = pad + 12

  // —— 顶部用户区：头像 → 昵称 → 摘录时间，全部左对齐上下排列 ——
  const avatarImg = await loadCanvasImage(canvas, payload.userAvatarUrl || '')
  ctx.save()
  ctx.beginPath()
  ctx.arc(pad + avatarSize / 2, cursorY + avatarSize / 2, avatarSize / 2, 0, Math.PI * 2)
  ctx.clip()
  if (avatarImg) {
    ctx.drawImage(avatarImg as unknown as CanvasImageSource, pad, cursorY, avatarSize, avatarSize)
  } else {
    drawAvatarFallback(ctx, pad, cursorY, avatarSize, userName)
  }
  ctx.restore()
  cursorY += avatarSize + 20

  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillStyle = COLORS.name
  ctx.font = '600 32px "Songti SC", "STSong", "Noto Serif SC", serif'
  ctx.fillText(userName, pad, cursorY)
  cursorY += 40

  ctx.fillStyle = COLORS.meta
  ctx.font = '22px "PingFang SC", sans-serif'
  ctx.fillText(`摘录于 ${excerptDate}`, pad, cursorY)
  cursorY += 56

  // —— 摘录正文：左对齐，自用户区下方自然向下排 ——
  ctx.fillStyle = COLORS.quote
  ctx.font = '700 34px "Songti SC", "STSong", "Noto Serif SC", serif'
  const quoteMaxWidth = POSTER_W - pad * 2
  const quoteLines = wrapTextLines(ctx, quoteText, quoteMaxWidth, 10)
  const quoteLineHeight = 58
  quoteLines.forEach((line, index) => {
    ctx.fillText(line, pad, cursorY + index * quoteLineHeight)
  })
  cursorY += quoteLines.length * quoteLineHeight + 48

  // —— 来源路径：左对齐 ——
  const pathLine =
    sourceLine1 ||
    [sourceLine2].filter(Boolean).join('') ||
    ''
  if (pathLine) {
    ctx.fillStyle = COLORS.meta
    ctx.font = '24px "PingFang SC", sans-serif'
    const pathLines = wrapTextLines(ctx, pathLine, quoteMaxWidth, 2)
    pathLines.forEach((line, index) => {
      ctx.fillText(line, pad, cursorY + index * 34)
    })
  }

  // —— 底部：分割线 + 左侧品牌（含 slogan）与右侧二维码垂直居中 ——
  const qrSize = 120
  const footerInnerPad = 28
  const footerTop = POSTER_H - pad - qrSize - footerInnerPad * 2

  ctx.strokeStyle = COLORS.divider
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(pad, footerTop)
  ctx.lineTo(POSTER_W - pad, footerTop)
  ctx.stroke()

  const qrX = POSTER_W - pad - qrSize
  const qrY = footerTop + footerInnerPad
  const qrCenterY = qrY + qrSize / 2

  const brandFontSize = 30
  const sloganFontSize = 20
  const brandGap = 10
  const brandBlockH = brandFontSize + brandGap + sloganFontSize
  const brandTop = qrCenterY - brandBlockH / 2

  ctx.textAlign = 'left'
  ctx.textBaseline = 'top'
  ctx.fillStyle = COLORS.name
  ctx.font = `600 ${brandFontSize}px "PingFang SC", "Songti SC", sans-serif`
  ctx.fillText(brandName, pad, brandTop)

  ctx.fillStyle = COLORS.meta
  ctx.font = `${sloganFontSize}px "PingFang SC", sans-serif`
  ctx.fillText(BRAND_SLOGAN, pad, brandTop + brandFontSize + brandGap)

  const qrImg = await loadCanvasImage(canvas, payload.qrImagePath || QR_IMAGE_PATH)
  if (qrImg) {
    drawRoundRect(ctx, qrX - 6, qrY - 6, qrSize + 12, qrSize + 12, 10)
    ctx.fillStyle = COLORS.qrBg
    ctx.fill()
    ctx.drawImage(qrImg as unknown as CanvasImageSource, qrX, qrY, qrSize, qrSize)
  } else {
    drawQrPlaceholder(ctx, qrX, qrY, qrSize)
  }

  return new Promise((resolve, reject) => {
    wx.canvasToTempFilePath({
      canvas: canvas as unknown as WechatMiniprogram.Canvas,
      fileType: 'png',
      quality: 1,
      success: (res) => resolve(res.tempFilePath),
      fail: (err) => reject(err),
    })
  })
}

export async function ensureAlbumWriteAuth(): Promise<boolean> {
  return new Promise((resolve) => {
    wx.getSetting({
      success: (res) => {
        if (res.authSetting['scope.writePhotosAlbum']) {
          resolve(true)
          return
        }
        wx.authorize({
          scope: 'scope.writePhotosAlbum',
          success: () => resolve(true),
          fail: () => {
            wx.showModal({
              title: '需要相册权限',
              content: '保存海报需要访问相册，请在设置中开启权限。',
              confirmText: '去设置',
              success: (modalRes) => {
                if (modalRes.confirm) wx.openSetting({})
              },
            })
            resolve(false)
          },
        })
      },
      fail: () => resolve(false),
    })
  })
}

export async function savePosterToAlbum(filePath: string): Promise<void> {
  const ok = await ensureAlbumWriteAuth()
  if (!ok) throw new Error('未授权相册权限')
  await new Promise<void>((resolve, reject) => {
    wx.saveImageToPhotosAlbum({
      filePath,
      success: () => resolve(),
      fail: (err) => reject(err),
    })
  })
}

export function openPosterShareMenu(filePath: string): void {
  if (typeof wx.showShareImageMenu !== 'function') {
    wx.showToast({ title: '当前微信版本不支持图片分享', icon: 'none' })
    return
  }
  wx.showShareImageMenu({
    path: filePath,
    // 注意：点底部叉号关闭时，部分基础库会走 fail（如 cancel），
    // 此前在 fail 里调了 previewImage，会误进全屏看图；此处不再做任何回退。
    fail: () => {},
  })
}
