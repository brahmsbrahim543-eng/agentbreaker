"""Data types for AgentBreaker SDK responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CarbonImpact:
    """Carbon footprint data for a single step and cumulative session.

    Attributes:
        kwh: Energy consumed by this step in kilowatt-hours.
        co2_grams: CO2 emitted by this step in grams.
        total_kwh: Cumulative energy consumed by the agent session.
        total_co2_grams: Cumulative CO2 emitted by the agent session.
    """

    kwh: float
    co2_grams: float
    total_kwh: float
    total_co2_grams: float


@dataclass(frozen=True)
class StepResult:
    """Risk assessment returned after tracking an agent step.

    Attributes:
        step_number: Sequential step index within the agent session.
        risk_score: Aggregate risk score between 0.0 and 1.0.
        risk_breakdown: Per-dimension risk scores (e.g. ``{"loop": 0.3, "cost": 0.1}``).
        action: Decision made by AgentBreaker: ``"ok"``, ``"warn"``, or ``"kill"``.
        warnings: Human-readable warning messages, if any.
        carbon_impact: Carbon footprint metrics, or *None* if unavailable.
    """

    step_number: int
    risk_score: float
    risk_breakdown: dict[str, Any]
    action: str
    warnings: list[str] = field(default_factory=list)
    carbon_impact: dict[str, Any] | None = None
