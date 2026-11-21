"""Process image of the simulated PLC: the four Modbus tables.

The PLC program reads and writes these lists directly during its scan.
Writes coming from the network go through write_coils / write_holding so they
are logged, the way a PLC records an HMI command.
"""

from __future__ import annotations

import logging

log = logging.getLogger("io")


class IOImage:
    def __init__(self, coils: int = 64, discrete_inputs: int = 64, holding: int = 64, input_regs: int = 64):
        self.coils = [False] * coils                     # FC1/5/15  read-write bits  (commands)
        self.discrete_inputs = [False] * discrete_inputs  # FC2       read-only bits   (states)
        self.holding = [0] * holding                     # FC3/6/16  read-write words (setpoints)
        self.input_regs = [0] * input_regs               # FC4       read-only words  (measurements)

    def write_coils(self, start: int, values: list[bool]) -> None:
        log.info("network write coils[%d..%d] = %s", start, start + len(values) - 1, [int(v) for v in values])
        self.coils[start:start + len(values)] = values

    def write_holding(self, start: int, values: list[int]) -> None:
        log.info("network write holding[%d..%d] = %s", start, start + len(values) - 1, values)
        self.holding[start:start + len(values)] = values
