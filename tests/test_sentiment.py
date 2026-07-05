import unittest
from unittest.mock import patch

from data.sentiment import analyze_sentiment


# ---------------------------------------------------------------------------
# VADER is deterministic — no mocking needed for the happy-path tests.
# Use texts with unambiguous polarity so the compound score is stable.
# ---------------------------------------------------------------------------

_STRONG_POS = (
    "Outstanding earnings beat all analyst expectations. "
    "Record profits with exceptional revenue growth and upgraded guidance."
)
_STRONG_NEG = (
    "Terrible losses mount as company faces bankruptcy. "
    "Devastating earnings miss amid fraud scandal. Stock crashed."
)
_NEUTRAL = "The company announced its annual general meeting will take place on Tuesday."


class TestOutputSchema(unittest.TestCase):

    def test_result_is_dict(self):
        result = analyze_sentiment(_STRONG_POS)
        self.assertIsInstance(result, dict)

    def test_result_has_exactly_three_keys(self):
        result = analyze_sentiment(_STRONG_POS)
        self.assertEqual(len(result), 3)
        self.assertEqual(set(result.keys()), {"sentiment", "score", "reason"})

    def test_sentiment_is_string(self):
        result = analyze_sentiment(_STRONG_POS)
        self.assertIsInstance(result["sentiment"], str)

    def test_score_is_int(self):
        result = analyze_sentiment(_STRONG_POS)
        self.assertIs(type(result["score"]), int)

    def test_reason_is_non_empty_string(self):
        result = analyze_sentiment(_STRONG_POS)
        self.assertIsInstance(result["reason"], str)
        self.assertGreater(len(result["reason"]), 0)

    def test_sentiment_value_is_one_of_three_allowed(self):
        for text in (_STRONG_POS, _STRONG_NEG, _NEUTRAL):
            with self.subTest(text=text[:40]):
                self.assertIn(analyze_sentiment(text)["sentiment"],
                              {"Positive", "Neutral", "Negative"})

    def test_score_is_always_in_valid_range(self):
        for text in (_STRONG_POS, _STRONG_NEG, _NEUTRAL):
            with self.subTest(text=text[:40]):
                self.assertIn(analyze_sentiment(text)["score"], {-1, 0, 1})


class TestPositiveSentiment(unittest.TestCase):

    def test_strong_positive_news_returns_positive(self):
        result = analyze_sentiment(_STRONG_POS)
        self.assertEqual(result["sentiment"], "Positive")
        self.assertEqual(result["score"], 1)

    def test_positive_score_is_plus_one(self):
        result = analyze_sentiment(_STRONG_POS)
        self.assertEqual(result["score"], 1)

    def test_positive_reason_contains_score(self):
        result = analyze_sentiment(_STRONG_POS)
        self.assertIn("VADER score", result["reason"])

    def test_earnings_beat_positive(self):
        result = analyze_sentiment(
            "Excellent quarterly results. Best performance ever. Strong profits beat estimates."
        )
        self.assertEqual(result["score"], 1)


class TestNegativeSentiment(unittest.TestCase):

    def test_strong_negative_news_returns_negative(self):
        result = analyze_sentiment(_STRONG_NEG)
        self.assertEqual(result["sentiment"], "Negative")
        self.assertEqual(result["score"], -1)

    def test_negative_score_is_minus_one(self):
        result = analyze_sentiment(_STRONG_NEG)
        self.assertEqual(result["score"], -1)

    def test_negative_reason_contains_score(self):
        result = analyze_sentiment(_STRONG_NEG)
        self.assertIn("VADER score", result["reason"])

    def test_loss_scandal_negative(self):
        result = analyze_sentiment(
            "Horrible losses. Worst quarterly report. Shares plunged on terrible news."
        )
        self.assertEqual(result["score"], -1)


class TestNeutralSentiment(unittest.TestCase):

    def test_neutral_news_returns_neutral(self):
        result = analyze_sentiment(_NEUTRAL)
        self.assertEqual(result["sentiment"], "Neutral")
        self.assertEqual(result["score"], 0)

    def test_neutral_score_is_zero(self):
        result = analyze_sentiment(_NEUTRAL)
        self.assertEqual(result["score"], 0)


class TestEmptyAndNoneInputs(unittest.TestCase):

    def test_empty_string_returns_fallback(self):
        result = analyze_sentiment("")
        self.assertEqual(result["sentiment"], "Neutral")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["reason"], "No news text provided.")

    def test_whitespace_only_returns_fallback(self):
        result = analyze_sentiment("   \n\t  ")
        self.assertEqual(result["sentiment"], "Neutral")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["reason"], "No news text provided.")

    def test_none_returns_fallback(self):
        result = analyze_sentiment(None)
        self.assertEqual(result["sentiment"], "Neutral")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["reason"], "No news text provided.")

    def test_empty_string_does_not_raise(self):
        try:
            analyze_sentiment("")
        except Exception as e:
            self.fail(f"analyze_sentiment raised unexpectedly: {e}")

    def test_none_does_not_raise(self):
        try:
            analyze_sentiment(None)
        except Exception as e:
            self.fail(f"analyze_sentiment raised unexpectedly: {e}")


class TestVaderUnavailable(unittest.TestCase):

    def test_returns_neutral_when_vader_module_missing(self):
        with patch("data.sentiment._VADER_OK", False):
            result = analyze_sentiment("Company posted strong earnings growth.")
        self.assertEqual(result["sentiment"], "Neutral")
        self.assertEqual(result["score"], 0)

    def test_does_not_raise_when_vader_module_missing(self):
        with patch("data.sentiment._VADER_OK", False):
            try:
                analyze_sentiment("Some news text.")
            except Exception as e:
                self.fail(f"analyze_sentiment raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
