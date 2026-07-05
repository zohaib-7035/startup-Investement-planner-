import pytest
from unittest.mock import patch, MagicMock

from data.parallel_runner import (
    run_agents_parallel,
    _compute_rsi,
    _run_technical_agent,
    _run_fundamentals_agent,
    _run_sentiment_agent,
    _run_risk_agent,
    _EMPTY_RESULT,
    _TECHNICAL_FALLBACK,
    _FUNDAMENTALS_FALLBACK,
    _SENTIMENT_FALLBACK,
    _MACRO_FALLBACK,
    _RISK_FALLBACK,
)

# ── Shared test data ──────────────────────────────────────────────────────────

_HISTORY_20 = [
    {
        "date": f"2024-01-{i+1:02d}",
        "close": float(100 + i),
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "volume": 1000,
    }
    for i in range(20)
]
_HISTORY_INCREASING = [
    {"date": f"2024-01-{i+1:02d}", "close": float(100 + i * 2),
     "open": 100.0, "high": 102.0, "low": 99.0, "volume": 1000}
    for i in range(30)
]
_HISTORY_DECREASING = [
    {"date": f"2024-01-{i+1:02d}", "close": float(200 - i * 2),
     "open": 200.0, "high": 201.0, "low": 198.0, "volume": 1000}
    for i in range(30)
]
_FUNDAMENTALS_POS = {
    "pe_ratio": 15.0, "pb_ratio": 2.0, "debt_to_equity": 0.5,
    "eps_last": 5.0, "eps_surprise": 0.3,
}
_FUNDAMENTALS_NEG = {**_FUNDAMENTALS_POS, "eps_surprise": -0.2}
_FUNDAMENTALS_NONE = {**_FUNDAMENTALS_POS, "eps_surprise": None}
_REC_BUY_TITLE = {"action": "Buy", "confidence": 0.85, "reason": "RSI in buy zone."}
_SENTIMENT_POS = {"sentiment": "Positive", "score": 1, "reason": "Good news."}
_SENTIMENT_NEG = {"sentiment": "Negative", "score": -1, "reason": "Bad news."}
_SENTIMENT_NEUTRAL = {"sentiment": "Neutral", "score": 0, "reason": "Mixed."}
_RISK_MEDIUM = {
    "var_1w_95": 0.02, "cvar_1w_95": 0.03, "portfolio_volatility": 0.15,
    "concentration_risk": 1.0, "risk_level": "MEDIUM", "warnings": None,
}
_RISK_HIGH = {**_RISK_MEDIUM, "risk_level": "HIGH"}
_RISK_NONE_LEVEL = {**_RISK_MEDIUM, "risk_level": None}
_AGGREGATE_BUY = {
    "final_action": "BUY", "confidence": 0.80,
    "reasoning": "Votes: ...", "conflicts": [],
}

_TICKER = "NVDA"
_START = "2024-01-01"
_END = "2024-01-31"
_NEWS = "Strong quarterly earnings beat."


def _setup_mocks(m_hist, m_fund, m_rec, m_sent, m_risk, m_agg):
    m_hist.return_value = _HISTORY_20
    m_fund.return_value = _FUNDAMENTALS_POS
    m_rec.return_value = _REC_BUY_TITLE
    m_sent.return_value = _SENTIMENT_POS
    m_risk.return_value = _RISK_MEDIUM
    m_agg.return_value = _AGGREGATE_BUY.copy()


# ── 1. TestComputeRsi ─────────────────────────────────────────────────────────

class TestComputeRsi:
    def test_returns_none_when_exactly_period_prices(self):
        # ≤ period → None (need strictly more than 14 for Wilder bootstrap)
        prices = [float(i) for i in range(1, 15)]
        assert _compute_rsi(prices) is None

    def test_returns_none_when_fewer_than_period_prices(self):
        prices = [float(i) for i in range(1, 10)]
        assert _compute_rsi(prices) is None

    def test_returns_float_for_sufficient_prices(self):
        prices = [float(100 + i) for i in range(20)]
        result = _compute_rsi(prices)
        assert isinstance(result, float)

    def test_rsi_within_valid_range(self):
        prices = [float(100 + i) for i in range(20)]
        result = _compute_rsi(prices)
        assert 0.0 <= result <= 100.0

    def test_all_same_prices_returns_float_or_none_without_raising(self):
        prices = [100.0] * 20
        result = _compute_rsi(prices)
        assert isinstance(result, (float, type(None)))

    def test_increasing_prices_rsi_above_50(self):
        close_prices = [float(c["close"]) for c in _HISTORY_INCREASING]
        result = _compute_rsi(close_prices)
        assert result > 50.0

    def test_decreasing_prices_rsi_below_50(self):
        close_prices = [float(c["close"]) for c in _HISTORY_DECREASING]
        result = _compute_rsi(close_prices)
        assert result < 50.0


# ── 2. TestWrapperTranslations ────────────────────────────────────────────────

class TestWrapperTranslations:
    @patch("data.parallel_runner.generate_recommendation", return_value=_REC_BUY_TITLE)
    @patch("data.parallel_runner.get_fundamentals", return_value=_FUNDAMENTALS_POS)
    @patch("data.parallel_runner.get_stock_history", return_value=_HISTORY_20)
    def test_technical_agent_uppercases_title_case_action(self, mh, mf, mr):
        result = _run_technical_agent(_TICKER, _START, _END)
        assert result["action"] == "BUY"

    @patch("data.parallel_runner.analyze_sentiment", return_value=_SENTIMENT_POS)
    def test_sentiment_score_plus1_maps_to_buy(self, _ms):
        result = _run_sentiment_agent(_NEWS)
        assert result["action"] == "BUY"

    @patch("data.parallel_runner.analyze_sentiment", return_value=_SENTIMENT_NEG)
    def test_sentiment_score_minus1_maps_to_sell(self, _ms):
        result = _run_sentiment_agent(_NEWS)
        assert result["action"] == "SELL"

    @patch("data.parallel_runner.analyze_sentiment", return_value=_SENTIMENT_NEUTRAL)
    def test_sentiment_score_0_maps_to_hold(self, _ms):
        result = _run_sentiment_agent(_NEWS)
        assert result["action"] == "HOLD"

    @patch("data.parallel_runner.calculate_risk_metrics", return_value=_RISK_HIGH)
    @patch("data.parallel_runner.get_stock_history", return_value=_HISTORY_20)
    def test_risk_agent_remaps_risk_level_to_level_key(self, _mh, _mr):
        result = _run_risk_agent(_TICKER, _START, _END)
        assert "level" in result
        assert result["level"] == "HIGH"

    @patch("data.parallel_runner.calculate_risk_metrics", return_value=_RISK_NONE_LEVEL)
    @patch("data.parallel_runner.get_stock_history", return_value=_HISTORY_20)
    def test_risk_agent_defaults_none_risk_level_to_low(self, _mh, _mr):
        result = _run_risk_agent(_TICKER, _START, _END)
        assert result["level"] == "LOW"

    @patch("data.parallel_runner.get_fundamentals", return_value=_FUNDAMENTALS_POS)
    def test_fundamentals_agent_pos_eps_returns_buy(self, _mf):
        result = _run_fundamentals_agent(_TICKER)
        assert result["action"] == "BUY"

    @patch("data.parallel_runner.get_fundamentals", return_value=_FUNDAMENTALS_NEG)
    def test_fundamentals_agent_neg_eps_returns_sell(self, _mf):
        result = _run_fundamentals_agent(_TICKER)
        assert result["action"] == "SELL"

    @patch("data.parallel_runner.get_fundamentals", return_value=_FUNDAMENTALS_NONE)
    def test_fundamentals_agent_none_eps_returns_hold_zero_confidence(self, _mf):
        result = _run_fundamentals_agent(_TICKER)
        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0

    @patch("data.parallel_runner.get_fundamentals", return_value=_FUNDAMENTALS_POS)
    def test_fundamentals_agent_confidence_0_70_when_eps_present(self, _mf):
        result = _run_fundamentals_agent(_TICKER)
        assert result["confidence"] == pytest.approx(0.70)


# ── 3. TestOutputSchema ───────────────────────────────────────────────────────

class TestOutputSchema:
    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_returns_dict_with_exactly_four_keys(
        self, mh, mf, mr, ms, mri, magg
    ):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert set(result.keys()) == {"final_action", "confidence", "reasoning", "conflicts"}

    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_final_action_is_string(self, mh, mf, mr, ms, mri, magg):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert isinstance(result["final_action"], str)

    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_confidence_is_float(self, mh, mf, mr, ms, mri, magg):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_conflicts_is_list(self, mh, mf, mr, ms, mri, magg):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert isinstance(result["conflicts"], list)

    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_reasoning_is_string(self, mh, mf, mr, ms, mri, magg):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert isinstance(result["reasoning"], str)

    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_aggregate_signals_exception_returns_empty_result(
        self, mh, mf, mr, ms, mri, magg
    ):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        magg.side_effect = RuntimeError("crash in aggregator")
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert result == _EMPTY_RESULT


# ── 4. TestAllAgentsSucceed ───────────────────────────────────────────────────

class TestAllAgentsSucceed:
    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_aggregate_signals_called_exactly_once(
        self, mh, mf, mr, ms, mri, magg
    ):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        magg.assert_called_once()

    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_agent_outputs_has_five_expected_keys(
        self, mh, mf, mr, ms, mri, magg
    ):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        call_kwargs = magg.call_args[0][0]
        assert set(call_kwargs.keys()) == {
            "technical", "fundamentals", "sentiment", "macro", "risk"
        }

    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_result_flows_through_from_aggregate_signals(
        self, mh, mf, mr, ms, mri, magg
    ):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        expected = {"final_action": "SELL", "confidence": 0.60,
                    "reasoning": "Bears dominate.", "conflicts": ["c1"]}
        magg.return_value = expected.copy()
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert result == expected

    @patch("data.parallel_runner.aggregate_signals")
    @patch("data.parallel_runner.calculate_risk_metrics")
    @patch("data.parallel_runner.analyze_sentiment")
    @patch("data.parallel_runner.generate_recommendation")
    @patch("data.parallel_runner.get_fundamentals")
    @patch("data.parallel_runner.get_stock_history")
    def test_aggregate_signals_exception_returns_empty_result(
        self, mh, mf, mr, ms, mri, magg
    ):
        _setup_mocks(mh, mf, mr, ms, mri, magg)
        magg.side_effect = RuntimeError("crash in aggregator")
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert result == _EMPTY_RESULT


# ── 5. TestAgentFailureIsolation ──────────────────────────────────────────────

class TestAgentFailureIsolation:
    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", return_value={"level": "LOW"})
    @patch("data.parallel_runner._run_macro_agent", return_value={"action": "HOLD", "confidence": 0.0})
    @patch("data.parallel_runner._run_sentiment_agent", return_value={"action": "HOLD", "confidence": 0.50})
    @patch("data.parallel_runner._run_fundamentals_agent", return_value={"action": "BUY", "confidence": 0.70})
    @patch("data.parallel_runner._run_technical_agent", side_effect=RuntimeError("API down"))
    def test_one_agent_exception_returns_valid_result(
        self, _mt, _mf, _ms, _mm, _mr, _magg
    ):
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert set(result.keys()) == {"final_action", "confidence", "reasoning", "conflicts"}

    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", return_value={"level": "LOW"})
    @patch("data.parallel_runner._run_macro_agent", return_value={"action": "HOLD", "confidence": 0.0})
    @patch("data.parallel_runner._run_sentiment_agent", side_effect=ValueError("empty corpus"))
    @patch("data.parallel_runner._run_fundamentals_agent", return_value={"action": "BUY", "confidence": 0.70})
    @patch("data.parallel_runner._run_technical_agent", return_value={"action": "BUY", "confidence": 0.85})
    def test_sentiment_agent_exception_returns_valid_result(
        self, _mt, _mf, _ms, _mm, _mr, _magg
    ):
        result = run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        assert set(result.keys()) == {"final_action", "confidence", "reasoning", "conflicts"}

    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", side_effect=Exception("fail"))
    @patch("data.parallel_runner._run_macro_agent", side_effect=Exception("fail"))
    @patch("data.parallel_runner._run_sentiment_agent", side_effect=Exception("fail"))
    @patch("data.parallel_runner._run_fundamentals_agent", side_effect=Exception("fail"))
    @patch("data.parallel_runner._run_technical_agent", side_effect=Exception("fail"))
    def test_all_agents_failing_aggregate_still_called(
        self, _mt, _mf, _ms, _mm, _mr, magg
    ):
        run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS, max_retries=0)
        magg.assert_called_once()

    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", side_effect=Exception("fail"))
    @patch("data.parallel_runner._run_macro_agent", side_effect=Exception("fail"))
    @patch("data.parallel_runner._run_sentiment_agent", side_effect=Exception("fail"))
    @patch("data.parallel_runner._run_fundamentals_agent", side_effect=Exception("fail"))
    @patch("data.parallel_runner._run_technical_agent", side_effect=Exception("fail"))
    def test_all_agents_failing_fallbacks_passed_to_aggregate(
        self, _mt, _mf, _ms, _mm, _mr, magg
    ):
        run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS, max_retries=0)
        passed = magg.call_args[0][0]
        assert passed["technical"]["action"] == "HOLD"
        assert passed["risk"]["level"] == "LOW"


# ── 6. TestTimeoutGuard ───────────────────────────────────────────────────────

class TestTimeoutGuard:
    def test_zero_timeout_returns_empty_result(self):
        result = run_agents_parallel(_TICKER, _START, _END, timeout_seconds=0)
        assert result == _EMPTY_RESULT

    def test_negative_timeout_returns_empty_result(self):
        result = run_agents_parallel(_TICKER, _START, _END, timeout_seconds=-5)
        assert result == _EMPTY_RESULT

    @patch("data.parallel_runner.aggregate_signals")
    def test_zero_timeout_does_not_call_aggregate(self, magg):
        run_agents_parallel(_TICKER, _START, _END, timeout_seconds=0)
        magg.assert_not_called()

    def test_non_numeric_timeout_returns_empty_result(self):
        result = run_agents_parallel(_TICKER, _START, _END, timeout_seconds="bad")
        assert result == _EMPTY_RESULT


# ── 7. TestNewsShortCircuit ───────────────────────────────────────────────────

class TestNewsShortCircuit:
    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", return_value={"level": "LOW"})
    @patch("data.parallel_runner._run_macro_agent", return_value={"action": "HOLD", "confidence": 0.0})
    @patch("data.parallel_runner._run_sentiment_agent", return_value={"action": "BUY", "confidence": 0.75})
    @patch("data.parallel_runner._run_fundamentals_agent", return_value={"action": "BUY", "confidence": 0.70})
    @patch("data.parallel_runner._run_technical_agent", return_value={"action": "BUY", "confidence": 0.85})
    @patch("data.parallel_runner._run_news_agent")
    def test_news_texts_provided_skips_news_agent(
        self, mock_news, _mt, _mf, _ms, _mm, _mr, _magg
    ):
        run_agents_parallel(_TICKER, _START, _END, news_texts=_NEWS)
        mock_news.assert_not_called()

    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", return_value={"level": "LOW"})
    @patch("data.parallel_runner._run_macro_agent", return_value={"action": "HOLD", "confidence": 0.0})
    @patch("data.parallel_runner._run_fundamentals_agent", return_value={"action": "BUY", "confidence": 0.70})
    @patch("data.parallel_runner._run_technical_agent", return_value={"action": "BUY", "confidence": 0.85})
    @patch("data.parallel_runner._run_sentiment_agent")
    @patch("data.parallel_runner._run_news_agent")
    def test_news_texts_provided_passes_to_sentiment_agent(
        self, mock_news, mock_sent, _mt, _mf, _mm, _mr, _magg
    ):
        mock_sent.return_value = {"action": "BUY", "confidence": 0.75}
        run_agents_parallel(_TICKER, _START, _END, news_texts="custom text")
        mock_news.assert_not_called()
        mock_sent.assert_called_once_with("custom text")

    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", return_value={"level": "LOW"})
    @patch("data.parallel_runner._run_macro_agent", return_value={"action": "HOLD", "confidence": 0.0})
    @patch("data.parallel_runner._run_sentiment_agent", return_value={"action": "HOLD", "confidence": 0.50})
    @patch("data.parallel_runner._run_fundamentals_agent", return_value={"action": "BUY", "confidence": 0.70})
    @patch("data.parallel_runner._run_technical_agent", return_value={"action": "BUY", "confidence": 0.85})
    @patch("data.parallel_runner._run_news_agent", return_value="news from stub")
    def test_news_texts_none_calls_news_agent(
        self, mock_news, _mt, _mf, _ms, _mm, _mr, _magg
    ):
        run_agents_parallel(_TICKER, _START, _END, news_texts=None)
        mock_news.assert_called_once_with(_TICKER)


# ── 8. TestRetryBehaviour ─────────────────────────────────────────────────────

class TestRetryBehaviour:
    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", return_value={"level": "LOW"})
    @patch("data.parallel_runner._run_macro_agent", return_value={"action": "HOLD", "confidence": 0.0})
    @patch("data.parallel_runner._run_sentiment_agent", return_value={"action": "HOLD", "confidence": 0.50})
    @patch("data.parallel_runner._run_fundamentals_agent", return_value={"action": "BUY", "confidence": 0.70})
    @patch("data.parallel_runner._run_technical_agent", return_value={"action": "BUY", "confidence": 0.85})
    def test_max_retries_zero_still_produces_valid_result(
        self, _mt, _mf, _ms, _mm, _mr, _magg
    ):
        result = run_agents_parallel(
            _TICKER, _START, _END, news_texts=_NEWS, max_retries=0
        )
        assert set(result.keys()) == {"final_action", "confidence", "reasoning", "conflicts"}

    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", return_value={"level": "LOW"})
    @patch("data.parallel_runner._run_macro_agent", return_value={"action": "HOLD", "confidence": 0.0})
    @patch("data.parallel_runner._run_sentiment_agent", return_value={"action": "HOLD", "confidence": 0.50})
    @patch("data.parallel_runner._run_fundamentals_agent", return_value={"action": "BUY", "confidence": 0.70})
    @patch("data.parallel_runner._run_technical_agent")
    def test_agent_succeeds_on_second_attempt_uses_actual_result(
        self, mock_tech, _mf, _ms, _mm, _mr, magg
    ):
        success_value = {"action": "BUY", "confidence": 0.85}
        mock_tech.side_effect = [RuntimeError("first fail"), success_value]
        run_agents_parallel(
            _TICKER, _START, _END, news_texts=_NEWS, max_retries=2
        )
        passed = magg.call_args[0][0]
        assert passed["technical"] == success_value

    @patch("data.parallel_runner.aggregate_signals", return_value=_AGGREGATE_BUY.copy())
    @patch("data.parallel_runner._run_risk_agent", return_value={"level": "LOW"})
    @patch("data.parallel_runner._run_macro_agent", return_value={"action": "HOLD", "confidence": 0.0})
    @patch("data.parallel_runner._run_sentiment_agent", return_value={"action": "HOLD", "confidence": 0.50})
    @patch("data.parallel_runner._run_fundamentals_agent", return_value={"action": "BUY", "confidence": 0.70})
    @patch("data.parallel_runner._run_technical_agent", side_effect=RuntimeError("always fails"))
    def test_agent_failing_all_retries_uses_fallback(
        self, _mt, _mf, _ms, _mm, _mr, magg
    ):
        run_agents_parallel(
            _TICKER, _START, _END, news_texts=_NEWS, max_retries=2
        )
        passed = magg.call_args[0][0]
        assert passed["technical"] == _TECHNICAL_FALLBACK


# ── 9. TestFallbackConstants ──────────────────────────────────────────────────

class TestFallbackConstants:
    def test_risk_fallback_has_level_low(self):
        assert _RISK_FALLBACK["level"] == "LOW"

    def test_risk_fallback_does_not_have_risk_level_key(self):
        assert "risk_level" not in _RISK_FALLBACK

    def test_voting_agent_fallbacks_have_hold_action(self):
        for fb in (_TECHNICAL_FALLBACK, _FUNDAMENTALS_FALLBACK,
                   _SENTIMENT_FALLBACK, _MACRO_FALLBACK):
            assert fb["action"] == "HOLD"

    def test_voting_agent_fallbacks_have_zero_confidence(self):
        for fb in (_TECHNICAL_FALLBACK, _FUNDAMENTALS_FALLBACK,
                   _SENTIMENT_FALLBACK, _MACRO_FALLBACK):
            assert fb["confidence"] == 0.0

    def test_empty_result_has_all_four_required_keys(self):
        assert set(_EMPTY_RESULT.keys()) == {
            "final_action", "confidence", "reasoning", "conflicts"
        }

    def test_empty_result_default_action_is_hold(self):
        assert _EMPTY_RESULT["final_action"] == "HOLD"

    def test_empty_result_default_confidence_is_zero(self):
        assert _EMPTY_RESULT["confidence"] == 0.0

    def test_sentiment_empty_string_returns_fallback(self):
        result = _run_sentiment_agent("")
        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0

    def test_sentiment_whitespace_only_returns_fallback(self):
        result = _run_sentiment_agent("   ")
        assert result["action"] == "HOLD"
        assert result["confidence"] == 0.0
