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

Evaluator output is untrusted data. The transition policy owns numeric bounds,
allowed fields, idempotency, and persistence. Expression guidance is additive
context and must never overwrite the host application's system prompt.
