-- Downtime Pareto (MES-DT-05) for the area (cell '') or one cell.
SELECT d.reason, d.category, round((sum(d.seconds) / 60)::numeric, 1) AS minutes, sum(d.stops)::bigint AS stops
FROM mes.period_bounds(:period) b, mes.downtime(b.t_from, b.t_to) d
WHERE :cell = '' OR d.cell = :cell
GROUP BY d.reason, d.category
ORDER BY minutes DESC
