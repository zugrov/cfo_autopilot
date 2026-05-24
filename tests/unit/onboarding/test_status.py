"""
Unit-тесты: onboarding status computation.
"""
from app.services.onboarding.status import OnboardingFacts, compute_onboarding


def _facts(**kwargs) -> OnboardingFacts:
    defaults = dict(
        bank_done=False,
        onec_done=False,
        telegram_done=False,
        dismissed=False,
        skipped_onec=False,
        skipped_telegram=False,
        is_owner=True,
    )
    defaults.update(kwargs)
    return OnboardingFacts(**defaults)


class TestComputeOnboarding:
    def test_new_company_shows_wizard_at_bank(self):
        result = compute_onboarding(_facts())
        assert result["show_wizard"] is True
        assert result["current_step"] == "bank"
        assert result["dismissed"] is False

    def test_bank_done_moves_to_onec(self):
        result = compute_onboarding(_facts(bank_done=True))
        assert result["current_step"] == "onec"
        assert result["show_wizard"] is True

    def test_onec_skipped_moves_to_telegram(self):
        result = compute_onboarding(
            _facts(bank_done=True, skipped_onec=True)
        )
        assert result["current_step"] == "telegram"

    def test_all_done_no_wizard(self):
        result = compute_onboarding(
            _facts(bank_done=True, onec_done=True, telegram_done=True)
        )
        assert result["current_step"] is None
        assert result["show_wizard"] is False

    def test_dismissed_hides_wizard(self):
        result = compute_onboarding(_facts(dismissed=True))
        assert result["show_wizard"] is False
        assert result["current_step"] is None

    def test_dismissed_with_pending_optional_shows_banner(self):
        result = compute_onboarding(
            _facts(bank_done=True, dismissed=True, onec_done=False)
        )
        assert result["show_wizard"] is False
        assert result["show_banner"] is True

    def test_non_owner_skips_telegram_step(self):
        result = compute_onboarding(
            _facts(bank_done=True, onec_done=True, is_owner=False)
        )
        assert result["current_step"] is None

    def test_telegram_skipped_completes_wizard(self):
        result = compute_onboarding(
            _facts(bank_done=True, onec_done=True, skipped_telegram=True)
        )
        assert result["current_step"] is None
