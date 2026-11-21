-- Good and not-good parts per hour (MES-CNT-04) for the area (cell '') or one cell.
SELECT to_char(h.hour, 'HH24":00"') AS hour, sum(h.good)::bigint AS good, sum(h.not_good)::bigint AS not_good
FROM mes.period_bounds(:period) b, mes.hourly(b.t_from, b.t_to) h
WHERE :cell = '' OR h.cell = :cell
GROUP BY h.hour
ORDER BY h.hour
