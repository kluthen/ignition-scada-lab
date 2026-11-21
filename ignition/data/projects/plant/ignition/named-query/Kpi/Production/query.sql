-- Production per cell and product for a named period.
SELECT p.cell, p.product_code AS product, p.good, p.rejects, p.scrapped, p.total,
       round(p.reject_pct::numeric, 2) AS reject_pct,
       to_char(p.first_part, 'HH24:MI') AS first_part, to_char(p.last_part, 'HH24:MI') AS last_part
FROM mes.period_bounds(:period) b, mes.production(b.t_from, b.t_to) p
WHERE :cell = '' OR p.cell = :cell
ORDER BY p.cell, p.product_code
