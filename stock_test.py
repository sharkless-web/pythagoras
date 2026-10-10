"""Tests for the Toss Securities stock-data-to-sonification flow."""

import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

import engine
import server
from stock_service import Candle, StockDataError, aggregate_minute_candles, fetch_recent_candles, fetch_stock_rankings, get_close_prices


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, test_case, responses):
        self.test_case = test_case
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.test_case.assertEqual(timeout, 10)
        self.requests.append(request)
        return FakeResponse(next(self.responses))


class StockServiceTest(unittest.TestCase):
    def test_sample_fallback_returns_close_prices(self):
        with patch.dict(os.environ, {}, clear=True):
            series = fetch_recent_candles("005930", count=30)
        self.assertEqual(series.source, "sample")
        self.assertEqual(len(series.candles), 30)
        self.assertEqual(series.close_prices[0], 72000.0)

    def test_missing_credentials_can_be_strict(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(StockDataError, "TOSSINVEST_CLIENT_ID"):
                fetch_recent_candles("AAPL", fallback_to_sample=False)

    def test_oauth_and_candles_are_converted_to_chronological_closes(self):
        opener = FakeOpener(
            self,
            [
                {"access_token": "test-token", "token_type": "Bearer", "expires_in": 86400},
                {"result": {"candles": [
                    {"timestamp": "2026-03-25T09:32:00+09:00", "openPrice": "102", "highPrice": "104", "lowPrice": "101", "closePrice": "103", "volume": "30"},
                    {"timestamp": "2026-03-25T09:31:00+09:00", "openPrice": "100", "highPrice": "103", "lowPrice": "99", "closePrice": "102", "volume": "20"},
                ]}},
            ],
        )
        series = fetch_recent_candles(
            "005930", count=2, client_id="id", client_secret="secret",
            fallback_to_sample=False, opener=opener,
        )
        self.assertEqual(series.source, "tossinvest")
        self.assertEqual(series.close_prices, [102.0, 103.0])
        self.assertTrue(opener.requests[0].full_url.endswith("/oauth2/token"))
        self.assertEqual(opener.requests[1].get_header("Authorization"), "Bearer test-token")

    def test_derived_intervals_combine_actual_minute_ohlcv(self):
        candles = [Candle(f"2026-10-08T09:{minute:02d}:00+09:00", 100 + minute,
                          104 + minute, 98 + minute, 101 + minute, minute + 1)
                   for minute in range(16)]
        for interval, expected_lengths in [(5, [5, 5, 5, 1]), (15, [15, 1]), (60, [16])]:
            result = aggregate_minute_candles(list(reversed(candles)), interval)
            self.assertEqual(len(result), len(expected_lengths))
            self.assertEqual(result[0].open, 100)
            self.assertEqual(result[0].close, 100 + expected_lengths[0])
            self.assertEqual(result[0].high, 104 + expected_lengths[0] - 1)
            self.assertEqual(result[0].low, 98)
            self.assertEqual(result[0].volume, sum(range(1, expected_lengths[0] + 1)))

    def test_five_minute_live_fetch_paginates_only_one_minute_api(self):
        def candle(minute):
            return {"timestamp": f"2026-10-08T09:{minute:02d}:00+09:00", "openPrice": "100",
                    "highPrice": "110", "lowPrice": "90", "closePrice": str(100 + minute), "volume": "10"}
        opener = FakeOpener(self, [
            {"access_token": "test-token"},
            {"result": {"candles": [candle(n) for n in range(14, 4, -1)], "nextBefore": "2026-10-08T09:04:00+09:00"}},
            {"result": {"candles": [candle(n) for n in range(4, -1, -1)], "nextBefore": None}},
        ])
        series = fetch_recent_candles("005930", "5m", 2, client_id="id", client_secret="secret",
                                      fallback_to_sample=False, opener=opener)
        self.assertEqual(series.source, "tossinvest")
        self.assertEqual(series.close_prices, [109, 114])
        self.assertEqual([c.volume for c in series.candles], [50, 50])
        self.assertIn("interval=1m", opener.requests[1].full_url)
        self.assertIn("before=2026-10-08T09%3A04%3A00%2B09%3A00", opener.requests[2].full_url)

    def test_close_prices_connect_to_existing_audio_engine(self):
        with patch.dict(os.environ, {}, clear=True):
            closes = get_close_prices("005930", count=30)
        wav_file = engine.generate_stereo_sound(closes, 800, "sine")
        self.assertIsInstance(wav_file, io.BytesIO)
        self.assertEqual(wav_file.read(4), b"RIFF")

    def test_rankings_are_enriched_with_stock_names(self):
        opener = FakeOpener(
            self,
            [
                {"access_token": "test-token"},
                {"result": {"rankedAt": "2026-10-02T14:30:00+09:00", "rankings": [{
                    "rank": 1,
                    "symbol": "005930",
                    "currency": "KRW",
                    "price": {"lastPrice": "72000", "basePrice": "70000", "changeRate": "0.0285"},
                    "tradingVolume": "18432100",
                    "tradingAmount": "1041436650000",
                }]}},
                {"result": [{"symbol": "005930", "name": "삼성전자", "currency": "KRW"}]},
            ],
        )
        payload = fetch_stock_rankings(
            "MARKET_TRADING_AMOUNT", "KR", "realtime", 10,
            client_id="id", client_secret="secret", opener=opener,
        )
        self.assertEqual(payload["rankings"][0]["name"], "삼성전자")
        self.assertAlmostEqual(payload["rankings"][0]["change_percent"], 2.85)
        self.assertIn("marketCountry=KR", opener.requests[1].full_url)
        self.assertIn("symbols=005930", opener.requests[2].full_url)

    def test_realtime_is_rejected_for_gainer_rankings(self):
        with self.assertRaisesRegex(ValueError, "do not support realtime"):
            fetch_stock_rankings(
                "TOP_GAINERS", "KR", "realtime", 10,
                client_id="id", client_secret="secret",
            )

    def test_demo_endpoint_is_explicit_and_includes_accessible_metrics(self):
        payload = server.stock_candles("005930", "1m", 30, demo=True)
        self.assertEqual(payload["source"], "sample")
        self.assertEqual(payload["name"], "삼성전자")
        self.assertEqual(len(payload["volumes"]), 30)
        self.assertEqual(payload["volumes"][0], 100000.0)
        self.assertIn("latest", payload["metrics"])
        self.assertIn("change_percent", payload["metrics"])

    def test_live_endpoint_does_not_hide_failure_with_sample_data(self):
        with patch("server.fetch_recent_candles", side_effect=StockDataError("live unavailable")):
            response = server.stock_candles("005930", "1m", 30, demo=False)
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"live unavailable", response.body)

    def test_windows_socket_denial_has_actionable_message(self):
        denied = OSError(10013, "socket access forbidden")
        with patch("stock_service._issue_access_token", side_effect=URLError(denied)):
            with self.assertRaisesRegex(StockDataError, "Windows.*외부 연결"):
                fetch_recent_candles(
                    "005930", client_id="id", client_secret="secret", fallback_to_sample=False
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
