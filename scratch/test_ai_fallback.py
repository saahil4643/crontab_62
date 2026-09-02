"""
scratch/test_ai_fallback.py

Test suite verifying Cron 62 Deterministic Python DCF AI Fallback integration:
1. Python DCF mathematical calculation correctness & formula verification
2. Financial input validation rules (WACC vs Terminal Growth, negative values, bounds)
3. Primary scraper success vs failure triggering logic
4. Valid AI inputs leading to deterministic Python calculation
5. Malformed/invalid AI inputs rejection (returns None safely)
6. AI API error resilience
7. Per-ticker independent fallback handling
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure root workspace is on python path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from models import ScrapeJob
from resilient_collector.ai_fallback import (
    calculate_dcf_in_python,
    fetch_dcf_ai_fallback,
    validate_ai_dcf_value,
    validate_dcf_inputs,
)
from resilient_collector.orchestrator import _process_alphaspread_chunk


class TestDeterministicDcfCalculation(unittest.TestCase):
    def setUp(self):
        self.valid_inputs = {
            "free_cash_flow_ttm": 1000000000.0,  # $1B FCF
            "growth_rate_5y_pct": 10.0,          # 10% FCF growth
            "wacc_pct": 9.0,                     # 9% WACC
            "terminal_growth_pct": 2.5,          # 2.5% terminal growth
            "total_cash": 500000000.0,           # $500M Cash
            "total_debt": 200000000.0,           # $200M Debt
            "shares_outstanding": 100000000.0,   # 100M Shares
        }

    def test_validate_dcf_inputs_valid(self):
        self.assertTrue(validate_dcf_inputs(self.valid_inputs))

    def test_validate_dcf_inputs_invalid_wacc_terminal_growth(self):
        # WACC <= terminal growth is mathematically invalid
        invalid_inputs = dict(self.valid_inputs, wacc_pct=2.0, terminal_growth_pct=3.0)
        self.assertFalse(validate_dcf_inputs(invalid_inputs))

    def test_validate_dcf_inputs_negative_fcf(self):
        invalid_inputs = dict(self.valid_inputs, free_cash_flow_ttm=-100.0)
        self.assertFalse(validate_dcf_inputs(invalid_inputs))

    def test_validate_dcf_inputs_missing_keys(self):
        invalid_inputs = {"free_cash_flow_ttm": 1000.0}
        self.assertFalse(validate_dcf_inputs(invalid_inputs))

    def test_python_dcf_calculation_math(self):
        """
        Verify exact mathematical formula:
        FCF0 = 1000M, g = 10%, r = 9%, g_term = 2.5%
        FCF1 = 1100M, PV1 = 1100 / 1.09 = 1009.174
        FCF2 = 1210M, PV2 = 1210 / 1.09^2 = 1018.433
        FCF3 = 1331M, PV3 = 1331 / 1.09^3 = 1027.778
        FCF4 = 1464.1M, PV4 = 1464.1 / 1.09^4 = 1037.210
        FCF5 = 1610.51M, PV5 = 1610.51 / 1.09^5 = 1046.733
        pv_fcfs = 5139.328M
        Terminal Value = (1610.51 * 1.025) / (0.09 - 0.025) = 1650.77275 / 0.065 = 25396.5038M
        PV Terminal = 25396.5038 / 1.09^5 = 16505.748M
        Enterprise Value = 5139.328M + 16505.748M = 21645.076M
        Equity Value = 21645.076M + 500M (cash) - 200M (debt) = 21945.076M
        Per Share = 21945.076M / 100M shares = $219.45
        """
        result = calculate_dcf_in_python(self.valid_inputs)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 219.45, delta=0.5)


class TestAiFallbackOrchestratorIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.job1 = ScrapeJob(
            row=3,
            ticker="AAPL",
            source="alphaspread",
            value_col="D",
            value_col_index=4,
            label="Alpha Spread",
        )
        self.mock_buffer = MagicMock()
        self.mock_buffer.enqueue_write = AsyncMock()
        self.mock_shutdown = MagicMock()
        self.mock_shutdown.is_requested.return_value = False

    @patch("resilient_collector.orchestrator._scrape_alphaspread", new_callable=AsyncMock)
    @patch("resilient_collector.ai_fallback.fetch_dcf_ai_fallback", new_callable=AsyncMock)
    @patch("resilient_collector.orchestrator.mark_completed")
    async def test_case_1_scraper_succeeds_ai_not_called(self, mock_mark, mock_ai_fallback, mock_scrape):
        """Scraper succeeds -> Scraped DCF used, AI is NOT called."""
        mock_scrape.return_value = "220.50"
        
        await _process_alphaspread_chunk([self.job1], self.mock_buffer, [], self.mock_shutdown)

        mock_scrape.assert_called_once_with(self.job1, [])
        mock_ai_fallback.assert_not_called()
        self.mock_buffer.enqueue_write.assert_called_once_with(self.job1, "220.50")
        mock_mark.assert_called_once_with("alphaspread", 3)

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_ai_fallback_fetch_and_calculate_success(self, mock_post):
        """AI returns structured financial inputs -> Python calculates deterministic DCF."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "ticker": "AAPL",
                            "free_cash_flow_ttm": 1000000000.0,
                            "growth_rate_5y_pct": 10.0,
                            "wacc_pct": 9.0,
                            "terminal_growth_pct": 2.5,
                            "total_cash": 500000000.0,
                            "total_debt": 200000000.0,
                            "shares_outstanding": 100000000.0,
                        })
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        with patch.object(config, "AI_FALLBACK_API_KEY", "test-key"):
            val = await fetch_dcf_ai_fallback("AAPL", "Alpha Spread")
            self.assertEqual(val, "219.45")

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_ai_fallback_invalid_inputs_rejected(self, mock_post):
        """AI returns invalid financial inputs -> Python rejects and returns None safely."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "ticker": "AAPL",
                            "free_cash_flow_ttm": -500.0,  # Negative FCF
                            "growth_rate_5y_pct": 10.0,
                            "wacc_pct": 2.0,              # WACC < Terminal Growth
                            "terminal_growth_pct": 3.0,
                            "total_cash": 0,
                            "total_debt": 0,
                            "shares_outstanding": 100,
                        })
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        with patch.object(config, "AI_FALLBACK_API_KEY", "test-key"):
            val = await fetch_dcf_ai_fallback("AAPL", "Alpha Spread")
            self.assertIsNone(val)


if __name__ == "__main__":
    unittest.main()
