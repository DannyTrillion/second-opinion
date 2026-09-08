import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FX = ROOT / "fixtures"

from secondopinion.engine.indicators import sma, rsi, percentile, median, returns  # noqa: E402
from secondopinion.engine.setups import SetupMatrix  # noqa: E402
from secondopinion.engine.baserate import forward_returns, base_rate_for, all_base_rates  # noqa: E402
from secondopinion.engine.cost import estimate_cost, _walk  # noqa: E402
from secondopinion.engine.verdict import evaluate, Policy, setups_claimed  # noqa: E402


def load(sym):
    return json.loads((FX / ("%s_1d.json" % sym)).read_text())


def end_of(date):
    import datetime
    d = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    return int((d + datetime.timedelta(days=1)).timestamp() * 1000) - 1


class TestIndicators(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 3)[2:], [2.0, 3.0, 4.0])
        self.assertIsNone(sma([1, 2, 3], 3)[1])

    def test_rsi_bounds_and_monotonic_series(self):
        up = [100 + i for i in range(40)]
        r = rsi(up, 14)
        self.assertEqual(r[-1], 100.0)
        down = [100 - i for i in range(40)]
        self.assertEqual(rsi(down, 14)[-1], 0.0)
        self.assertIsNone(r[13])

    def test_percentile_median(self):
        self.assertEqual(percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(percentile([7], 0.9), 7)

    def test_returns(self):
        self.assertIsNone(returns([1, 2])[0])
        self.assertAlmostEqual(returns([1, 2])[1], 1.0)


class TestSetups(unittest.TestCase):
    def test_no_lookahead(self):
        """Flags on bar i must not change when future bars are removed."""
        closes = [float(r[4]) for r in load("BTCUSDT")]
        full = SetupMatrix(closes)
        cut = SetupMatrix(closes[:700])
        for key in full.flags:
            self.assertEqual(full.flags[key][:700], cut.flags[key], key)

    def test_breakout_synthetic(self):
        closes = [100.0] * 30 + [101.0]
        m = SetupMatrix(closes)
        self.assertTrue(m.flags["BREAKOUT_20D"][30])
        self.assertFalse(m.flags["BREAKDOWN_20D"][30])
        closes = [100.0] * 30 + [99.0]
        self.assertTrue(SetupMatrix(closes).flags["BREAKDOWN_20D"][30])

    def test_three_up_down(self):
        closes = [100, 99, 101, 102, 103]
        m = SetupMatrix([float(c) for c in closes])
        self.assertTrue(m.flags["THREE_UP"][4])
        self.assertFalse(m.flags["THREE_DOWN"][4])

    def test_big_day_uses_own_history(self):
        closes = [float(r[4]) for r in load("SOLUSDT")]
        m = SetupMatrix(closes)
        i = len(closes) - 1
        while not m.flags["BIG_UP_DAY"][i]:
            i -= 1
        self.assertGreaterEqual(m.ret[i], m.thresholds["p90"][i])
        # percentile thresholds exist only once enough trailing history is available
        self.assertIsNone(m.thresholds["p90"][10])


class TestBaseRate(unittest.TestCase):
    def test_forward_returns(self):
        closes = [100.0, 110.0, 121.0, 133.1]
        self.assertAlmostEqual(forward_returns(closes, [0], 3)[0], 0.331)
        self.assertEqual(forward_returns(closes, [2], 3), [])

    def test_stats_and_determinism(self):
        closes = [float(r[4]) for r in load("ETHUSDT")]
        idx = list(range(0, 500))
        a = base_rate_for(closes, idx, "X", 3)
        b = base_rate_for(closes, idx, "X", 3)
        self.assertEqual(a.to_dict(), b.to_dict())
        self.assertEqual(a.n, 500)
        self.assertLessEqual(a.ci95_median_low, a.median_fwd)
        self.assertGreaterEqual(a.ci95_median_high, a.median_fwd)
        self.assertTrue(0 <= a.hit_rate <= 1)

    def test_all_base_rates_respects_upto(self):
        closes = [float(r[4]) for r in load("BNBUSDT")]
        m = SetupMatrix(closes)
        r = all_base_rates(m, 3, upto=400)
        self.assertEqual(r["ALL_DAYS"].n, 401)


class TestCost(unittest.TestCase):
    BOOK = {"bids": [["99.0", "1"], ["98.0", "10"]], "asks": [["101.0", "1"], ["102.0", "10"]]}

    def test_walk(self):
        avg, ok = _walk(self.BOOK["asks"], 101.0)
        self.assertAlmostEqual(avg, 101.0)
        self.assertTrue(ok)
        avg, ok = _walk(self.BOOK["asks"], 1e9)
        self.assertFalse(ok)

    def test_estimate(self):
        c = estimate_cost(50.0, self.BOOK, fee_rate=0.001)
        self.assertEqual(c.impact_source, "orderbook")
        self.assertAlmostEqual(c.mid, 100.0)
        self.assertAlmostEqual(c.spread_bps, 200.0)
        self.assertAlmostEqual(c.buy_impact_bps, 100.0)
        self.assertAlmostEqual(c.round_trip_bps, 20.0 + 200.0)
        self.assertTrue(c.fill_covered)
        big = estimate_cost(1e9, self.BOOK)
        self.assertFalse(big.fill_covered)

    def test_assumed_without_book(self):
        c = estimate_cost(100.0, None)
        self.assertEqual(c.impact_source, "assumed")
        self.assertAlmostEqual(c.round_trip_bps, 30.0)


class TestVerdict(unittest.TestCase):
    def test_sol_momentum_buy_is_vetoed_on_evidence(self):
        v = evaluate("SOLUSDT", "BUY", 100, load("SOLUSDT"), None, Policy(max_data_age_hours=1e9),
                     now_ms=end_of("2026-08-27"), thesis="strong momentum after the breakout")
        self.assertEqual(v.verdict, "VETO")
        self.assertEqual(v.primary_setup, "BIG_UP_DAY")
        self.assertIn("BIG_UP_DAY", v.active_setups)
        self.assertLess(v.edge_after_cost_bps, 0)
        self.assertGreaterEqual(v.primary["n"], 30)
        names = {c["name"]: c for c in v.checks}
        self.assertFalse(names["edge_after_cost"]["passed"])
        self.assertEqual(names["edge_after_cost"]["unit"], "bps")

    def test_hallucinated_thesis_is_a_hard_veto(self):
        v = evaluate("BTCUSDT", "BUY", 100, load("BTCUSDT"), None, Policy(max_data_age_hours=1e9),
                     now_ms=end_of("2026-08-12"), thesis="momentum breakout")
        self.assertEqual(v.verdict, "VETO")
        tp = [c for c in v.checks if c["name"] == "thesis_present"][0]
        self.assertFalse(tp["passed"])

    def test_dip_buy_after_three_red_days(self):
        v = evaluate("BTCUSDT", "BUY", 100, load("BTCUSDT"), None, Policy(max_data_age_hours=1e9),
                     now_ms=end_of("2026-08-12"), thesis="buy the dip")
        self.assertEqual(v.primary_setup, "THREE_DOWN")
        self.assertIn(v.verdict, ("APPROVE", "CAUTION"))
        self.assertGreater(v.edge_after_cost_bps, 0)

    def test_policy_cap_is_hard_veto(self):
        v = evaluate("BNBUSDT", "BUY", 5000, load("BNBUSDT"), None, Policy(max_data_age_hours=1e9, max_notional_usd=1000),
                     now_ms=end_of("2026-08-12"))
        self.assertEqual(v.verdict, "VETO")
        self.assertIn("max_notional", [c["name"] for c in v.checks if not c["passed"]])

    def test_plain_day_is_caution_not_veto(self):
        v = evaluate("BTCUSDT", "BUY", 100, load("BTCUSDT"), None, Policy(max_data_age_hours=1e9), now_ms=end_of("2026-09-07"))
        self.assertIn(v.primary_setup, ("ALL_DAYS", "ABOVE_SMA50", "BELOW_SMA50"))
        self.assertNotEqual(v.verdict, "VETO")

    def test_stale_data_is_hard_veto(self):
        v = evaluate("BTCUSDT", "BUY", 100, load("BTCUSDT"), None, Policy(max_data_age_hours=30),
                     now_ms=end_of("2026-09-07") + 5 * 86400000)
        self.assertEqual(v.verdict, "VETO")

    def test_byte_identical_decisions(self):
        kl = load("SOLUSDT")
        book = json.loads((FX / "BTCUSDT_depth.json").read_text())
        a = evaluate("SOLUSDT", "BUY", 100, kl, book, Policy(max_data_age_hours=1e9), now_ms=end_of("2026-08-27"), thesis="momentum")
        b = evaluate("SOLUSDT", "BUY", 100, kl, book, Policy(max_data_age_hours=1e9), now_ms=end_of("2026-08-27"), thesis="momentum")
        self.assertEqual(a.body_sha256, b.body_sha256)
        self.assertEqual(json.dumps(a.to_dict(), sort_keys=True), json.dumps(b.to_dict(), sort_keys=True))

    def test_golden_hash_for_frozen_fixture(self):
        """Pinned: the SOL 2026-08-27 momentum replay on the committed fixture. Changes here mean the maths changed."""
        v = evaluate("SOLUSDT", "BUY", 100, load("SOLUSDT"), None, Policy(max_data_age_hours=1e9),
                     now_ms=end_of("2026-08-27"), thesis="momentum")
        self.assertEqual(v.body_sha256, GOLDEN_SOL)

    def test_thesis_words(self):
        self.assertIn("BIG_UP_DAY", setups_claimed("strong momentum today"))
        self.assertIn("THREE_DOWN", setups_claimed("buying the dip"))
        self.assertEqual(setups_claimed("I like the logo"), [])


GOLDEN_SOL = "a573151108396a57c9a614968a1c408778f3025767536fd49aaaa325e7f90fc0"

if __name__ == "__main__":
    unittest.main()


class TestNewModules(unittest.TestCase):
    def test_multi_horizon_in_receipt(self):
        v = evaluate("SOLUSDT", "BUY", 100, load("SOLUSDT"), None, Policy(max_data_age_hours=1e9),
                     now_ms=end_of("2026-08-27"), thesis="momentum")
        self.assertEqual(sorted(v.primary_by_horizon.keys(), key=int), ["1", "3", "7"])
        self.assertEqual(v.primary_by_horizon["3"]["n"], v.primary["n"])
        self.assertIn("same setup by horizon", v.summary())

    def test_walkforward_is_out_of_sample_and_summarises(self):
        from secondopinion.engine.walkforward import walk_forward, summarize, render_markdown
        kl = load("BNBUSDT")[:420]
        res = walk_forward("BNBUSDT", kl, horizon=3, start=400, every=1)
        self.assertEqual(res["days"], 420 - 3 - 400)
        for r in res["rows"]:
            self.assertIn(r["verdict"], ("APPROVE", "CAUTION", "VETO"))
            c0, c1 = float(kl[r["t"]][4]), float(kl[r["t"] + 3][4])
            self.assertAlmostEqual(r["gross"], c1 / c0 - 1.0)
        s = summarize([res])
        self.assertEqual(s["days_total"], res["days"])
        md = render_markdown(s)
        self.assertIn("walk-forward", md)

    def test_evidence_tables(self):
        from secondopinion.engine.evidence import build, render_markdown
        ev = build(FX, 3)
        self.assertGreaterEqual(len(ev["symbols"]), 4)
        self.assertIn("BTCUSDT", ev["table"])
        for p in ev["pairs"]:
            self.assertGreaterEqual(p["n"], ev["min_n"])
            self.assertFalse(p["pays"] and p["loses"])
        self.assertIn("| setup |", render_markdown(ev))
