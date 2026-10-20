import unittest

from n0rma import presence as p


def ap(bssid, ssid="", sig=-80.0, freq=2412):
    return {"bssid": bssid, "ssid": ssid, "signal": sig, "freq": freq}


class TrackerTest(unittest.TestCase):
    def test_only_hidden_or_private_logged(self):
        t = p.PresenceTracker()
        ev = t.on_scan(100.0, [ap("00:11:22:33:44:55", "Home"), ap("00:11:22:33:44:56", ""), ap("02:11:22:33:44:57", "Guest")])
        self.assertEqual([e[1] for e in ev], ["wifi:00:11:22:33:44:56", "wifi:02:11:22:33:44:57"])

    def test_gone_after_missing_scans_stamped_at_last_seen(self):
        t = p.PresenceTracker(gone_after=150)
        t.on_scan(100.0, [ap("02:aa:bb:cc:dd:ee", "x")])
        self.assertEqual(t.on_scan(200.0, []), [])
        g = t.on_scan(260.0, [])
        self.assertEqual((g[0][3], g[0][0]), (p.GONE, 100.0))

    def test_hidden_source_that_shows_a_name_keeps_it(self):
        t = p.PresenceTracker()
        t.on_scan(1.0, [ap("d6:11:22:33:44:56", "")])
        ev = t.on_scan(21.0, [ap("d6:11:22:33:44:56", "DIRECT-roku-XMX")])
        self.assertEqual((ev[0][3], ev[0][2]), (p.NAME, "DIRECT-roku-XMX"))


class SummaryTest(unittest.TestCase):
    def test_open_interval_runs_to_now_when_scanning(self):
        ev = [(0.0, "*", "", p.START), (10.0, "k", "(hidden)", p.SEEN)]
        s = p.summarize(ev, 100.0, 1000.0, True)[0]
        self.assertEqual((s["total"], s["hidden"]), (90.0, True))

    def test_start_closes_previous_dead_run_at_last_event(self):
        ev = [(0.0, "*", "", p.START), (10.0, "k", "a", p.SEEN), (50.0, "j", "b", p.SEEN), (500.0, "*", "", p.START)]
        s = {x["key"]: x for x in p.summarize(ev, 600.0, 1000.0, True)}
        self.assertEqual(s["k"]["total"], 40.0)   # ended at the last thing logged, not stretched into the next run

    def test_scanning_seconds(self):
        ev = [(0.0, "*", "", p.START), (100.0, "*", "", p.STOP), (200.0, "*", "", p.START)]
        self.assertEqual(p.scanning_seconds(ev, 300.0, 1000.0, True), 200.0)
        self.assertEqual(p.scanning_seconds(ev, 300.0, 1000.0, False), 100.0)


if __name__ == "__main__":
    unittest.main()
