import unittest

from n0rma import det_ble, spam


def flood(d, t0, n, step, fam="Apple pairing pop-up", rssi=-55):
    for i in range(n):
        d.on_ad(f"r-{t0}-{i}", fam, rssi, t0 + i * step)


class SpamDetectorTest(unittest.TestCase):
    def test_many_different_addresses_is_a_watch(self):
        d = spam.SpamDetector(); flood(d, 1000.0, 20, 0.5)
        s = d.evaluate(1010.0)
        self.assertEqual(s.level, "watch"); self.assertEqual(s.distinct, 20); self.assertIn("Apple pairing pop-up", s.message)

    def test_same_addresses_repeating_is_not(self):
        d = spam.SpamDetector()
        for i in range(200):
            d.on_ad("AA:BB", "Apple pairing pop-up", -50, 1000.0 + i * 0.1)
        for i in range(5):
            for j in range(40):
                d.on_ad(f"dev{i}", "Apple pairing pop-up", -60, 1000.0 + j * 0.1)
        self.assertEqual(d.evaluate(1015.0).level, "ok")

    def test_a_crowd_of_repeaters_is_not(self):   # 15 distinct addresses, each advertising 10 times: ratio too low
        d = spam.SpamDetector()
        for i in range(15):
            for j in range(10):
                d.on_ad(f"dev{i}", "Google Fast Pair pop-up", -70, 1000.0 + j + i * 0.001)
        self.assertEqual(d.evaluate(1012.0).level, "ok")

    def test_sustained_large_flood_is_an_alert(self):
        d = spam.SpamDetector(); last = "ok"
        for sec in range(91):
            now = 5000.0 + sec
            for k in range(2):
                d.on_ad(f"r{sec}-{k}", "Windows Swift Pair pop-up", -48, now)
            last = d.evaluate(now).level
        self.assertEqual(last, "alert")

    def test_brief_burst_stays_a_watch(self):
        d = spam.SpamDetector(); flood(d, 2000.0, 40, 0.2)
        self.assertEqual(d.evaluate(2009.0).level, "watch")

    def test_flood_ends_when_ads_stop(self):
        d = spam.SpamDetector(); flood(d, 3000.0, 20, 0.5)
        self.assertEqual(d.evaluate(3010.0).level, "watch")
        self.assertEqual(d.evaluate(3070.0).level, "ok")


class FamilyTest(unittest.TestCase):
    def test_families(self):
        self.assertEqual(spam.family({0x004C: bytes([0x07, 0x19])}, {}), "Apple pairing pop-up")
        self.assertEqual(spam.family({0x004C: bytes([0x0F, 0x05])}, {}), "Apple setup pop-up")
        self.assertIsNone(spam.family({0x004C: bytes([0x10, 0x05])}, {}))   # ordinary Apple chatter
        self.assertEqual(spam.family({}, {"0000fe2c-0000-1000-8000-00805f9b34fb": b"\x01\x02\x03"}), "Google Fast Pair pop-up")
        self.assertEqual(spam.family({0x0006: bytes([0x03, 0x00, 0x80])}, {}), "Windows Swift Pair pop-up")
        self.assertIsNone(spam.family({0x0006: bytes([0x01, 0x09])}, {}))

    def test_classify_adv_tags_spam_but_trackers_win(self):
        self.assertEqual(det_ble.classify_adv({0x004C: bytes([0x07, 0x19])}, {}, [])[0], "spam")
        self.assertEqual(det_ble.classify_adv({0x004C: bytes([0x12, 0x19])}, {}, [])[0], "tracker")


if __name__ == "__main__":
    unittest.main()


class CamKnownTest(unittest.TestCase):
    def test_marked_camera_source_is_not_flagged_and_other_names_still_are(self):
        from n0rma import det_wifi
        from n0rma.core import DB, Engine
        eng = Engine(DB(":memory:"), quiet=True)
        w = det_wifi.WifiDetector(eng); w.first_pass = False
        bss = lambda m, n, sig: {"bssid": m, "ssid": n, "signal": sig, "freq": 2437, "rid_ies": [], "seen_ms": None}
        w.evaluate([bss("e0:b2:60:41:b1:79", "Cam-test", -70)])
        self.assertEqual(eng.state["network"]["level"], "watch")
        self.assertEqual(eng.live["cam"]["key"], "wifi:e0:b2:60:41:b1|Cam-test")
        eng.db.kv_set("wifi_mine", ["wifi:e0:b2:60:41:b1|Cam-test"])
        w.evaluate([bss("e0:b2:60:41:b1:89", "Cam-test", -70)])      # sister address of the same radio: also known
        self.assertEqual(eng.state["network"]["level"], "ok")
        w.evaluate([bss("e0:b2:60:41:b1:99", "SpyCam_1", -40)])      # a differently named network is NOT silenced
        self.assertEqual(eng.state["network"]["level"], "alert")

    def test_signal_history_for_the_find_view(self):
        from n0rma import det_wifi
        from n0rma.core import DB, Engine
        eng = Engine(DB(":memory:"), quiet=True)
        w = det_wifi.WifiDetector(eng); w.first_pass = False
        for sig in (-80, -70, -60):
            w.evaluate([{"bssid": "aa:bb:cc:dd:ee:01", "ssid": "Home", "signal": sig, "freq": 2437, "rid_ies": [], "seen_ms": None}])
        self.assertEqual(eng.live["wifi_hist"]["aa:bb:cc:dd:ee:01"], [-80, -70, -60])
