"""
Onboarding — статус guided-первого запуска.

Шаги: bank (обязательный) → onec (рекомендуется) → telegram (опционально, owner).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StepId = Literal["bank", "onec", "telegram"]


@dataclass
class OnboardingFacts:
    bank_done: bool
    onec_done: bool
    telegram_done: bool
    dismissed: bool
    skipped_onec: bool
    skipped_telegram: bool
    is_owner: bool


@dataclass
class OnboardingStep:
    id: StepId
    done: bool
    required: bool
    skipped: bool


def compute_current_step(facts: OnboardingFacts) -> StepId | None:
    if facts.dismissed:
        return None
    if not facts.bank_done:
        return "bank"
    if not facts.onec_done and not facts.skipped_onec:
        return "onec"
    if facts.is_owner and not facts.telegram_done and not facts.skipped_telegram:
        return "telegram"
    return None


def compute_onboarding(facts: OnboardingFacts) -> dict:
    current = compute_current_step(facts)
    steps = [
        OnboardingStep(id="bank", done=facts.bank_done, required=True, skipped=False),
        OnboardingStep(
            id="onec",
            done=facts.onec_done,
            required=False,
            skipped=facts.skipped_onec and not facts.onec_done,
        ),
        OnboardingStep(
            id="telegram",
            done=facts.telegram_done,
            required=False,
            skipped=facts.skipped_telegram and not facts.telegram_done,
        ),
    ]
    show_wizard = current is not None
    show_banner = (
        facts.bank_done
        and facts.dismissed
        and (
            (not facts.onec_done and not facts.skipped_onec)
            or (facts.is_owner and not facts.telegram_done and not facts.skipped_telegram)
        )
    )
    return {
        "steps": [
            {
                "id": s.id,
                "done": s.done,
                "required": s.required,
                "skipped": s.skipped,
            }
            for s in steps
        ],
        "current_step": current,
        "show_wizard": show_wizard,
        "show_banner": show_banner,
        "dismissed": facts.dismissed,
    }
