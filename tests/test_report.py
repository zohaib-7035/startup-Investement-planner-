import unittest

from data.report import render_report

_FULL_DATA = {
    "company_name": "Apple Inc.",
    "recommendation": "BUY",
    "confidence_score": 0.85,
    "technical_signals": {"action": "Buy", "confidence": 0.85, "reason": "RSI oversold"},
    "fundamentals": {"pe_ratio": 28.5, "eps": 6.11, "market_cap": 2800000000000.0},
    "sentiment": "Positive",
    "risk_level": "Medium",
    "portfolio_allocation": {"AAPL": 0.5, "MSFT": 0.3},
    "timestamp": "2026-07-04T10:00:00",
}


class TestOutputSchema(unittest.TestCase):

    def test_result_is_a_string(self):
        result = render_report(_FULL_DATA)
        self.assertIsInstance(result, str)

    def test_result_is_non_empty(self):
        result = render_report(_FULL_DATA)
        self.assertGreater(len(result), 500)

    def test_non_dict_input_type_returns_fallback_html(self):
        result = render_report(["AAPL", "BUY"])
        self.assertIsInstance(result, str)
        self.assertIn("No data available", result)

    def test_html_injection_in_string_field_is_escaped(self):
        data = {**_FULL_DATA, "company_name": "<script>alert(1)</script>"}
        result = render_report(data)
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_result_contains_html_root_tag(self):
        result = render_report(_FULL_DATA)
        self.assertIn("<html", result)

    def test_result_contains_head_tag(self):
        result = render_report(_FULL_DATA)
        self.assertIn("<head>", result)

    def test_result_contains_body_tag(self):
        result = render_report(_FULL_DATA)
        self.assertIn("<body>", result)

    def test_result_contains_style_block(self):
        result = render_report(_FULL_DATA)
        self.assertIn("<style>", result)


class TestHappyPath(unittest.TestCase):

    def setUp(self):
        self.result = render_report(_FULL_DATA)

    def test_company_name_appears_in_output(self):
        self.assertIn("Apple Inc.", self.result)

    def test_recommendation_appears_in_output(self):
        self.assertIn("BUY", self.result)

    def test_confidence_score_appears_as_percentage(self):
        self.assertIn("85%", self.result)

    def test_technical_signals_key_appears_in_output(self):
        self.assertIn("action", self.result)
        self.assertIn("RSI oversold", self.result)

    def test_fundamentals_key_appears_in_output(self):
        self.assertIn("pe_ratio", self.result)
        self.assertIn("28.50", self.result)

    def test_sentiment_appears_in_output(self):
        self.assertIn("Positive", self.result)

    def test_risk_level_appears_in_output(self):
        self.assertIn("Medium", self.result)

    def test_portfolio_allocation_ticker_appears_in_output(self):
        self.assertIn("AAPL", self.result)
        self.assertIn("MSFT", self.result)

    def test_timestamp_appears_in_output(self):
        self.assertIn("2026-07-04T10:00:00", self.result)

    def test_all_none_field_values_renders_html_not_literal_none(self):
        data = {k: None for k in _FULL_DATA}
        result = render_report(data)
        self.assertIsInstance(result, str)
        self.assertIn("<html", result)
        self.assertNotIn("None", result)


class TestConfidenceFormatting(unittest.TestCase):

    def _render(self, score):
        # portfolio_allocation set to None to avoid false "0%" matches from allocation percentages
        data = {**_FULL_DATA, "confidence_score": score, "portfolio_allocation": None}
        return render_report(data)

    def test_0_85_renders_as_85_percent(self):
        self.assertIn("85%", self._render(0.85))

    def test_1_0_renders_as_100_percent(self):
        self.assertIn("100%", self._render(1.0))

    def test_0_0_renders_as_0_percent(self):
        self.assertIn("0%", self._render(0.0))

    def test_none_renders_as_na(self):
        self.assertIn("N/A", self._render(None))

    def test_above_1_clamped_to_100_percent(self):
        self.assertIn("100%", self._render(1.5))

    def test_below_0_clamped_to_0_percent(self):
        self.assertIn("0%", self._render(-0.5))


class TestRecommendationBadge(unittest.TestCase):

    def _render(self, rec):
        data = {**_FULL_DATA, "recommendation": rec}
        return render_report(data)

    def test_buy_produces_green_badge(self):
        self.assertIn("#28a745", self._render("BUY"))

    def test_sell_produces_red_badge(self):
        self.assertIn("#dc3545", self._render("SELL"))

    def test_hold_produces_amber_badge(self):
        self.assertIn("#fd7e14", self._render("HOLD"))

    def test_lowercase_buy_produces_green_badge(self):
        self.assertIn("#28a745", self._render("buy"))

    def test_titlecase_hold_produces_amber_badge(self):
        self.assertIn("#fd7e14", self._render("Hold"))

    def test_unknown_recommendation_produces_grey_badge(self):
        self.assertIn("#6c757d", self._render("STRONG_BUY"))


class TestNoneFieldFallback(unittest.TestCase):

    def _render_with_none(self, key):
        data = {**_FULL_DATA, key: None}
        return render_report(data)

    def test_company_name_none_renders_na(self):
        self.assertIn("N/A", self._render_with_none("company_name"))

    def test_recommendation_none_renders_na(self):
        self.assertIn("N/A", self._render_with_none("recommendation"))

    def test_confidence_score_none_renders_na(self):
        result = render_report({**_FULL_DATA, "confidence_score": None, "portfolio_allocation": None})
        self.assertIn("N/A", result)

    def test_technical_signals_none_renders_na(self):
        self.assertIn("N/A", self._render_with_none("technical_signals"))

    def test_fundamentals_none_renders_na(self):
        self.assertIn("N/A", self._render_with_none("fundamentals"))

    def test_sentiment_none_renders_na(self):
        self.assertIn("N/A", self._render_with_none("sentiment"))

    def test_risk_level_none_renders_na(self):
        self.assertIn("N/A", self._render_with_none("risk_level"))

    def test_portfolio_allocation_none_renders_na(self):
        self.assertIn("N/A", self._render_with_none("portfolio_allocation"))

    def test_timestamp_none_renders_na(self):
        self.assertIn("N/A", self._render_with_none("timestamp"))


class TestPortfolioAllocation(unittest.TestCase):

    def test_tickers_appear_in_output(self):
        result = render_report(_FULL_DATA)
        self.assertIn("AAPL", result)
        self.assertIn("MSFT", result)

    def test_weights_rendered_as_percentages(self):
        result = render_report(_FULL_DATA)
        self.assertIn("50.0%", result)
        self.assertIn("30.0%", result)

    def test_none_allocation_renders_na(self):
        result = render_report({**_FULL_DATA, "portfolio_allocation": None})
        self.assertIn("N/A", result)

    def test_empty_dict_allocation_renders_na(self):
        result = render_report({**_FULL_DATA, "portfolio_allocation": {}})
        self.assertIn("N/A", result)


class TestPreflightGuard(unittest.TestCase):

    def test_none_input_returns_string(self):
        result = render_report(None)
        self.assertIsInstance(result, str)

    def test_none_input_contains_no_data_available(self):
        result = render_report(None)
        self.assertIn("No data available", result)

    def test_empty_dict_input_returns_string(self):
        result = render_report({})
        self.assertIsInstance(result, str)

    def test_empty_dict_input_contains_no_data_available(self):
        result = render_report({})
        self.assertIn("No data available", result)

    def test_none_input_does_not_raise(self):
        try:
            render_report(None)
        except Exception as exc:
            self.fail(f"render_report(None) raised unexpectedly: {exc}")

    def test_empty_dict_does_not_raise(self):
        try:
            render_report({})
        except Exception as exc:
            self.fail(f"render_report({{}}) raised unexpectedly: {exc}")
