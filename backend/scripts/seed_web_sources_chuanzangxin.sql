-- 聚焦西部三省份: 四川 + 西藏 + 新疆
-- 1) 恢复之前误删的新疆两源
UPDATE web_source SET is_deleted=0, enabled=1, updated_at=NOW() WHERE id IN (65,66) AND is_deleted=1;

-- 2) 新增四川剩余市州 + 新疆深度源(通用 crawl, 按 name 去重)
INSERT INTO web_source (name, url, description, allow_domains, keywords, exclude_keywords, regions, scrape_mode, max_depth, max_pages, llm_enhance, enabled, is_deleted, created_at, updated_at)
SELECT * FROM (
  -- 四川剩余市州公共资源交易
  SELECT '广元市公共资源交易' AS name, 'http://www.gyggzy.gov.cn/' AS url, '广元市公共资源交易', 'gyggzy.gov.cn' AS allow_domains, '矿业,资源,出让,招标,中标,工程' AS keywords, '' AS exclude_keywords, '四川,广元' AS regions, 'crawl' AS scrape_mode, 1 AS max_depth, 30 AS max_pages, 'filter' AS llm_enhance, 1 AS enabled, 0 AS is_deleted, NOW() AS created_at, NOW() AS updated_at
  UNION ALL SELECT '遂宁市公共资源交易', 'http://www.snjsjy.com/', '遂宁市公共资源交易', 'snjsjy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,遂宁', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '内江市公共资源交易', 'http://www.njgcjy.com/', '内江市公共资源交易', 'njgcjy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,内江', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '眉山市公共资源交易', 'http://www.msggzy.org.cn/', '眉山市公共资源交易', 'msggzy.org.cn', '矿业,资源,出让,招标,中标,工程', '', '四川,眉山', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '资阳市公共资源交易', 'http://www.zyggzy.com/', '资阳市公共资源交易', 'zyggzy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,资阳', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '广安市公共资源交易', 'http://www.gaggzy.com/', '广安市公共资源交易', 'gaggzy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,广安', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '巴中市公共资源交易', 'http://www.bzggzy.gov.cn/', '巴中市公共资源交易', 'bzggzy.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '四川,巴中', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '雅安市公共资源交易', 'http://www.yaggzy.com/', '雅安市公共资源交易', 'yaggzy.com', '矿业,资源,出让,招标,中标,工程', '', '四川,雅安', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  -- 新疆自治区/地市公共资源交易 + 自然资源厅
  UNION ALL SELECT '新疆维吾尔自治区自然资源厅', 'http://zrzyt.xinjiang.gov.cn/', '新疆自然资源厅矿业权/公示', 'xinjiang.gov.cn', '矿业,采矿,探矿,资源,出让,地质灾害', '', '新疆', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '乌鲁木齐市公共资源交易', 'http://ggzy.wlmq.gov.cn/', '乌鲁木齐市公共资源交易', 'wlmq.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,乌鲁木齐', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '克拉玛依市公共资源交易', 'http://ggzy.klmy.gov.cn/', '克拉玛依市公共资源交易', 'klmy.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,克拉玛依', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '喀什地区公共资源交易', 'http://ggzy.kashi.gov.cn/', '喀什地区公共资源交易', 'kashi.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,喀什', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '伊犁哈萨克自治州公共资源交易', 'http://ggzy.ylz.gov.cn/', '伊犁州公共资源交易', 'ylz.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,伊犁', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '昌吉回族自治州公共资源交易', 'http://ggzy.cj.gov.cn/', '昌吉州公共资源交易', 'cj.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,昌吉', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '吐鲁番市公共资源交易', 'http://ggzy.tlf.gov.cn/', '吐鲁番市公共资源交易', 'tlf.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,吐鲁番', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '哈密市公共资源交易', 'http://ggzy.hami.gov.cn/', '哈密市公共资源交易', 'hami.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,哈密', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '和田地区公共资源交易', 'http://ggzy.hotan.gov.cn/', '和田地区公共资源交易', 'hotan.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,和田', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '阿克苏地区公共资源交易', 'http://ggzy.aks.gov.cn/', '阿克苏地区公共资源交易', 'aks.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,阿克苏', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '巴音郭楞蒙古自治州公共资源交易', 'http://ggzy.bz.gov.cn/', '巴州公共资源交易', 'bz.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,巴州', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '阿勒泰地区公共资源交易', 'http://ggzy.alt.gov.cn/', '阿勒泰地区公共资源交易', 'alt.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,阿勒泰', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '塔城地区公共资源交易', 'http://ggzy.tacheng.gov.cn/', '塔城地区公共资源交易', 'tacheng.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,塔城', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '博尔塔拉蒙古自治州公共资源交易', 'http://ggzy.bortala.gov.cn/', '博州公共资源交易', 'bortala.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,博州', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
  UNION ALL SELECT '克孜勒苏柯尔克孜自治州公共资源交易', 'http://ggzy.kzls.gov.cn/', '克州公共资源交易', 'kzls.gov.cn', '矿业,资源,出让,招标,中标,工程', '', '新疆,克州', 'crawl', 1, 30, 'filter', 1, 0, NOW(), NOW()
) t WHERE NOT EXISTS (SELECT 1 FROM web_source WHERE name=t.name AND is_deleted=0);
