SELECT order_id, product_code, target_qty, status, good_qty, reject_qty,
       to_char(started_at, 'DD/MM HH24:MI') AS started, to_char(ended_at, 'DD/MM HH24:MI') AS ended
FROM mes.work_order
WHERE cell = :cell
ORDER BY seq DESC
LIMIT 10
