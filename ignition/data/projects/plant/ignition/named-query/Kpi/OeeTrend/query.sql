-- Hourly OEE, A, P, Q (percent) of the area (cell '') or one cell.
SELECT to_char(t.bucket, 'HH24":00"') AS hour,
       round((t.oee * 100)::numeric, 1)          AS oee,
       round((t.availability * 100)::numeric, 1) AS availability,
       round((t.performance * 100)::numeric, 1)  AS performance,
       round((t.quality * 100)::numeric, 1)      AS quality
FROM mes.period_bounds(:period) b, mes.oee_trend(date_trunc('hour', b.t_from), b.t_to, interval '1 hour') t
WHERE t.cell = CASE WHEN :cell = '' THEN 'FIN' ELSE :cell END
  AND t.total > 0
ORDER BY t.bucket
