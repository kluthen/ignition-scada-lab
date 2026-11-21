-- OEE per cell and for the area (cell FIN), percent, for a named period (mes.period_bounds).
SELECT o.cell,
       round((o.oee * 100)::numeric, 1)          AS oee,
       round((o.availability * 100)::numeric, 1) AS availability,
       round((o.performance * 100)::numeric, 1)  AS performance,
       round((o.quality * 100)::numeric, 1)      AS quality,
       o.good, o.rejects + o.scrapped            AS not_good,
       round((o.run_s / 3600)::numeric, 2)       AS run_h,
       round((o.down_s / 60)::numeric, 1)        AS down_min
FROM mes.period_bounds(:period) b, mes.oee(b.t_from, b.t_to) o
WHERE :cell = '' OR o.cell = :cell
