"""Demo program: one tank, an operator-set inlet valve, an outlet pump.

Register map (zero-based Modbus addresses; Ignition Modbus addresses are
one-based by default, e.g. holding 0 -> "HR1"):

Coils (commands, SCADA writes)
  0  auto_mode         1 = pump driven by level setpoints, 0 = manual
  1  pump_manual_cmd   pump command in manual mode
  2  fault_reset       pulse 1 to reset the pump fault (PLC clears it)

Discrete inputs (states, SCADA reads)
  0  pump_running
  1  level_high_alarm  level >= 95 %
  2  level_low_alarm   level <= 5 %
  3  pump_fault        pump ran dry; stays latched until fault_reset

Holding registers (setpoints, SCADA writes)
  0  inlet_valve_pct   0..100 %
  1  level_start_sp    x10 %, auto mode starts the pump above it (default 800)
  2  level_stop_sp     x10 %, auto mode stops the pump below it  (default 200)

Input registers (measurements, SCADA reads)
  0  level             x10 %
  1  inflow            x10 %/min
  2  outflow           x10 %/min
  3  pump_starts       counter
  4  heartbeat         increments every scan (wraps at 65535)
"""

from __future__ import annotations

import logging

from io_image import IOImage

log = logging.getLogger("tank")

INLET_MAX_PCT_PER_MIN = 60.0   # tank % per minute with the valve 100 % open
PUMP_PCT_PER_MIN = 90.0        # tank % per minute removed by the pump


class Program:
    def __init__(self, io: IOImage):
        self.io = io
        self.level = 50.0
        io.coils[0] = True          # start in auto
        io.holding[0] = 50          # valve half open
        io.holding[1] = 800
        io.holding[2] = 200
        self._was_running = False

    def scan(self, dt: float) -> None:
        io = self.io
        auto, manual_cmd, reset = io.coils[0], io.coils[1], io.coils[2]
        valve = max(0, min(100, io.holding[0]))
        start_sp, stop_sp = io.holding[1] / 10.0, io.holding[2] / 10.0
        running, fault = io.discrete_inputs[0], io.discrete_inputs[3]

        if reset:
            if fault:
                log.info("pump fault reset")
            fault = False
            io.coils[2] = False

        if fault:
            running = False
        elif auto:
            if self.level >= start_sp:
                running = True
            elif self.level <= stop_sp:
                running = False
        else:
            running = manual_cmd

        inflow = INLET_MAX_PCT_PER_MIN * valve / 100.0
        outflow = PUMP_PCT_PER_MIN if running else 0.0
        self.level += (inflow - outflow) * dt / 60.0
        if self.level <= 0.0:
            self.level = 0.0
            if running:
                log.warning("pump ran dry -> fault")
                fault, running, outflow = True, False, 0.0
        self.level = min(self.level, 100.0)

        if running and not self._was_running:
            io.input_regs[3] = (io.input_regs[3] + 1) & 0xFFFF
        self._was_running = running

        io.discrete_inputs[0] = running
        io.discrete_inputs[1] = self.level >= 95.0
        io.discrete_inputs[2] = self.level <= 5.0
        io.discrete_inputs[3] = fault
        io.input_regs[0] = round(self.level * 10)
        io.input_regs[1] = round(inflow * 10)
        io.input_regs[2] = round(outflow * 10)
        io.input_regs[4] = (io.input_regs[4] + 1) & 0xFFFF
