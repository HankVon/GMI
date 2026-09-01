SELECT id, name, keywords, regions, allow_domains, exclude_keywords, llm_enhance,
       scrape_mode, max_depth, max_pages
FROM web_source WHERE id IN (106, 77, 80, 83, 104, 105, 107, 108);
