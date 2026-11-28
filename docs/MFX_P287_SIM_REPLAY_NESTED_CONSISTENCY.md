# P287 — SIM replay nested receipt consistency

The compact P033 V1 hash payload does not serialize all nested P032/P019/P018 and P031 fields. Independently check their research-only flags, identity, direction, causal timestamps and routed row/group consistency when verifying the replay, including empty NO_SIGNAL receipts. Four regression methods reject contradictory nested receipts without modifying the stored link. Existing V1 hash payload, formula, source and release gates are unchanged; no claim of external authentication. No provider/cache/schedule/Production/MST change.
