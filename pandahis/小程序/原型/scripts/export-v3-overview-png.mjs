/**
 * 导出 v3-原型总览.html 为单张纵向整页 PNG（约 2x DPR）。
 * 长页：分块 clip + sharp 拼接；导出前中和 sticky/fixed，避免重复条带。
 *
 * 依赖：本机 Google Chrome；npm i（playwright-core、sharp）
 * 运行：npm run export:v3-png
 */
import { chromium } from 'playwright-core';
import sharp from 'sharp';
import fs from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
/** 「原型」目录（本脚本上一级） */
const BASE = path.resolve(__dirname, '..');
const OUT = path.join(BASE, 'exports');

const JOBS = [{ html: 'v3-原型总览.html', png: 'v3-原型总览-全页-2x.png' }];

const DPR = 2;
const CHUNK_CSS = 3200;

function mkdirp(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

async function prepDom(page) {
  await page.evaluate(() => {
    const bar = document.getElementById('zoom-bar');
    if (bar) bar.style.setProperty('display', 'none', 'important');
    const vp = document.getElementById('proto-viewport');
    const wrap = document.getElementById('zoom-wrap');
    if (vp) {
      vp.style.setProperty('overflow', 'visible', 'important');
      vp.style.setProperty('height', 'auto', 'important');
      vp.style.setProperty('min-height', '0', 'important');
      vp.style.setProperty('flex', 'none', 'important');
      vp.style.setProperty('max-height', 'none', 'important');
    }
    if (wrap) {
      wrap.style.transform = 'none';
      wrap.style.willChange = 'auto';
      wrap.style.minWidth = '100%';
      wrap.style.width = 'max-content';
      wrap.style.marginBottom = '0';
    }
    document.documentElement.style.setProperty('height', 'auto', 'important');
    document.documentElement.style.setProperty('overflow', 'visible', 'important');
    document.body.style.setProperty('height', 'auto', 'important');
    document.body.style.setProperty('min-height', '0', 'important');
    document.body.style.setProperty('display', 'block', 'important');
    document.body.style.setProperty('overflow', 'visible', 'important');

    const root = document.getElementById('zoom-wrap') || document.body;
    root.querySelectorAll('*').forEach((el) => {
      let pos;
      try {
        pos = getComputedStyle(el).position;
      } catch {
        return;
      }
      if (pos === 'sticky' || pos === 'fixed') {
        if (!el.dataset._exportPos) el.dataset._exportPos = el.getAttribute('style') || '';
        el.style.setProperty('position', 'static', 'important');
        el.style.setProperty('box-shadow', 'none', 'important');
        el.style.setProperty('z-index', 'auto', 'important');
      }
    });
  });
  await page.evaluate(
    () =>
      new Promise((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(resolve));
      }),
  );
  await page.waitForTimeout(500);
  await page.evaluate(() => {
    void document.body.offsetHeight;
    void document.documentElement.offsetHeight;
  });
}

async function measure(page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const body = document.body;
    const wrap = document.getElementById('zoom-wrap');
    const w = Math.max(
      doc.scrollWidth,
      body.scrollWidth,
      wrap ? wrap.scrollWidth : 0,
      wrap ? wrap.offsetWidth : 0,
    );
    const h = Math.max(
      doc.scrollHeight,
      body.scrollHeight,
      wrap ? wrap.scrollHeight : 0,
      wrap ? wrap.offsetHeight : 0,
    );
    return { w: Math.ceil(w), h: Math.ceil(h) };
  });
}

async function verticalStitch(buffers, outPath) {
  const metas = [];
  for (const b of buffers) {
    const meta = await sharp(b).metadata();
    metas.push({ b, width: meta.width, height: meta.height });
  }
  const width = Math.max(...metas.map((m) => m.width));
  const height = metas.reduce((s, m) => s + m.height, 0);
  let top = 0;
  const composite = [];
  for (const m of metas) {
    composite.push({ input: m.b, top, left: 0 });
    top += m.height;
  }
  await sharp({
    create: {
      width,
      height,
      channels: 4,
      background: { r: 247, g: 243, b: 239, alpha: 1 },
    },
  })
    .composite(composite)
    .png({ compressionLevel: 6 })
    .toFile(outPath);
}

async function exportOne(browser, job) {
  const context = await browser.newContext({
    locale: 'zh-CN',
    deviceScaleFactor: DPR,
  });
  const page = await context.newPage();
  const url = pathToFileURL(path.join(BASE, job.html)).href;
  await page.goto(url, { waitUntil: 'load', timeout: 180000 });
  await page.waitForTimeout(2000);
  await prepDom(page);
  let { w: totalW, h: totalH } = await measure(page);
  if (totalH < 400) totalH = 800;
  if (totalW < 400) totalW = 1200;

  const vw = Math.min(totalW + 64, 16000);
  const vh = Math.min(CHUNK_CSS, 8000);
  await page.setViewportSize({ width: vw, height: vh });

  const buffers = [];
  for (let y = 0; y < totalH; y += vh) {
    const sliceCss = Math.min(vh, totalH - y);
    await page.evaluate((yy) => window.scrollTo(0, yy), y);
    await page.waitForTimeout(150);
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    const buf = await page.screenshot({
      type: 'png',
      clip: { x: 0, y: 0, width: vw, height: sliceCss },
    });
    buffers.push(buf);
  }
  await context.close();

  const outPath = path.join(OUT, job.png);
  await verticalStitch(buffers, outPath);
  const st = fs.statSync(outPath);
  const meta = await sharp(outPath).metadata();
  console.log('OK', outPath, `${meta.width}×${meta.height}`, Math.round(st.size / 1024), 'KB');
}

mkdirp(OUT);
const browser = await chromium.launch({
  channel: 'chrome',
  headless: true,
});
try {
  for (const job of JOBS) {
    await exportOne(browser, job);
  }
} finally {
  await browser.close();
}
