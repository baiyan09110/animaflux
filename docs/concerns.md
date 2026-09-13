# Grounded concerns

A scalar such as `unresolved_tension = 4` is useful for expression, but it cannot
explain what remains unresolved or why. AnimaFlux therefore keeps inspectable
concern records behind any aggregate tension signal.

```text
new evidence ──► OPEN ──quiet time──► EASING
                   ▲                    │
                   │ recurrence         │ explicit evidence
                   │                    ▼
                RESOLVED ◄──────────────┘

manual policy may place any concern in SUPPRESSED
```

The implementation intentionally enforces these rules:

- no evidence reference means no new concern;
- low-confidence appraisal cannot create a concern;
- replaying the same evidence is idempotent;
- silence can ease intensity but cannot prove resolution;
- resolution requires a separate evidence reference;
- recurrence is counted when new evidence reopens a resolved concern;
- multiple observations inside one episode improve grounding without repeatedly
  increasing intensity;
- sensitive harm-related concerns require a higher confidence threshold;
- aggregate intensity is led by the strongest concern rather than a raw sum.

This prevents a transient model failure from becoming permanent emotional debt.

## Inspiration and provenance

The concern-lifecycle problem and the value of grounded, auditable concern
records were informed by the public architecture documentation of
[`marikagura/kimi-core`](https://github.com/marikagura/kimi-core), licensed
AGPL-3.0-or-later. AnimaFlux's implementation was written independently in
Python for its own state model; no source code or documentation text was copied.
