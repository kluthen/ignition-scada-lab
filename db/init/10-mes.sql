-- MES model, first slice (docs/mes-requirements.md: ORD, DSP, CNT, TRC).
-- Idempotent: runs when the pgdata volume is created, and again with
-- scripts/db_apply.py on an existing database. Master data rows for the cells
-- come from docs/cells.csv (scripts/db_apply.py), not from this file.

CREATE TABLE IF NOT EXISTS mes.product (                 -- MES-ORD-05, = cell recipe table (scenario.md 3)
    product_code     text PRIMARY KEY,
    part_type        smallint NOT NULL UNIQUE,
    description      text NOT NULL,
    nominal_mm       double precision NOT NULL,
    tolerance_mm     double precision NOT NULL,
    ideal_cycle_s    double precision NOT NULL
);
INSERT INTO mes.product VALUES
    ('HSG-A20', 1, 'Valve housing A, bore 20 mm', 20.000, 0.050, 2.4),
    ('HSG-B32', 2, 'Valve housing B, bore 32 mm', 32.000, 0.080, 2.6),
    ('HSG-C45', 3, 'Valve housing C, bore 45 mm', 45.000, 0.100, 2.8)
ON CONFLICT (product_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS mes.cell (                    -- equipment master, from docs/cells.csv
    cell                  text PRIMARY KEY,              -- C01..C05 = Ignition UDT instance name
    bay                   text NOT NULL,
    qualified_part_types  smallint[] NOT NULL,
    notes                 text NOT NULL DEFAULT ''
);

CREATE SEQUENCE IF NOT EXISTS mes.work_order_seq;     -- dispatch sequence
CREATE SEQUENCE IF NOT EXISTS mes.order_no_seq;       -- order numbers OF-<year>-<n> of the lab planner
CREATE TABLE IF NOT EXISTS mes.work_order (              -- MES-ORD-01/02
    order_id       text PRIMARY KEY CHECK (length(order_id) <= 32),
    product_code   text NOT NULL REFERENCES mes.product,
    target_qty     integer NOT NULL CHECK (target_qty > 0),
    seq            bigint NOT NULL DEFAULT nextval('mes.work_order_seq'),   -- dispatch sequence
    status         text NOT NULL DEFAULT 'Planned'
                   CHECK (status IN ('Planned', 'Released', 'Dispatched', 'Running', 'Completed', 'ClosedShort', 'Cancelled')),
    cell           text REFERENCES mes.cell,              -- set at dispatch
    good_qty       integer,                               -- PLC counters at completion (MES-CNT-03)
    reject_qty     integer,
    created_by     text NOT NULL DEFAULT 'system',
    created_at     timestamptz NOT NULL DEFAULT now(),
    dispatched_at  timestamptz,
    started_at     timestamptz,
    ended_at       timestamptz
);
CREATE INDEX IF NOT EXISTS work_order_status_idx ON mes.work_order (status, seq);

CREATE TABLE IF NOT EXISTS mes.order_event (             -- MES-ORD-02: every status change, with the user
    id         bigserial PRIMARY KEY,
    order_id   text NOT NULL REFERENCES mes.work_order,
    status     text NOT NULL,
    cell       text,
    by_user    text NOT NULL,
    at         timestamptz NOT NULL DEFAULT now(),
    comment    text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS mes.part_result (             -- MES-TRC-01
    cell              text NOT NULL REFERENCES mes.cell,
    startup_time      timestamptz NOT NULL,              -- C01.Admin.StartUpTime: controller run
    sequence          bigint NOT NULL,                   -- C01.Traceability.Sequence within that run
    part_id           text NOT NULL,
    order_id          text NOT NULL,
    product_code      text,
    part_type         smallint NOT NULL,
    measured_mm       double precision NOT NULL,
    result            smallint NOT NULL,                 -- 1 Good, 2 Reject, 3 Scrapped
    defect_code       smallint NOT NULL,
    produced_at       timestamptz NOT NULL,              -- C01.Traceability.Timestamp (PLC, UTC)
    received_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (cell, startup_time, sequence)
);
CREATE UNIQUE INDEX IF NOT EXISTS part_result_part_id_idx ON mes.part_result (part_id);
CREATE INDEX IF NOT EXISTS part_result_order_idx ON mes.part_result (order_id);
CREATE INDEX IF NOT EXISTS part_result_time_idx ON mes.part_result (produced_at);

CREATE TABLE IF NOT EXISTS mes.cell_state (              -- PackML state log, basis for downtime and OEE
    cell          text NOT NULL REFERENCES mes.cell,
    started_at    timestamptz NOT NULL,
    state         smallint NOT NULL,
    state_name    text NOT NULL,
    stop_reason   smallint NOT NULL,
    stop_text     text NOT NULL,
    order_id      text NOT NULL DEFAULT '',
    PRIMARY KEY (cell, started_at)
);

CREATE TABLE IF NOT EXISTS mes.event (                   -- warnings and notable events (MES-DSP-03, MES-CNT-03)
    id         bigserial PRIMARY KEY,
    cell       text,
    at         timestamptz NOT NULL DEFAULT now(),
    severity   text NOT NULL CHECK (severity IN ('Info', 'Warning', 'Error')),
    kind       text NOT NULL,
    message    text NOT NULL
);

-- Hourly production per cell (MES-CNT-04 without the shift calendar yet).
CREATE OR REPLACE VIEW mes.hourly_production AS
SELECT cell, date_trunc('hour', produced_at) AS hour,
       count(*) FILTER (WHERE result = 1) AS good,
       count(*) FILTER (WHERE result <> 1) AS not_good
FROM mes.part_result GROUP BY 1, 2;
