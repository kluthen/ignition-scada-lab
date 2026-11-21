SELECT c.cell, c.bay,
       count(r.part_id) FILTER (WHERE r.result = 1)  AS good,
       count(r.part_id) FILTER (WHERE r.result <> 1) AS rejects,
       round(100.0 * count(r.part_id) FILTER (WHERE r.result <> 1) / nullif(count(r.part_id), 0), 1) AS reject_pct,
       (SELECT count(*) FROM mes.work_order w
         WHERE w.cell = c.cell AND w.status = 'Completed' AND w.ended_at >= date_trunc('day', now())) AS orders_done,
       to_char(max(r.produced_at), 'HH24:MI:SS') AS last_part
FROM mes.cell c
LEFT JOIN mes.part_result r ON r.cell = c.cell AND r.produced_at >= date_trunc('day', now())
GROUP BY c.cell, c.bay
ORDER BY c.cell
