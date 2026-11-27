# P261 — fix synthetic research clock boundaries

Concrete review of P256–P260 found that duration/contiguity alone permitted off-grid bars, and P260 accepted the just-finished UTC day as current for up to 15 minutes after midnight. Reject non-grid M15/H1/D1 starts in the common validation path; reject decisions at/after the current UTC day end. No change to delayed research lookback semantics, source calendar qualification or production decisions. Five regression tests; rollback by squash revert. SIM only, NO_SIGNAL.
