-- 一级地域 Tab 图：腾讯云 COS 公网 URL（与 scripts/gen_civ_tab_pngs.py + COS MCP 上传路径一致）
UPDATE civilization_l1
SET tab_image_url = CONCAT(
    'https://pandahis-1300045339.cos.ap-chengdu.myqcloud.com/histomap/civ-tab/',
    code,
    '.png'
)
WHERE code IS NOT NULL AND status = 1;
