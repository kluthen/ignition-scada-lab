-- Rejects and scrap by defect code for the area (cell '') or one cell.
SELECT r.defect, sum(r.parts)::bigint AS parts
FROM mes.period_bounds(:period) b, mes.rejects(b.t_from, b.t_to) r
WHERE :cell = '' OR r.cell = :cell
GROUP BY r.defect
ORDER BY parts DESC
