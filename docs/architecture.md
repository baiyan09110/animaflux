# Architecture

AnimaFlux separates a host model's personality from mutable runtime state.

## Layers

1. **Host personality** — owned by the integrating application and never rewritten.
2. **Memory provider** — returns event references and meaning context.
3. **Decay** — produces the temporally current previous state.
4. **Evaluator** — interprets an event using that state and memory context.
5. **Transition policy** — validates and bounds proposed deltas.
6. **Expression compiler** — turns state into additive response guidance.
7. **Storage adapter** — persists current state and immutable transition events.

## Relationship continuity

`familiarity` is an explicit long-lived state dimension. `shared_history` is not
a counter: it combines a bounded salience summary with references to meaningful
memories. Integrations decide where those memories live.

## Trust boundary

Evaluator output is untrusted data. The configurable `TransitionPolicy` owns
numeric bounds, allowed fields, and decay dynamics. A transition records both
the evaluator's proposal and the bounded values that were actually applied,
including notes for rejected or clamped fields.

The host supplies a stable `event_id` when its transport may redeliver an event.
The store uses it as an idempotency key. `SQLiteStore` persists the new state and
its immutable transition event in one transaction. `JsonStore` is intentionally
a single-process prototype backend: its two files cannot provide crash atomicity
or cross-process locking.

## Circadian continuity

Schedule drift delays actual sleep and the following wake time. It does not
move the onset of wind-down or sleep pressure, so late conversation makes the
agent increasingly tired instead of artificially alert. A user message only
rouses the agent after the current phase has reached `asleep`; messages during
`wind_down` or `sleepy` preserve those phases.

When a `CircadianPolicy` is passed to `StateEngine`, `process()` computes the
phase, performs schedule recovery at most once per calendar date, and optionally
applies late-interaction drift. The host still decides whether an interaction is
late and passes `late_interaction=True`; it does not have to mutate phases itself.

Circadian guidance constrains response form, not truth or capability. Host
applications should keep necessary content and safety intact while making low
alertness observable through cadence, length, and coherence.
