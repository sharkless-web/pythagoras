"""Tests for the stock-data-to-sonification MVP.

Run with: ``python -m unittest stock_test -v``
"""

import io
import json
import os
import unittest
from unittest.mock import patch

import engine
from stock_service import StockDataError, fetch_recent_candles, get_close_prices


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class StockServiceTest(unittest.TestCase):
    def test_sample_fallback_returns_close_prices(self):
        with patch.dict(os.environ, {}, clear=True):
            series = fetch_recent_candles("005930", count=30)

        self.assertEqual(series.source, "sample")
        self.assertEqual(len(series.candles), 30)
        self.assertEqual(series.close_prices[0], 72000.0)
        self.assertTrue(all(isinstance(value, float) for value in series.close_prices))

    def test_missing_key_can_be_strict(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(StockDataError, "STOCK_API_KEY"):
                fetch_recent_candles("AAPL", fallback_to_sample=False)

    def test_live_response_is_sorted_oldest_first(self):
        payload = {
            "status": "ok",
            "values": [
                {"datetime": "2026-01-02 09:10:00", "open": "102", "high": "104", "low": "101", "close": "103", "volume": "30"},
                {"datetime": "2026-01-02 09:05:00", "open": "100", "high": "103", "low": "99", "close": "102", "volume": "20"},
            ],
        }

        def fake_opener(request, timeout):
            self.assertIn("symbol=AAPL", request.full_url)
            self.assertEqual(timeout, 10)
            return FakeResponse(payload)

        series = fetch_recent_candles(
            "AAPL", count=2, api_key="test-key", fallback_to_sample=False, opener=fake_opener
        )
        self.assertEqual(series.source, "twelve_data")
        self.assertEqual(series.close_prices, [102.0, 103.0])

    def test_close_prices_connect_to_existing_audio_engine(self):
        with patch.dict(os.environ, {}, clear=True):
            closes = get_close_prices("005930", count=30)

        wav_file = engine.generate_stereo_sound(closes, 800, "sine")
        self.assertIsInstance(wav_file, io.BytesIO)
        self.assertEqual(wav_file.read(4), b"RIFF")


if __name__ == "__main__":
    unittest.main(verbosity=2)
