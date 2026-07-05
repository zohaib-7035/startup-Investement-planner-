import pytest
from data.profile_advisor import (
    get_profile_recommendations,
    _BUY_THRESHOLD,
)


class TestOutputSchema:
    def test_default_profiles_has_three_keys(self):
        result = get_profile_recommendations("NVDA", "BUY", "HIGH")
        assert set(result.keys()) == {"conservative", "balanced", "aggressive"}

    def test_each_profile_has_required_keys(self):
        result = get_profile_recommendations("NVDA", "BUY", "HIGH")
        for profile in result.values():
            assert set(profile.keys()) == {"action", "position_size", "reasoning"}

    def test_position_size_is_float(self):
        result = get_profile_recommendations("NVDA", "BUY", "HIGH")
        for profile in result.values():
            assert isinstance(profile["position_size"], float)

    def test_action_is_string(self):
        result = get_profile_recommendations("NVDA", "BUY", "HIGH")
        for profile in result.values():
            assert isinstance(profile["action"], str)

    def test_reasoning_is_string(self):
        result = get_profile_recommendations("NVDA", "BUY", "HIGH")
        for profile in result.values():
            assert isinstance(profile["reasoning"], str)


class TestFormulaVerification:
    def test_buy_high_conservative_position_and_action(self):
        result = get_profile_recommendations("NVDA", "BUY", "HIGH")
        assert result["conservative"]["position_size"] == pytest.approx(0.10)
        assert result["conservative"]["action"] == "HOLD"

    def test_buy_high_balanced_position_and_action(self):
        result = get_profile_recommendations("NVDA", "BUY", "HIGH")
        assert result["balanced"]["position_size"] == pytest.approx(0.25)
        assert result["balanced"]["action"] == "HOLD"

    def test_buy_high_aggressive_position_and_action(self):
        result = get_profile_recommendations("NVDA", "BUY", "HIGH")
        assert result["aggressive"]["position_size"] == pytest.approx(0.45)
        assert result["aggressive"]["action"] == "BUY"

    def test_buy_low_aggressive_position_and_action(self):
        result = get_profile_recommendations("NVDA", "BUY", "LOW")
        assert result["aggressive"]["position_size"] == pytest.approx(0.9)
        assert result["aggressive"]["action"] == "BUY"

    def test_buy_medium_balanced_position(self):
        result = get_profile_recommendations("NVDA", "BUY", "MEDIUM")
        assert result["balanced"]["position_size"] == pytest.approx(0.375)

    def test_conservative_lte_balanced_lte_aggressive_on_buy(self):
        for vol in ("LOW", "MEDIUM", "HIGH"):
            result = get_profile_recommendations("AAPL", "BUY", vol)
            c = result["conservative"]["position_size"]
            b = result["balanced"]["position_size"]
            a = result["aggressive"]["position_size"]
            assert c <= b <= a


class TestSignalBehaviour:
    def test_sell_signal_all_profiles_zero_hold(self):
        result = get_profile_recommendations("NVDA", "SELL", "HIGH")
        for profile in result.values():
            assert profile["position_size"] == pytest.approx(0.0)
            assert profile["action"] == "HOLD"

    def test_hold_signal_all_profiles_zero_hold(self):
        result = get_profile_recommendations("NVDA", "HOLD", "LOW")
        for profile in result.values():
            assert profile["position_size"] == pytest.approx(0.0)
            assert profile["action"] == "HOLD"

    def test_title_case_signal_same_result_as_uppercase(self):
        result_upper = get_profile_recommendations("NVDA", "BUY", "HIGH")
        result_title = get_profile_recommendations("NVDA", "Buy", "HIGH")
        for name in result_upper:
            assert result_upper[name]["position_size"] == pytest.approx(
                result_title[name]["position_size"]
            )

    def test_lowercase_signal_accepted(self):
        result = get_profile_recommendations("NVDA", "buy", "HIGH")
        assert result["aggressive"]["position_size"] == pytest.approx(0.45)

    def test_mixed_case_volatility_accepted(self):
        result = get_profile_recommendations("NVDA", "BUY", "high")
        assert result["aggressive"]["position_size"] == pytest.approx(0.45)


class TestThresholdBoundary:
    def test_position_size_exactly_0_3_is_hold(self):
        # BUY + HIGH: 1.0 * 0.5 * 0.6 = 0.30 — at threshold, not above it
        profiles = [{"name": "exact", "risk_tol": 0.6}]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert result["exact"]["position_size"] == pytest.approx(0.30)
        assert result["exact"]["action"] == "HOLD"

    def test_position_size_just_above_0_3_is_buy(self):
        # BUY + HIGH: 1.0 * 0.5 * 0.62 = 0.31
        profiles = [{"name": "near", "risk_tol": 0.62}]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert result["near"]["position_size"] > _BUY_THRESHOLD
        assert result["near"]["action"] == "BUY"

    def test_risk_tol_zero_gives_position_size_zero(self):
        profiles = [{"name": "zero", "risk_tol": 0.0}]
        result = get_profile_recommendations("NVDA", "BUY", "LOW", profiles=profiles)
        assert result["zero"]["position_size"] == pytest.approx(0.0)

    def test_risk_tol_one_buy_low_gives_position_size_one(self):
        profiles = [{"name": "max_risk", "risk_tol": 1.0}]
        result = get_profile_recommendations("NVDA", "BUY", "LOW", profiles=profiles)
        assert result["max_risk"]["position_size"] == pytest.approx(1.0)


class TestCustomProfiles:
    def test_single_custom_profile_is_only_key(self):
        profiles = [{"name": "ultra_safe", "risk_tol": 0.05}]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert list(result.keys()) == ["ultra_safe"]

    def test_custom_profile_position_size_formula(self):
        # BUY + HIGH: 1.0 * 0.5 * 0.05 = 0.025
        profiles = [{"name": "ultra_safe", "risk_tol": 0.05}]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert result["ultra_safe"]["position_size"] == pytest.approx(0.025)


class TestPreflightGuards:
    def test_unknown_signal_returns_empty_dict(self):
        result = get_profile_recommendations("NVDA", "STRONG_BUY", "HIGH")
        assert result == {}

    def test_unknown_volatility_returns_empty_dict(self):
        result = get_profile_recommendations("NVDA", "BUY", "EXTREME")
        assert result == {}

    def test_all_invalid_profiles_returns_empty_dict(self):
        profiles = [{"name": "", "risk_tol": 0.5}, {"risk_tol": 0.5}]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert result == {}

    def test_one_valid_one_invalid_profile_returns_valid_only(self):
        profiles = [
            {"name": "good", "risk_tol": 0.5},
            {"name": "", "risk_tol": 0.5},
        ]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert list(result.keys()) == ["good"]

    def test_profile_missing_name_key_is_skipped(self):
        profiles = [{"risk_tol": 0.5}]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert result == {}

    def test_profile_risk_tol_above_one_is_skipped(self):
        profiles = [{"name": "too_risky", "risk_tol": 1.1}]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert result == {}

    def test_profile_risk_tol_below_zero_is_skipped(self):
        profiles = [{"name": "negative", "risk_tol": -0.1}]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert result == {}

    def test_non_dict_profile_entry_is_skipped(self):
        profiles = ["not_a_dict", 42, None]
        result = get_profile_recommendations("NVDA", "BUY", "HIGH", profiles=profiles)
        assert result == {}
