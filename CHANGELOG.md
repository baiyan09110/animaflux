# Changelog

## 0.1.3 - 2026-09-14

- Add an ordered schema migration registry and reject unsupported future states.
- Bound expression guidance by rule count and character count while prioritizing
  alertness-critical constraints.
- Audit the raw persisted `source_state` separately from the decayed
  `previous_state` used for appraisal.

## 0.1.2 - 2026-09-14

- Evaluate circadian dates and clock minutes in an explicit IANA time zone.
- Recover schedule drift for every elapsed silent day rather than only once per call.
- Replace the JSON idempotency lookback window with a reconciled event index.
- Restore defensive delta bounds inside direct `apply()` calls.
- Preserve host-defined state extensions and repair invalid built-in field types.
- Use explicitly managed SQLite transactions and close connections reliably.

## 0.1.1 - 2026-09-13

- Make small circadian offsets converge to zero and guard daily recovery.
- Wire optional circadian phase and schedule updates into `StateEngine.process`.
- Add schema-versioned, backward-compatible state loading.
- Add a dormant exit for concerns that finish easing.
- Make transition bounds and decay dynamics configurable through `TransitionPolicy`.
- Record evaluator-proposed deltas alongside applied deltas and policy notes.
- Add host event idempotency and atomic SQLite state/audit commits.
- Document JSON storage limitations and add a runnable integration example.

## 0.1.0 - 2026-09-13

- First public source release.
