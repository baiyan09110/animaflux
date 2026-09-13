"""Minimal, runnable AnimaFlux integration."""

from __future__ import annotations

from tempfile import TemporaryDirectory

from animaflux import Appraisal, CircadianPolicy, JsonStore, StateDelta, StateEngine


class ExampleEvaluator:
    """Replace this deterministic example with your model-backed evaluator."""

    def evaluate(self, event, previous_state, memory):
        return Appraisal(
            meaning="an attempt to reconnect",
            importance=6,
            uncertainty=2,
        ), StateDelta(
            {
                "emotion": {"anger": -1.0, "happiness": 0.5},
                "relationship": {"trust": 0.25},
            }
        )


with TemporaryDirectory() as runtime_directory:
    engine = StateEngine(
        JsonStore(runtime_directory),
        ExampleEvaluator(),
        circadian_policy=CircadianPolicy(timezone_name="Asia/Shanghai"),
    )
    transition = engine.process(
        "The user returned after a disagreement.",
        event_id="example:event:1",
    )
    print(transition.appraisal.meaning)
    print(transition.applied_delta)
