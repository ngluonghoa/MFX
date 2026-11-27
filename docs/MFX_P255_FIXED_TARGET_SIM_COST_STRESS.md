# P255 — fixed target adverse fee sensitivity

Research only. Recompute verified P252 lifecycle and accepted P251 structural
plans under a caller-supplied strictly increasing nonnegative per-unit entry fee
increment grid starting at zero. Keep quote, SL and first-obstacle TP1 fixed.
No target reselection, parameter fitting, returns, or real fills. Pass counts
must never increase with adverse fees. No quote acquisition, writes, broker
orders, or numerical source approvals. This is calibration infrastructure,
not calibration on actual FX history. Original source remains frozen.
