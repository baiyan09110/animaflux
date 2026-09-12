"""AnimaFlux: continuity beneath the conversation."""

from .engine import StateEngine
from .expression import ExpressionTexture, compile_expression
from .circadian import CircadianPolicy
from .models import AgentState, Appraisal, MemoryInfluence, StateDelta
from .storage import JsonStore, SQLiteStore, StateStore

__all__ = [
    "AgentState",
    "Appraisal",
    "CircadianPolicy",
    "ExpressionTexture",
    "JsonStore",
    "MemoryInfluence",
    "SQLiteStore",
    "StateDelta",
    "StateEngine",
    "StateStore",
    "compile_expression",
]

__version__ = "0.1.0.dev0"
