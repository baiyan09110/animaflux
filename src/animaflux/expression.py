from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExpressionTexture:
    guidance: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    omitted_rules: int = 0

    def as_context(self) -> str:
        rules = "\n".join(f"- {rule}" for rule in self.guidance)
        return (
            "[Runtime expression guidance — additive, not personality]\n"
            f"{rules}\n"
            "- Preserve factual accuracy, task completion, and the host personality."
        )


def compile_expression(
    state: dict,
    *,
    max_rules: int = 6,
    max_characters: int = 1200,
) -> ExpressionTexture:
    """Compile observable writing constraints without inventing new facts."""
    emotion = state.get("emotion", {})
    relationship = state.get("relationship", {})
    inner = state.get("inner", {})
    circadian = state.get("circadian", {})
    concerns = state.get("concerns", {})
    rules: list[str] = []
    reasons: list[str] = []

    if float(emotion.get("anger", 0)) >= 4:
        rules.append(
            "Use direct, compact wording for disagreement; do not insult or infer motives."
        )
        reasons.append("anger")
    if float(emotion.get("sadness", 0)) >= 4:
        rules.append(
            "Allow slower pacing and honest incompleteness without using silence as punishment."
        )
        reasons.append("sadness")
    if float(relationship.get("unresolved_tension", 0)) >= 2:
        rules.append(
            "Make any intention to repair or approach explicit before explaining a position; "
            "do not let closeness sound like provocation."
        )
        reasons.append("unresolved tension")
    if float(inner.get("sharing_urge", 0)) >= 7:
        rules.append(
            "Offer one relevant thought or association instead of only answering reactively."
        )
        reasons.append("sharing urge")

    sleepiness = float(inner.get("sleepiness", 0))
    phase = str(circadian.get("phase", "awake"))
    if sleepiness >= 7 or phase in {"sleepy", "asleep", "half_awake", "waking"}:
        rules.append(
            "Make drowsiness observable in the response itself: use short clauses, few branches, "
            "and one to three compact paragraphs; avoid polished, fully alert exposition."
        )
        reasons.append("sleepiness")
    if sleepiness >= 9:
        rules.append(
            "Unless the task is urgent, respond only to the most important immediate point."
        )
        reasons.append("extreme sleepiness")
    if phase in {"asleep", "half_awake"}:
        rules.append(
            "Treat the message as a brief rousing, not proof of getting up. Do not claim to be "
            "fully awake or getting out of bed; keep the first response fragmentary and half-awake."
        )
        reasons.append(phase)
    elif phase == "waking":
        rules.append("Recover coherence gradually while retaining some drowsiness.")
        reasons.append(phase)

    active_concerns = [
        value
        for value in concerns.values()
        if isinstance(value, dict) and str(value.get("status", "")).upper() in {"OPEN", "EASING"}
    ]
    if active_concerns:
        strongest = max(active_concerns, key=lambda value: float(value.get("intensity", 0)))
        summary = str(strongest.get("summary", "an unresolved issue"))
        rules.append(
            f"Keep the active concern in view ({summary}), but mention it only when relevant. "
            "Show repair through a concrete, legible approach instead of pressure or accusation."
        )
        reasons.append("active concern")

    if phase in {"sleepy", "asleep", "half_awake", "waking"}:
        rules.append(
            "Circadian state has priority over stylistic intensity: preserve necessary content and "
            "safety, but render it through the current level of alertness."
        )

    if not rules:
        rules.append("Use a stable, natural cadence without artificially performing a state.")
        reasons.append("neutral")
    budgeted = _budget_guidance(rules, max_rules=max_rules, max_characters=max_characters)
    return ExpressionTexture(budgeted, reasons, omitted_rules=len(rules) - len(budgeted))


def _budget_guidance(rules: list[str], *, max_rules: int, max_characters: int) -> list[str]:
    """Keep prompt cost bounded while retaining alertness-critical instructions first."""
    if max_rules < 1 or max_characters < 1:
        return []
    priority_markers = (
        "Circadian state has priority",
        "Treat the message as a brief rousing",
        "Recover coherence gradually",
        "Make drowsiness observable",
    )
    ranked = sorted(
        enumerate(rules),
        key=lambda item: (not any(marker in item[1] for marker in priority_markers), item[0]),
    )
    selected: list[tuple[int, str]] = []
    used = 0
    for index, rule in ranked:
        cost = len(rule) + 2
        if len(selected) >= max_rules or used + cost > max_characters:
            continue
        selected.append((index, rule))
        used += cost
    return [rule for _, rule in sorted(selected)]
