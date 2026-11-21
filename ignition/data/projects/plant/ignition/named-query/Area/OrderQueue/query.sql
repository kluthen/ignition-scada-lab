SELECT order_id, product_code, target_qty, status, coalesce(cell, '') AS cell,
       to_char(created_at, 'DD/MM HH24:MI') AS created
FROM mes.work_order
WHERE status IN ('Released', 'Dispatched', 'Running')
ORDER BY CASE status WHEN 'Running' THEN 0 WHEN 'Dispatched' THEN 1 ELSE 2 END, seq
LIMIT 30
