const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const htmlPath = path.join(__dirname, 'shang-card-visual.html');
const htmlExists = fs.existsSync(htmlPath);
const requiresTemplate = { skip: htmlExists ? false : '样板尚未创建' };

function readTemplate() {
  return fs.readFileSync(htmlPath, 'utf8');
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function tagWithAttribute(tag, attribute, value) {
  return new RegExp(
    `<${tag}\\b(?=[^>]*\\b${escapeRegExp(attribute)}=["']${escapeRegExp(value)}["'])[^>]*>`,
    'i',
  );
}

function variantRegion(html, variant) {
  const pattern = new RegExp(
    `<([a-z][\\w:-]*)\\b(?=[^>]*\\bdata-variant=["']${variant}["'])[^>]*>([\\s\\S]*?)<\\/\\1>`,
    'i',
  );
  const match = html.match(pattern);
  assert.ok(match, `应提供 ${variant} 方案区域`);
  return match[0];
}

test('待实现的商代卡片视觉样板已创建', () => {
  assert.ok(htmlExists, `样板尚未创建：${htmlPath}`);
});

test('声明中文页面标题和移动端 viewport', requiresTemplate, () => {
  const html = readTemplate();
  const title = html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i)?.[1].trim();

  assert.match(html, /<html\b[^>]*\blang=["']zh(?:-CN)?["'][^>]*>/i);
  assert.ok(title && /[\u3400-\u9fff]/u.test(title), '页面标题应包含中文');
  const viewport = html.match(/<meta\b(?=[^>]*\bname=["']viewport["'])[^>]*>/i)?.[0];
  assert.ok(viewport, '应声明 viewport');
  assert.match(viewport, /width=device-width/i);
  assert.match(viewport, /initial-scale=1(?:\.0)?/i);
});

test('提供浅色基线和无插画的增强色方案', requiresTemplate, () => {
  const html = readTemplate();
  const baseline = variantRegion(html, 'baseline');
  const enhanced = variantRegion(html, 'enhanced');

  assert.match(baseline, /(?:data-theme=["']light["']|class=["'][^"']*\blight\b[^"']*["'])/i);
  assert.doesNotMatch(baseline, /<(?:svg|img|picture|canvas)\b/i, '浅色基线不应包含插画');
  assert.doesNotMatch(enhanced, /<(?:svg|img|picture|canvas)\b/i, '增强色方案不应包含插画');
  assert.match(enhanced, /(?:data-tone=["']enhanced["']|class=["'][^"']*\benhanced\b[^"']*["'])/i);
});

for (const variant of ['museum', 'rubbing', 'wash']) {
  test(`${variant} 插画方案包含带可访问标题的 SVG`, requiresTemplate, () => {
    const region = variantRegion(readTemplate(), variant);
    const svg = region.match(/<svg\b[\s\S]*?<\/svg>/i)?.[0];

    assert.ok(svg, `${variant} 方案应包含 SVG 插画`);
    const titleMatch = svg.match(/<title\b([^>]*)>([^<]+)<\/title>/i);
    assert.ok(titleMatch?.[2].trim(), `${variant} SVG 应包含非空 title`);

    const titleId = titleMatch[1].match(/\bid=["']([^"']+)["']/i)?.[1];
    assert.ok(titleId, `${variant} SVG title 应具有 id`);
    const svgOpeningTag = svg.match(/^<svg\b[^>]*>/i)?.[0] ?? '';
    assert.match(svgOpeningTag, new RegExp(`\\baria-labelledby=["'][^"']*\\b${escapeRegExp(titleId)}\\b[^"']*["']`, 'i'));
  });
}

test('连续朝代列表至少依次包含夏、商、西周', requiresTemplate, () => {
  const html = readTemplate();
  const dynastyList = html.match(
    /<(?:ol|ul|nav)\b(?=[^>]*(?:data-dynasties|aria-label=["'][^"']*朝代))[^>]*>([\s\S]*?)<\/(?:ol|ul|nav)>/i,
  )?.[1];

  assert.ok(dynastyList, '应提供带语义标识的连续朝代列表');
  assert.match(dynastyList, /夏[\s\S]*商[\s\S]*西周/u);
});

test('提供 375px 与 320px 设备宽度按钮并暴露选中状态', requiresTemplate, () => {
  const html = readTemplate();

  for (const width of ['375', '320']) {
    assert.match(html, new RegExp(
      `<button\\b(?=[^>]*\\bdata-width=["']${width}["'])(?=[^>]*\\baria-pressed=["'](?:true|false)["'])[^>]*>`,
      'i',
    ));
  }
});

test('透明度控件由 range、output、默认值和 clamp 逻辑组成', requiresTemplate, () => {
  const html = readTemplate();
  const range = html.match(
    /<input\b(?=[^>]*\btype=["']range["'])(?=[^>]*\bid=["']([^"']+)["'])(?=[^>]*(?:data-opacity|name=["']opacity["']))(?=[^>]*\bmin=["'](?:0|0\.0+)["'])(?=[^>]*\bmax=["'](?:1|1\.0+|100)["'])(?=[^>]*\bvalue=["'](?:0(?:\.\d+)?|1(?:\.0+)?|\d{1,2}|100)["'])[^>]*>/i,
  );

  assert.ok(range, '应提供透明度 range 控件');
  const rangeId = range[1];
  assert.match(html, new RegExp(`<output\\b[^>]*\\bfor=["']${escapeRegExp(rangeId)}["'][^>]*>`, 'i'));

  const scripts = [...html.matchAll(/<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
    .map((match) => match[1])
    .join('\n');
  assert.match(scripts, /(?:const|let|var)\s+\w*(?:default|opacity)\w*\s*=\s*(?:0(?:\.\d+)?|1(?:\.0+)?|\d{1,3})\b/i, '脚本应声明透明度默认值');
  assert.match(scripts, /Math\.m(?:in|ax)\s*\([\s\S]*Math\.m(?:ax|in)\s*\(/, '脚本应使用上下界 clamp 逻辑');
  assert.match(scripts, new RegExp(`${escapeRegExp(rangeId)}|(?:querySelector|getElementById)\\s*\\([^)]*(?:opacity|range)`, 'i'), '透明度脚本应关联 range 控件');
  assert.match(scripts, /(?:textContent|value)\s*=|\.value\b/i, '透明度脚本应更新控件或 output');
});

test('五种 variant 均可通过按钮切换', requiresTemplate, () => {
  const html = readTemplate();
  const variants = ['baseline', 'enhanced', 'museum', 'rubbing', 'wash'];

  for (const variant of variants) {
    assert.match(html, new RegExp(
      `<button\\b(?=[^>]*\\bdata-variant-target=["']${variant}["'])(?=[^>]*\\baria-pressed=["'](?:true|false)["'])[^>]*>`,
      'i',
    ));
  }

  const declared = [...html.matchAll(/data-variant-target=["']([^"']+)["']/gi)].map((match) => match[1]);
  assert.deepEqual(new Set(declared), new Set(variants));
});

test('包含移动端媒体查询且不加载外部网络资源', requiresTemplate, () => {
  const html = readTemplate();

  assert.match(html, /@media\s*\([^)]*(?:max-width\s*:|width\s*<=)[^)]*\)/i);
  assert.doesNotMatch(html, /<(?:script|img|iframe|source|video|audio)\b[^>]*\bsrc=["'](?:https?:)?\/\//i);
  assert.doesNotMatch(html, /<link\b[^>]*\bhref=["'](?:https?:)?\/\//i);
  assert.doesNotMatch(html, /@import\s+(?:url\()?\s*["']?(?:https?:)?\/\//i);
  assert.doesNotMatch(html, /\b(?:fetch|import)\s*\(\s*["'](?:https?:)?\/\//i);
  assert.doesNotMatch(html, /url\(\s*["']?(?:https?:)?\/\//i);
  assert.doesNotMatch(html, /\b(?:srcset|poster|data|action)=["'](?:https?:)?\/\//i);
});

test('装饰 SVG 不拦截指针事件', requiresTemplate, () => {
  const html = readTemplate();
  const decorativeSvgs = [...html.matchAll(
    /<svg\b(?=[^>]*(?:aria-hidden=["']true["']|data-decorative(?:=["']true["'])?))[^>]*>/gi,
  )].map((match) => match[0]);

  assert.ok(decorativeSvgs.length > 0, '应至少包含一个明确标记的装饰 SVG');
  const hasInlineRule = decorativeSvgs.every((svg) => /(?:style=["'][^"']*pointer-events\s*:\s*none|class=["'][^"']*\bdecorative-svg\b)/i.test(svg));
  const hasClassRule = /\.decorative-svg\s*\{[^}]*pointer-events\s*:\s*none\b[^}]*\}/i.test(html);

  assert.ok(hasInlineRule && (hasClassRule || decorativeSvgs.every((svg) => /style=/i.test(svg))), '所有装饰 SVG 都应设置 pointer-events: none');
});
