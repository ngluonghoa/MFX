# P260 — ADR and synthetic session filter

SOURCE_LOCKED_03 paragraphs 37/122. Compare current observed closed-M15 UTC-session range with mean prior completed daily ranges, explicit lookback 2–60 and threshold (0,3], strict exhaustion boundary, explicit half-open UTC session clock. Same policy both directions, no inferred live broker session/DST/news, no canonical D1 admission. No actual calibration or production gate promotion. Tests exact equality, mirror, session boundary, incomplete and future inputs. NO_SIGNAL; rollback squash revert.
