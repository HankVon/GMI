-- 聚焦川藏(四川+西藏): 移除非川藏省份扩充源、启用川藏禁用源、新增川藏深度源
-- 可重复执行(新增部分按 name 去重)

-- 1) 软删除非川藏的省级扩充源(仅保留四川/西藏)
UPDATE web_source SET is_deleted=1, updated_at=NOW()
WHERE id IN (41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,58,59,61,62,63,64,65,66) AND is_deleted=0;

-- 2) 启用川藏已有的禁用源(intent 模式)
UPDATE web_source SET enabled=1, updated_at=NOW()
WHERE id IN (12,13,14,15,16,18,19,20,21,22,23,24) AND is_deleted=0;

-- 3) 修正乱码名称
UPDATE web_source SET name='四川省水利厅-公示公告' WHERE id=22 AND is_deleted=0;
UPDATE web_source SET name='四川省应急厅-公示公告' WHERE id=23 AND is_deleted=0;

-- 4) 新增川藏深度源(通用 crawl)
INSERT INTO web_source (name, url, description, allow_domains, keywords, exclude_keywords, regions, scrape_mode, max_depth, max_pages, llm_enhance, enabled, is_deleted, created_at, updated_at)
SELECT * FROM (
  SELECT '四川省交通运输厅' AS name, 'https://jtt.sc.gov.cn/' AS url, '四川省交通运输厅招投标/公示' AS description, 'jtt.sc.gov.cn' AS allow_domains, '矿业,地质,资源,招标,中标,工程,采购' AS keywords, '' AS exclude_keywords, '四川' AS regions, 'crawl' AS scrape_mode, 1 AS max_depth, 30 AS max_pages, 'filter' AS llm_enhance, 1 AS enabled, 0 AS is_deleted, NOW() AS created_at, NOW() AS updated_at
  UNION ALL SELECT '四川省经济和信息化厅', 'https://jxt.sc.gov.cn/', '四川省经信厅项目/公示', 'jxt.sc.gov.cn', '矿业,资源,招标,工程,采购', '', '四川', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '成都市公共资源交易', 'https://www.cdggzy.com/', '成都市公共资源交易', 'cdggzy.com', '矿业,采矿,探矿,资源,出让,招标,中标,工程', '', '四川,成都', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '德阳市公共资源交易', 'http://ggzy.deyang.gov.cn/', '德阳市公共资源交易', 'deyang.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '四川,德阳', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '宜宾市公共资源交易', 'http://ggzy.yibin.gov.cn/', '宜宾市公共资源交易', 'yibin.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '四川,宜宾', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '攀枝花市公共资源交易', 'http://www.pzhggzy.com/', '攀枝花市(钒钛矿业)公共资源交易', 'pzhggzy.com', '矿业,采矿,钒钛,资源,出让,招标,中标', '', '四川,攀枝花', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '泸州市公共资源交易', 'http://www.lzsggzy.com/', '泸州市公共资源交易', 'lzsggzy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,泸州', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '南充市公共资源交易', 'http://www.ncggzy.com/', '南充市公共资源交易', 'ncggzy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,南充', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '乐山市公共资源交易', 'http://www.lsggzy.com/', '乐山市公共资源交易', 'lsggzy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,乐山', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '自贡市公共资源交易', 'http://ggzy.zg.gov.cn/', '自贡市公共资源交易', 'zg.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '四川,自贡', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '达州市公共资源交易', 'http://www.dzggzy.cn/', '达州市公共资源交易', 'dzggzy.cn', '矿业,资源,出让,招标,中标,工程', '', '四川,达州', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '凉山彝族自治州公共资源交易', 'http://www.lsggzy.cn/', '凉山州(攀西矿业)公共资源交易', 'lsggzy.cn', '矿业,采矿,资源,出让,招标,中标', '', '四川,凉山', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '甘孜藏族自治州公共资源交易', 'http://www.gzggzy.gov.cn/', '甘孜州(川藏)公共资源交易', 'gzggzy.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '四川,甘孜,西藏', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '阿坝藏族羌族自治州公共资源交易', 'http://www.abggzy.com/', '阿坝州(川藏)公共资源交易', 'abggzy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,阿坝,西藏', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '西藏自治区自然资源厅', 'http://zrzyt.xizang.gov.cn/', '西藏自治区自然资源厅矿业权/公示', 'xizang.gov.cn', '矿业,采矿,探矿,资源,出让,地质灾害', '', '西藏', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '拉萨市公共资源交易', 'http://ggzy.lasa.gov.cn/', '拉萨市公共资源交易', 'lasa.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '西藏,拉萨', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '昌都市公共资源交易', 'http://ggzy.changdu.gov.cn/', '昌都市(川藏线)公共资源交易', 'changdu.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '西藏,昌都', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '林芝市公共资源交易', 'http://ggzy.linzhi.gov.cn/', '林芝市(川藏线)公共资源交易', 'linzhi.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '西藏,林芝', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '山南市公共资源交易', 'http://ggzy.shannan.gov.cn/', '山南市公共资源交易', 'shannan.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '西藏,山南', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '日喀则市公共资源交易', 'http://ggzy.rikaze.gov.cn/', '日喀则市公共资源交易', 'rikaze.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '西藏,日喀则', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '那曲市公共资源交易', 'http://ggzy.naqu.gov.cn/', '那曲市公共资源交易', 'naqu.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '西藏,那曲', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '阿里地区公共资源交易', 'http://ggzy.ali.gov.cn/', '阿里地区公共资源交易', 'ali.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '西藏,阿里', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
) t WHERE NOT EXISTS (SELECT 1 FROM web_source WHERE name=t.name AND is_deleted=0);
