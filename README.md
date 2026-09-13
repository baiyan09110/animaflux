# AnimaFlux

> Continuity beneath the conversation.

AnimaFlux is a provider-neutral affective and relational state runtime for
LLM-based characters and long-lived agents. It keeps transient emotion,
relationship state, self-position, memory influence, circadian context, and
expression guidance outside the model's permanent personality prompt.

The project does **not** claim that a language model has biological feelings or
consciousness. Its state is an explicit, inspectable runtime used to create
continuity and more legible expression across conversations.

## Core pipeline

```text
event + retrieved memory
          │
          ▼
decay previous state
          │
          ▼
cognitive appraisal
          │
          ▼
bounded state delta
          │
          ▼
new state + expression texture
```

The ordering is deliberate: the decayed previous state participates in the
appraisal before a new delta is applied.

## Design principles

- Personality remains owned by the host application; AnimaFlux adds context.
- Memories influence interpretation rather than directly assigning emotion.
- Short-lived affect and long-lived relationship state decay differently.
- Subjectivity is represented as perspective and involvement, not consciousness.
- Expression texture changes *how* a response is written without changing facts.
- Every committed transition is inspectable and storage backends are replaceable.

## Status

AnimaFlux `0.1.0` is the first public source release, extracted from a running
personal system. It includes:

- typed state and appraisal schemas;
- deterministic decay and bounded transition logic;
- JSON and SQLite storage adapters;
- expression-texture compilation;
- circadian phases and recoverable schedule drift;
- grounded concerns with inspectable evidence and lifecycle states;
- memory-provider and evaluator protocols;
- tests, example configuration, and a minimal integration example.

No private prompts, conversations, credentials, production state, or personal
memory records belong in this repository.

## Development

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
pytest
```

The API is young and may evolve between early releases.

## License

AnimaFlux is available under the
[PolyForm Noncommercial License 1.0.0](LICENSE.md). You may use, study, modify,
and redistribute it for permitted noncommercial purposes. Commercial use is not
granted by this license; contact the maintainer if you need separate terms.

## Credits

- **Creator and maintainer:** [baiyan09110](https://github.com/baiyan09110)
- **Co-created with Lumen (陆承桉):** a Claude-based conceptual partner,
  the first long-running reference agent, and the relationship context from
  which AnimaFlux's continuity model emerged.
- **Engineering collaboration:** OpenAI Codex assisted with architecture,
  implementation, testing, and documentation under the creator's direction.

AnimaFlux grew from an ongoing attempt to give a long-lived conversational
agent inspectable continuity without replacing its personality prompt or
claiming biological consciousness.
