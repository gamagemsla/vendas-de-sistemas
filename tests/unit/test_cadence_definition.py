"""Unit tests for CadenceDefinitionSchema and related functionality."""

from __future__ import annotations

from datetime import timedelta

from vendas.domain.entities.cadence_definition import (
    CadenceStepSchema,
    Channel,
    FallbackTrigger,
)


class TestCadenceStepSchema:
    """Tests for CadenceStepSchema validation and conversion."""

    def test_valid_step_creation(self):
        step = CadenceStepSchema(
            step_number=1,
            channel=Channel.WHATSAPP,
            template_name="initial_contact",
            delay_hours=0,
        )
        assert step.step_number == 1
        assert step.channel == Channel.WHATSAPP
        assert step.template_name == "initial_contact"
        assert step.delay_hours == 0
        assert step.is_fallback is False

    def test_delay_parsing_from_string_hours(self):
        step = CadenceStepSchema(
            step_number=1,
            channel=Channel.WHATSAPP,
            template_name="test",
            delay_hours="48h",
        )
        assert step.delay_hours == 48

    def test_delay_parsing_from_string_days(self):
        step = CadenceStepSchema(
            step_number=1,
            channel=Channel.WHATSAPP,
            template_name="test",
            delay_hours="2d",
        )
        assert step.delay_hours == 48

    def test_delay_parsing_from_string_minutes(self):
        step = CadenceStepSchema(
            step_number=1,
            channel=Channel.WHATSAPP,
            template_name="test",
            delay_hours="30m",
        )
        assert step.delay_hours == 1  # 30 minutes rounds up to 1 hour

    def test_delay_parsing_from_timedelta(self):
        step = CadenceStepSchema(
            step_number=1,
            channel=Channel.WHATSAPP,
            template_name="test",
            delay_hours=timedelta(hours=3),
        )
        assert step.delay_hours == 3

    def test_to_timedelta_conversion(self):
        step = CadenceStepSchema(
            step_number=1,
            channel=Channel.WHATSAPP,
            template_name="test",
            delay_hours=48,
        )
        assert step.to_timedelta() == timedelta(hours=48)

    def test_fallback_step_fields(self):
        step = CadenceStepSchema(
            step_number=5,
            channel=Channel.EMAIL,
            template_name="fallback_email_1",
            delay_hours=48,
            is_fallback=True,
            fallback_trigger=FallbackTrigger.ON_CONSECUTIVE_FAILURES,
            max_consecutive_failures=2,
        )
        assert step.is_fallback is True
        assert step.fallback_trigger == FallbackTrigger.ON_CONSECUTIVE_FAILURES
        assert step.max_consecutive_failures == 2


import pytest

from vendas.domain.entities.cadence_definition import (
    CADENCE_REGISTRY,
    CadenceDefinitionSchema,
    get_cadence,
    register_cadence,
)
from vendas.domain.policies.cadence_policy import CadencePolicy
from vendas.domain.policies.cadence_policy import CadenceStep as DomainCadenceStep


class TestCadenceDefinitionSchema:
    """Tests for CadenceDefinitionSchema validation."""

    def test_valid_definition(self):
        definition = CadenceDefinitionSchema(
            version="1.0.0",
            name="test_cadence",
            steps=[
                CadenceStepSchema(
                    step_number=1, channel=Channel.WHATSAPP, template_name="step1", delay_hours=0
                ),
                CadenceStepSchema(
                    step_number=2,
                    channel=Channel.EMAIL,
                    template_name="step2",
                    delay_hours=24,
                    is_fallback=True,
                ),
            ],
            max_steps=2,
        )
        assert definition.version == "1.0.0"
        assert definition.name == "test_cadence"
        assert len(definition.steps) == 2
        assert definition.max_steps == 2

    def test_rejects_non_sequential_steps(self):
        with pytest.raises(ValueError, match="step_numbers must be sequential"):
            CadenceDefinitionSchema(
                version="1.0.0",
                name="test_cadence",
                steps=[
                    CadenceStepSchema(
                        step_number=1,
                        channel=Channel.WHATSAPP,
                        template_name="step1",
                        delay_hours=0,
                    ),
                    CadenceStepSchema(
                        step_number=3, channel=Channel.EMAIL, template_name="step2", delay_hours=24
                    ),
                ],
                max_steps=3,
            )

    def test_rejects_invalid_version_format(self):
        with pytest.raises(ValueError, match="version"):
            CadenceDefinitionSchema(
                version="1.0",  # Not SemVer
                name="test_cadence",
                steps=[
                    CadenceStepSchema(
                        step_number=1,
                        channel=Channel.WHATSAPP,
                        template_name="step1",
                        delay_hours=0,
                    ),
                ],
                max_steps=1,
            )

    def test_rejects_fallback_before_non_fallback(self):
        with pytest.raises(
            ValueError, match="Non-fallback steps cannot appear after fallback steps"
        ):
            CadenceDefinitionSchema(
                version="1.0.0",
                name="test_cadence",
                steps=[
                    CadenceStepSchema(
                        step_number=1,
                        channel=Channel.EMAIL,
                        template_name="fallback1",
                        delay_hours=0,
                        is_fallback=True,
                    ),
                    CadenceStepSchema(
                        step_number=2,
                        channel=Channel.WHATSAPP,
                        template_name="step2",
                        delay_hours=24,
                    ),
                ],
                max_steps=2,
            )

    def test_rejects_all_fallback_steps(self):
        with pytest.raises(ValueError, match="must have at least one non-fallback step"):
            CadenceDefinitionSchema(
                version="1.0.0",
                name="test_cadence",
                steps=[
                    CadenceStepSchema(
                        step_number=1,
                        channel=Channel.EMAIL,
                        template_name="fallback1",
                        delay_hours=0,
                        is_fallback=True,
                    ),
                ],
                max_steps=1,
            )

    def test_rejects_max_steps_less_than_steps_count(self):
        with pytest.raises(ValueError, match="max_steps.*must be >="):
            CadenceDefinitionSchema(
                version="1.0.0",
                name="test_cadence",
                steps=[
                    CadenceStepSchema(
                        step_number=1,
                        channel=Channel.WHATSAPP,
                        template_name="step1",
                        delay_hours=0,
                    ),
                    CadenceStepSchema(
                        step_number=2, channel=Channel.EMAIL, template_name="step2", delay_hours=24
                    ),
                ],
                max_steps=1,
            )

    def test_to_policy_steps_conversion(self):
        definition = CadenceDefinitionSchema(
            version="1.0.0",
            name="test_cadence",
            steps=[
                CadenceStepSchema(
                    step_number=1, channel=Channel.WHATSAPP, template_name="initial", delay_hours=0
                ),
                CadenceStepSchema(
                    step_number=2,
                    channel=Channel.WHATSAPP,
                    template_name="followup",
                    delay_hours=48,
                ),
                CadenceStepSchema(
                    step_number=3,
                    channel=Channel.EMAIL,
                    template_name="fallback",
                    delay_hours=24,
                    is_fallback=True,
                ),
            ],
            max_steps=3,
        )
        policy_steps = definition.to_policy_steps()
        assert len(policy_steps) == 3
        assert all(isinstance(s, DomainCadenceStep) for s in policy_steps)
        assert policy_steps[0].step_number == 1
        assert policy_steps[0].channel.value == "whatsapp"
        assert policy_steps[0].delay == timedelta(hours=0)
        assert policy_steps[2].is_fallback is True


class TestCadenceRegistry:
    """Tests for the in-memory cadence registry."""

    def setup_method(self):
        # Clear registry before each test
        CADENCE_REGISTRY.clear()

    def test_register_and_get_cadence(self):
        definition = CadenceDefinitionSchema(
            version="1.0.0",
            name="test_cadence",
            steps=[
                CadenceStepSchema(
                    step_number=1, channel=Channel.WHATSAPP, template_name="step1", delay_hours=0
                ),
            ],
            max_steps=1,
        )
        register_cadence(definition)
        retrieved = get_cadence("test_cadence", "1.0.0")
        assert retrieved.version == "1.0.0"
        assert retrieved.name == "test_cadence"

    def test_get_latest_version_when_no_version_specified(self):
        definition_v1 = CadenceDefinitionSchema(
            version="1.0.0",
            name="test_cadence",
            steps=[
                CadenceStepSchema(
                    step_number=1, channel=Channel.WHATSAPP, template_name="step1", delay_hours=0
                )
            ],
            max_steps=1,
        )
        definition_v2 = CadenceDefinitionSchema(
            version="2.0.0",
            name="test_cadence",
            steps=[
                CadenceStepSchema(
                    step_number=1, channel=Channel.WHATSAPP, template_name="step1", delay_hours=0
                )
            ],
            max_steps=1,
        )
        register_cadence(definition_v1)
        register_cadence(definition_v2)
        latest = get_cadence("test_cadence")
        assert latest.version == "2.0.0"

    def test_raises_on_duplicate_registration(self):
        definition = CadenceDefinitionSchema(
            version="1.0.0",
            name="test_cadence",
            steps=[
                CadenceStepSchema(
                    step_number=1, channel=Channel.WHATSAPP, template_name="step1", delay_hours=0
                )
            ],
            max_steps=1,
        )
        register_cadence(definition)
        with pytest.raises(ValueError, match="already registered"):
            register_cadence(definition)

    def test_raises_on_not_found(self):
        with pytest.raises(KeyError, match="No cadence found for"):
            get_cadence("nonexistent")


class TestProcessCadenceStepScheduling:
    """Integration tests for ProcessCadenceStepCommand scheduling using the policy."""

    def test_advance_step_uses_policy_delay(self):
        """Test that the command calculates next_run_at using policy delay, not immediate now."""
        # This test will be expanded when we have the full command integration
        # For now, verify the policy returns correct delays
        policy = CadencePolicy()
        # Step 0 -> step 1 has delay 0
        delay = policy.get_delay_until_next(0)
        assert delay == timedelta(minutes=0)
        # Step 1 -> step 2 has delay 2 days
        delay = policy.get_delay_until_next(1)
        assert delay == timedelta(days=2)
        # Step 3 -> step 4 has delay 5 days
        delay = policy.get_delay_until_next(3)
        assert delay == timedelta(days=5)
