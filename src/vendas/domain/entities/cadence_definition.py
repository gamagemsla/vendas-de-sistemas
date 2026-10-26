"""Cadence Definition Schema - Versioned cadence configuration with Pydantic v2."""

from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from vendas.domain.policies.cadence_policy import CadenceStep as DomainCadenceStep


class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class FallbackTrigger(str, Enum):
    ON_FAILURE = "on_failure"
    ON_CONSECUTIVE_FAILURES = "on_consecutive_failures"
    NEVER = "never"


class CadenceStepSchema(BaseModel):
    """Definition of a single cadence step (immutable, validated)."""

    step_number: Annotated[int, Field(ge=1, description="Sequential step number (1-indexed)")]
    channel: Channel
    template_name: Annotated[str, Field(min_length=1, max_length=100)]
    delay_hours: Annotated[
        int, Field(ge=0, description="Delay in hours until this step (relative to previous)")
    ]
    is_fallback: bool = False
    fallback_trigger: FallbackTrigger = FallbackTrigger.NEVER
    max_consecutive_failures: Annotated[int, Field(ge=1, default=2)] = 2

    @field_validator("delay_hours", mode="before")
    @classmethod
    def _parse_delay(cls, v: int | str | timedelta) -> int:
        if isinstance(v, timedelta):
            return int(v.total_seconds() // 3600)
        if isinstance(v, str):
            v = v.strip().lower()
            if v.endswith("h"):
                return int(v[:-1])
            if v.endswith("d"):
                return int(v[:-1]) * 24
            if v.endswith("m"):
                return max(1, int(v[:-1]) // 60)
        return int(v)

    def to_timedelta(self) -> timedelta:
        return timedelta(hours=self.delay_hours)


class CadenceDefinitionSchema(BaseModel):
    """Versioned schema for a complete commercial cadence definition."""

    version: Annotated[
        str, Field(pattern=r"^\d+\.\d+\.\d+$", description="SemVer: major.minor.patch")
    ]
    name: Annotated[str, Field(min_length=1, max_length=50, pattern=r"^[a-z_][a-z0-9_]*$")]
    description: str | None = None
    steps: Annotated[list[CadenceStepSchema], Field(min_length=1, max_length=20)]
    max_steps: Annotated[int, Field(ge=1, le=20)]
    default_fallback_channel: Channel = Channel.EMAIL
    global_fallback_trigger: FallbackTrigger = FallbackTrigger.ON_CONSECUTIVE_FAILURES
    global_max_consecutive_failures: Annotated[int, Field(ge=1, default=2)] = 2

    @model_validator(mode="after")
    def _validate_steps(self) -> CadenceDefinitionSchema:
        # 1. step_numbers must be sequential 1..N
        expected = list(range(1, len(self.steps) + 1))
        actual = [s.step_number for s in self.steps]
        if actual != expected:
            raise ValueError(
                f"step_numbers must be sequential 1..{len(self.steps)}, found: {actual}"
            )

        # 2. max_steps must be >= number of defined steps
        if self.max_steps < len(self.steps):
            raise ValueError(
                f"max_steps ({self.max_steps}) must be >= number of defined steps ({len(self.steps)})"
            )

        # 3. At least one non-fallback step must exist
        if all(s.is_fallback for s in self.steps):
            raise ValueError("Cadence must have at least one non-fallback step")

        # 4. Fallback steps must come after non-fallback steps
        seen_fallback = False
        for s in self.steps:
            if s.is_fallback:
                seen_fallback = True
            elif seen_fallback:
                raise ValueError("Non-fallback steps cannot appear after fallback steps")

        return self

    def to_policy_steps(self) -> list[DomainCadenceStep]:
        """Convert to domain CadenceStep list for CadencePolicy."""
        from vendas.domain.policies.cadence_policy import Channel as DomainChannel

        return [
            DomainCadenceStep(
                step_number=s.step_number,
                channel=DomainChannel(s.channel.value),
                template_name=s.template_name,
                delay=s.to_timedelta(),
                is_fallback=s.is_fallback,
            )
            for s in self.steps
        ]


# In-memory registry of cadence definitions
CADENCE_REGISTRY: dict[str, CadenceDefinitionSchema] = {}


def register_cadence(definition: CadenceDefinitionSchema) -> None:
    key = f"{definition.name}@v{definition.version}"
    if key in CADENCE_REGISTRY:
        raise ValueError(f"Cadence already registered: {key}")
    CADENCE_REGISTRY[key] = definition


def get_cadence(name: str, version: str | None = None) -> CadenceDefinitionSchema:
    if version:
        key = f"{name}@v{version}"
        if key not in CADENCE_REGISTRY:
            raise KeyError(f"Cadence not found: {key}")
        return CADENCE_REGISTRY[key]
    # Return highest version available for the name
    candidates = [v for k, v in CADENCE_REGISTRY.items() if k.startswith(f"{name}@v")]
    if not candidates:
        raise KeyError(f"No cadence found for: {name}")
    return max(candidates, key=lambda c: tuple(map(int, c.version.split("."))))
