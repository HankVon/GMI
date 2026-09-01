SELECT id,name,max_pages,last_run_result,last_error FROM web_source WHERE id=57;
SELECT COUNT(*) AS ziyang_clues_now FROM web_clue WHERE is_deleted=0 AND (title LIKE '%资阳%' OR region LIKE '%资阳%');
SELECT source_id, COUNT(*) AS n FROM web_clue WHERE is_deleted=0 AND title LIKE '%资阳%' GROUP BY source_id;
