import math
import unittest

from n0rma import micsweep as m


def csv(lo, step, dbs):
    return f"d,t,{lo},{lo + step * len(dbs)},{step},1," + ",".join(str(x) for x in dbs)


class CarrierTest(unittest.TestCase):
    def pts(self, spikes, n=200, floor=-50.0):
        d = [floor + (i % 3) * 0.5 for i in range(n)]
        for i, v in spikes.items():
            d[i] = v
        return m.parse_rows(csv(100_000_000, 25_000, d))

    def test_parse(self):
        self.assertEqual(len(m.parse_rows(csv(1e8, 25000, [-1, -2, -3]))), 3)
        self.assertEqual(m.parse_rows("junk"), [])

    def test_narrow_spike_found(self):
        c = m.carriers(self.pts({50: -30}))
        self.assertEqual(len(c), 1)
        self.assertAlmostEqual(list(c)[0], 100_000_000 + 50 * 25_000, delta=m.BINS)

    def test_wide_hump_ignored(self):
        self.assertEqual(m.carriers(self.pts({i: -30 for i in range(50, 60)})), {})

    def test_quiet_has_none(self):
        self.assertEqual(m.carriers(self.pts({})), {})

    def test_steady_needs_persistence(self):
        passes = [{1e8: -30, 2e8: -30}, {1e8: -30}, {1e8: -30}, {1e8: -30}]
        self.assertEqual(set(m.steady(passes)), {1e8})

    def test_diff_tolerates_drift(self):
        cur = {100_000_000 + m.BINS: -30, 433_920_000: -40}
        self.assertEqual([f for f, _ in m.diff(cur, [100_000_000])], [433_920_000])

    def test_band(self):
        self.assertIn("UHF", m.band_of(433.92e6))


class ToneTest(unittest.TestCase):
    rate, win = 8000, 0.5
    pat = [0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0, 0]

    def audio(self, follow):
        n = int(self.rate * self.win)
        lag = int(self.rate * 0.1)                           # playback starts a little after capture
        out = [0] * lag
        for i, on in enumerate(self.pat):
            for k in range(n):
                t = k / self.rate
                out.append(int(8000 * math.sin(2 * math.pi * m.TONE_HZ * t)) if (on and follow) else int(300 * math.sin(2 * math.pi * 333 * t + i)))
        return out

    def test_tone_returned(self):
        corr, db, p = m.tone_score(self.audio(True), self.rate, self.pat, self.win)
        self.assertGreater(corr, 0.9)
        self.assertGreater(db, 6)
        self.assertLessEqual(p, 0.01)

    def test_no_tone(self):
        corr, db, p = m.tone_score(self.audio(False), self.rate, self.pat, self.win)
        self.assertFalse(m.hit((corr, db, p)))

    def test_verdicts(self):
        hit, quiet = (0.95, 12.0, 0.002), (0.1, 0.5, 0.6)
        self.assertEqual(m.verdict(hit, []), "possible")
        self.assertEqual(m.verdict(hit, [quiet, quiet]), "confirmed")
        self.assertEqual(m.verdict(hit, [quiet, (0.9, 10.0, 0.004)]), "coupling")
        self.assertEqual(m.verdict(quiet, [quiet]), "none")

    def test_random_pattern_has_a_mix(self):
        for _ in range(50):
            p = m.random_pattern(16)
            self.assertTrue(4 <= sum(p) <= 12)

    def test_controls(self):
        self.assertTrue(abs(m.pick_control(433.92e6, [434.17e6]) - 434.17e6) >= 100e3)
        self.assertEqual(m.pick_carrier_control(433.92e6, [433.95e6, 435e6, 900e6]), 435e6)
        self.assertIsNone(m.pick_carrier_control(433.92e6, []))

    def test_baseline_roundtrip(self):
        import os, tempfile
        p = os.path.join(tempfile.mkdtemp(), "b.json")
        m.save_baseline({1e8, 2e8}, p)
        b = m.load_baseline(p)
        self.assertEqual(b["carriers"], [1e8, 2e8])
        self.assertEqual(b["gain"], m.GAIN)
        self.assertIsNone(m.load_baseline(p + "x"))


if __name__ == "__main__":
    unittest.main()
