SELECT to_char(produced_at, 'HH24:MI:SS') AS time, part_id, order_id, product_code,
       round(measured_mm::numeric, 3) AS measured_mm,
       CASE result WHEN 1 THEN 'Good' WHEN 2 THEN 'Reject' ELSE 'Scrapped' END AS result, defect_code
FROM mes.part_result
WHERE cell = :cell
ORDER BY produced_at DESC
LIMIT 25
