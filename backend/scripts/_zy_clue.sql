SELECT COUNT(*) AS ziyang_clues FROM web_clue WHERE is_deleted=0 AND (title LIKE '%资阳%' OR region LIKE '%资阳%');
SELECT id,name,url,max_pages,last_run_result FROM web_source WHERE id=57;
