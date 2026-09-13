# Changelog

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
