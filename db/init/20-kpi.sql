-- KPI layer: OEE, downtime, rejects, production per period (docs/system/kpi.md).
-- Every screen, the daily export and later reports read these functions, so
-- their figures are the same (MES-RPT-01 "figures equal the MES screens").
-- Idempotent, like 10-mes.sql: replayed by scripts/db_apply.py.
--
-- Periods are half-open [p_from, p_to). Time after now() is never counted, so
-- the current day can be asked for like a closed one.

-- Site master data: the production day starts at day_start in the site's time
-- zone. Calendar day (00:00) until the shift calendar is decided
-- (docs/README.md decision 7); a 06:00 start would only change this row.
CREATE TABLE IF NOT EXISTS mes.site (
    site       text PRIMARY KEY,
    name       text NOT NULL,
    timezone   text NOT NULL,
    day_start  time NOT NULL DEFAULT '00:00'
);
INSERT INTO mes.site VALUES ('ANN', 'Brevent Hydraulics, Annecy', 'Europe/Paris', '00:00')
ON CONFLICT (site) DO NOTHING;

-- PackML state names (docs/opcua-registry.md section 5). The names logged in
-- mes.cell_state are read from the controller and can lag one state behind.
CREATE TABLE IF NOT EXISTS mes.packml_state (
    state  smallint PRIMARY KEY,
    name   text NOT NULL
);
INSERT INTO mes.packml_state VALUES
    (0, 'Undefined'), (1, 'Clearing'), (2, 'Stopped'), (3, 'Starting'), (4, 'Idle'), (5, 'Suspended'),
    (6, 'Execute'), (7, 'Stopping'), (8, 'Aborting'), (9, 'Aborted'), (10, 'Holding'), (11, 'Held'),
    (12, 'Unholding'), (13, 'Suspending'), (14, 'Unsuspending'), (15, 'Resetting'), (16, 'Completing'),
    (17, 'Complete')
ON CONFLICT (state) DO UPDATE SET name = EXCLUDED.name;

-- Downtime reasons (MES-DT-03 table, MVP content from the URS mapping). The
-- StopReason of the controller selects the reason; StopReason 0 outside
-- Execute means no order is loaded.
CREATE TABLE IF NOT EXISTS mes.downtime_reason (
    stop_reason  smallint PRIMARY KEY,
    category     text NOT NULL,
    reason       text NOT NULL,
    active       boolean NOT NULL DEFAULT true
);
INSERT INTO mes.downtime_reason (stop_reason, category, reason) VALUES
    (0, 'Organisational', 'No order'),
    (1, 'Unclassified', 'Stop command'), (2, 'Unclassified', 'Hold command'),
    (4, 'Unclassified', 'Abort command'), (5, 'Unclassified', 'Suspend command'),
    (3, 'Planned', 'Changeover'),
    (10, 'Organisational', 'No parts from upstream'), (11, 'Organisational', 'Downstream blocked'),
    (20, 'Process', 'Reject bin full'),
    (101, 'Safety', 'Emergency stop'), (103, 'Safety', 'Guard door'),
    (110, 'Technical', 'Robot gripper'), (111, 'Technical', 'Robot gripper'),
    (120, 'Technical', 'Conveyor'), (121, 'Technical', 'Conveyor'), (122, 'Technical', 'Conveyor'),
    (140, 'Technical', 'Conveyor'),
    (130, 'Technical', 'Quality station'), (131, 'Technical', 'Quality station'),
    (150, 'Utilities', 'Compressed air'),
    (160, 'Technical', 'Robot controller')
ON CONFLICT (stop_reason) DO NOTHING;

-- Defect codes (docs/opcua-registry.md section 5).
CREATE TABLE IF NOT EXISTS mes.defect (
    defect_code  smallint PRIMARY KEY,
    name         text NOT NULL
);
INSERT INTO mes.defect VALUES
    (0, 'None'), (1, 'Undersize'), (2, 'Oversize'), (3, 'NoMeasurement'), (4, 'IdUnreadable'),
    (5, 'Dropped'), (6, 'Purged')
ON CONFLICT (defect_code) DO UPDATE SET name = EXCLUDED.name;

-- ---------------------------------------------------------------------------
-- Periods

-- Production day d of the site: [d + day_start, d + 1 + day_start) in local
-- time, so 23 h and 25 h days at the DST changes.
CREATE OR REPLACE FUNCTION mes.day_bounds(d date)
RETURNS TABLE (t_from timestamptz, t_to timestamptz)
LANGUAGE sql STABLE AS $$
    SELECT (d + s.day_start) AT TIME ZONE s.timezone,
           (d + 1 + s.day_start) AT TIME ZONE s.timezone
    FROM mes.site s ORDER BY s.site LIMIT 1
$$;

-- Production day an instant belongs to.
CREATE OR REPLACE FUNCTION mes.production_day(t timestamptz)
RETURNS date
LANGUAGE sql STABLE AS $$
    SELECT ((t AT TIME ZONE s.timezone) - s.day_start)::date
    FROM mes.site s ORDER BY s.site LIMIT 1
$$;

-- Named periods used by the screens: today, yesterday, last_hour, last_8h, last_24h.
CREATE OR REPLACE FUNCTION mes.period_bounds(p text)
RETURNS TABLE (t_from timestamptz, t_to timestamptz)
LANGUAGE sql STABLE AS $$
    SELECT b.t_from, b.t_to FROM mes.day_bounds(mes.production_day(now())) b WHERE p = 'today'
    UNION ALL
    SELECT b.t_from, b.t_to FROM mes.day_bounds(mes.production_day(now()) - 1) b WHERE p = 'yesterday'
    UNION ALL
    SELECT date_trunc('second', now()) - x.span, date_trunc('second', now())
    FROM (VALUES ('last_hour', interval '1 hour'), ('last_8h', interval '8 hours'),
                 ('last_24h', interval '24 hours')) x (name, span)
    WHERE x.name = p
$$;

-- ---------------------------------------------------------------------------
-- State intervals: the PackML state log cut to a period.

-- One row per state interval overlapping [p_from, p_to), clipped to it and to
-- now(). The state in force at p_from comes from the last row before it. The
-- reason follows MES-DT mapping: Execute has none.
CREATE OR REPLACE FUNCTION mes.state_intervals(p_from timestamptz, p_to timestamptz)
RETURNS TABLE (cell text, state smallint, state_name text, stop_reason smallint, category text,
               reason text, order_id text, started_at timestamptz, ended_at timestamptz,
               seconds double precision)
LANGUAGE sql STABLE AS $$
    WITH log AS (
        SELECT cs.cell, cs.state, cs.stop_reason, cs.order_id, cs.started_at,
               lead(cs.started_at) OVER (PARTITION BY cs.cell ORDER BY cs.started_at) AS next_at
        FROM mes.cell_state cs
        WHERE cs.started_at < p_to
          AND cs.started_at >= coalesce((SELECT max(x.started_at) FROM mes.cell_state x
                                         WHERE x.cell = cs.cell AND x.started_at <= p_from), '-infinity')
    ), clipped AS (
        SELECT l.*, greatest(l.started_at, p_from) AS t0,
               least(coalesce(l.next_at, now()), p_to, now()) AS t1
        FROM log l
    )
    SELECT c.cell, c.state, coalesce(ps.name, 'State ' || c.state),
           c.stop_reason,
           CASE WHEN c.state = 6 THEN 'Running' ELSE coalesce(r.category, 'Unclassified') END,
           CASE WHEN c.state = 6 THEN 'Execute' ELSE coalesce(r.reason, 'Stop reason ' || c.stop_reason) END,
           c.order_id, c.t0, c.t1, extract(epoch FROM c.t1 - c.t0)::double precision
    FROM clipped c
    LEFT JOIN mes.packml_state ps ON ps.state = c.state
    LEFT JOIN mes.downtime_reason r ON r.stop_reason = c.stop_reason
    WHERE c.t1 > c.t0
$$;

-- ---------------------------------------------------------------------------
-- KPIs

-- OEE per cell, plus one row for the whole area (cell = 'FIN'), MES-OEE-01..04.
-- Planned production time = time covered by the state log in the period: the
-- lab runs 24/7, no shift calendar, no planned breaks yet; Maintenance mode is
-- not logged yet (MES-OEE-01, to do). Performance is not capped (MES-OEE-03).
-- Parts count by produced_at in the period, from the cell's first state row
-- on: parts made before the state log existed have no time base.
CREATE OR REPLACE FUNCTION mes.oee(p_from timestamptz, p_to timestamptz)
RETURNS TABLE (cell text, planned_s double precision, run_s double precision, down_s double precision,
               total bigint, good bigint, rejects bigint, scrapped bigint, ideal_s double precision,
               availability double precision, performance double precision, quality double precision,
               oee double precision)
LANGUAGE sql STABLE AS $$
    WITH t AS (
        SELECT si.cell, sum(si.seconds) AS planned_s,
               coalesce(sum(si.seconds) FILTER (WHERE si.state = 6), 0) AS run_s
        FROM mes.state_intervals(p_from, p_to) si GROUP BY si.cell
    ), logged AS (
        SELECT cs.cell, min(cs.started_at) AS since FROM mes.cell_state cs GROUP BY cs.cell
    ), p AS (
        SELECT r.cell, count(*) AS total,
               count(*) FILTER (WHERE r.result = 1) AS good,
               count(*) FILTER (WHERE r.result = 2) AS rejects,
               count(*) FILTER (WHERE r.result = 3) AS scrapped,
               sum(pr.ideal_cycle_s) AS ideal_s
        FROM mes.part_result r JOIN mes.product pr ON pr.part_type = r.part_type
        JOIN logged lg ON lg.cell = r.cell AND r.produced_at >= lg.since
        WHERE r.produced_at >= p_from AND r.produced_at < p_to
        GROUP BY r.cell
    ), per_cell AS (
        SELECT c.cell, coalesce(t.planned_s, 0) AS planned_s, coalesce(t.run_s, 0) AS run_s,
               coalesce(p.total, 0) AS total, coalesce(p.good, 0) AS good,
               coalesce(p.rejects, 0) AS rejects, coalesce(p.scrapped, 0) AS scrapped,
               coalesce(p.ideal_s, 0) AS ideal_s
        FROM mes.cell c LEFT JOIN t USING (cell) LEFT JOIN p USING (cell)
    ), agg AS (
        SELECT coalesce(pc.cell, 'FIN') AS cell, sum(pc.planned_s) AS planned_s, sum(pc.run_s) AS run_s,
               sum(pc.total)::bigint AS total, sum(pc.good)::bigint AS good,
               sum(pc.rejects)::bigint AS rejects, sum(pc.scrapped)::bigint AS scrapped,
               sum(pc.ideal_s) AS ideal_s
        FROM per_cell pc GROUP BY GROUPING SETS ((pc.cell), ())
    )
    SELECT a.cell, a.planned_s, a.run_s, a.planned_s - a.run_s,
           a.total, a.good, a.rejects, a.scrapped, a.ideal_s,
           a.run_s / nullif(a.planned_s, 0),
           a.ideal_s / nullif(a.run_s, 0),
           a.good::double precision / nullif(a.total, 0),
           (a.run_s / nullif(a.planned_s, 0)) * (a.ideal_s / nullif(a.run_s, 0))
               * (a.good::double precision / nullif(a.total, 0))
    FROM agg a
    ORDER BY a.cell = 'FIN', a.cell
$$;

-- OEE per time bucket (e.g. one hour) over a period, per cell and 'FIN'.
-- Buckets after now() are left out.
CREATE OR REPLACE FUNCTION mes.oee_trend(p_from timestamptz, p_to timestamptz, p_step interval)
RETURNS TABLE (bucket timestamptz, cell text, availability double precision,
               performance double precision, quality double precision, oee double precision,
               good bigint, total bigint)
LANGUAGE sql STABLE AS $$
    SELECT b, o.cell, o.availability, o.performance, o.quality, o.oee, o.good, o.total
    FROM generate_series(p_from, p_to - p_step, p_step) b,
         LATERAL mes.oee(b, b + p_step) o
    WHERE b < now()
    ORDER BY b, o.cell = 'FIN', o.cell
$$;

-- Downtime per cell and reason (MES-DT-05 Pareto): duration and number of
-- stops. A stop is a run of consecutive non-Execute intervals with the same
-- reason; it counts in the period where it starts or is in force at p_from.
CREATE OR REPLACE FUNCTION mes.downtime(p_from timestamptz, p_to timestamptz)
RETURNS TABLE (cell text, category text, reason text, seconds double precision, stops bigint)
LANGUAGE sql STABLE AS $$
    WITH si AS (
        SELECT s.*, lag(s.reason) OVER (PARTITION BY s.cell ORDER BY s.started_at) AS prev_reason
        FROM mes.state_intervals(p_from, p_to) s
    )
    SELECT si.cell, si.category, si.reason, sum(si.seconds),
           count(*) FILTER (WHERE si.prev_reason IS DISTINCT FROM si.reason)
    FROM si WHERE si.state <> 6
    GROUP BY si.cell, si.category, si.reason
    ORDER BY sum(si.seconds) DESC
$$;

-- Rejects and scrap per cell and defect code.
CREATE OR REPLACE FUNCTION mes.rejects(p_from timestamptz, p_to timestamptz)
RETURNS TABLE (cell text, defect_code smallint, defect text, result text, parts bigint)
LANGUAGE sql STABLE AS $$
    SELECT r.cell, r.defect_code, coalesce(d.name, 'Code ' || r.defect_code),
           CASE r.result WHEN 2 THEN 'Reject' ELSE 'Scrapped' END, count(*)
    FROM mes.part_result r LEFT JOIN mes.defect d USING (defect_code)
    WHERE r.result <> 1 AND r.produced_at >= p_from AND r.produced_at < p_to
    GROUP BY 1, 2, 3, 4
    ORDER BY count(*) DESC
$$;

-- Production per cell and product.
CREATE OR REPLACE FUNCTION mes.production(p_from timestamptz, p_to timestamptz)
RETURNS TABLE (cell text, product_code text, good bigint, rejects bigint, scrapped bigint, total bigint,
               reject_pct double precision, first_part timestamptz, last_part timestamptz)
LANGUAGE sql STABLE AS $$
    SELECT r.cell, pr.product_code,
           count(*) FILTER (WHERE r.result = 1), count(*) FILTER (WHERE r.result = 2),
           count(*) FILTER (WHERE r.result = 3), count(*),
           100.0 * count(*) FILTER (WHERE r.result <> 1) / count(*),
           min(r.produced_at), max(r.produced_at)
    FROM mes.part_result r JOIN mes.product pr ON pr.part_type = r.part_type
    WHERE r.produced_at >= p_from AND r.produced_at < p_to
    GROUP BY 1, 2 ORDER BY 1, 2
$$;

-- Good and not-good parts per hour and cell (MES-CNT-04), with zero rows for
-- hours without production; hours after now() are left out.
CREATE OR REPLACE FUNCTION mes.hourly(p_from timestamptz, p_to timestamptz)
RETURNS TABLE (hour timestamptz, cell text, good bigint, not_good bigint)
LANGUAGE sql STABLE AS $$
    SELECT h, c.cell,
           count(r.part_id) FILTER (WHERE r.result = 1),
           count(r.part_id) FILTER (WHERE r.result <> 1)
    FROM generate_series(date_trunc('hour', p_from), p_to - interval '1 second', interval '1 hour') h
    CROSS JOIN mes.cell c
    LEFT JOIN mes.part_result r
           ON r.cell = c.cell AND r.produced_at >= greatest(h, p_from)
          AND r.produced_at < least(h + interval '1 hour', p_to)
    WHERE h < now()
    GROUP BY h, c.cell ORDER BY h, c.cell
$$;

-- Area total per hour, as columns for the charts (one row per hour).
CREATE OR REPLACE FUNCTION mes.hourly_area(p_from timestamptz, p_to timestamptz)
RETURNS TABLE (hour timestamptz, good bigint, not_good bigint)
LANGUAGE sql STABLE AS $$
    SELECT h.hour, sum(h.good)::bigint, sum(h.not_good)::bigint
    FROM mes.hourly(p_from, p_to) h GROUP BY h.hour ORDER BY h.hour
$$;

-- Orders worked in the period: started before p_to, not ended before p_from.
-- good/rejects are the MES counts of the whole order; *_in_period those of the period.
CREATE OR REPLACE FUNCTION mes.orders(p_from timestamptz, p_to timestamptz)
RETURNS TABLE (order_id text, product_code text, cell text, status text, target_qty integer,
               good bigint, rejects bigint, good_in_period bigint, rejects_in_period bigint,
               plc_good integer, plc_rejects integer, started_at timestamptz, ended_at timestamptz,
               duration_min double precision)
LANGUAGE sql STABLE AS $$
    SELECT w.order_id, w.product_code, w.cell, w.status, w.target_qty,
           count(r.part_id) FILTER (WHERE r.result = 1),
           count(r.part_id) FILTER (WHERE r.result <> 1),
           count(r.part_id) FILTER (WHERE r.result = 1 AND r.produced_at >= p_from AND r.produced_at < p_to),
           count(r.part_id) FILTER (WHERE r.result <> 1 AND r.produced_at >= p_from AND r.produced_at < p_to),
           w.good_qty, w.reject_qty, w.started_at, w.ended_at,
           extract(epoch FROM coalesce(w.ended_at, now()) - w.started_at) / 60
    FROM mes.work_order w LEFT JOIN mes.part_result r ON r.order_id = w.order_id
    WHERE w.started_at < p_to AND (w.ended_at IS NULL OR w.ended_at >= p_from)
    GROUP BY w.order_id
    ORDER BY w.started_at
$$;
