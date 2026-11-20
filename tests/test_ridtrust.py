import unittest
from unittest import mock

from n0rma import det_ble, ridtrust

from tests.test_parsers import basic_msg, loc_msg

ADDR = "c4:5e:12:34:56:78"


def loc(lat, lon):
    m = bytearray(loc_msg(lat, lon))
    m[19] = 0x4B  # vertical accuracy < 10 m, horizontal < 3 m
    return bytes(m)


def sd(counter, msg):
    return bytes([0x0D, counter & 0xFF]) + msg


class Describe(unittest.TestCase):
    def test_without_a_verdict_it_still_says_unverified(self):
        self.assertEqual(ridtrust.describe({}, "Bluetooth"), "(Bluetooth; unverified)")

    def test_a_verdict_and_its_reasons(self):
        e = {"trust": "spoofed", "trust_reasons": ["teleport", "known_spoofer"]}
        self.assertEqual(ridtrust.describe(e, "Wi-Fi"), "(Wi-Fi; remoteid: SPOOFED - teleport, known_spoofer)")
        self.assertEqual(ridtrust.describe({"trust": "plausible", "trust_reasons": []}, "Bluetooth"),
                         "(Bluetooth; remoteid: plausible)")

    def test_garbage_never_raises(self):
        self.assertEqual(ridtrust.judge(b"", "ble_service_data", ADDR), {})
        self.assertEqual(ridtrust.judge(b"\x0d", "ble_service_data", ADDR), {})
        self.assertEqual(ridtrust.judge_wifi_ie("0d zz", "aa:bb:cc:dd:ee:ff"), {})


@unittest.skipUnless(ridtrust.AVAILABLE, "pip install 'n0rma-sec[trust]'")
class Verdicts(unittest.TestCase):
    def setUp(self):
        ridtrust._tracker = None

    def test_a_steady_drone_is_plausible(self):
        for i in range(20):
            r = ridtrust.judge(sd(i, loc(33.5 + i * 0.00003, -85.3)), "ble_service_data", ADDR, -60, 1000.0 + i)
        self.assertEqual(r["trust"], "plausible")

    def test_a_drone_that_jumps_10_km_and_stays_is_spoofed(self):
        # Three places 5.5 km apart, ten seconds each: no aircraft does that, a spoofing script does.
        for s in range(40):
            r = ridtrust.judge(sd(s, loc(33.5 + 0.05 * (s // 10), -85.3)), "ble_service_data", ADDR, -60, 1000.0 + s)
        self.assertEqual(r["trust"], "spoofed")
        self.assertIn("teleport", r["trust_reasons"])

    def test_wifi_beacon_ie_from_iw(self):
        ie = " ".join(f"{b:02x}" for b in bytes([0x0D, 1, 0xF2, 25, 2]) + basic_msg("1581F4XYZ123") + loc(33.5, -85.3))
        r = ridtrust.judge_wifi_ie(ie, "60:60:1f:00:00:01", -50, 1000.0)
        self.assertIn(r["trust"], ("plausible", "suspicious"))

    def test_the_ble_alert_carries_the_verdict(self):
        class Adv:
            manufacturer_data, service_uuids, local_name = {}, [], ""

        class Dev:
            address, name = ADDR, ""

        d = det_ble.BLEDetector.__new__(det_ble.BLEDetector)
        d.seen, d.seen_total, d.ambient = {}, 0, 0
        for s in range(40):
            a = Adv()
            a.rssi = -60
            a.service_data = {"0000fffa-0000-1000-8000-00805f9b34fb": sd(s, loc(33.5 + 0.05 * (s // 10), -85.3))}
            with mock.patch.object(det_ble.time, "time", return_value=1000.0 + s):
                d._cb(Dev(), a)
        self.assertEqual(d.seen[ADDR]["extra"]["trust"], "spoofed")


if __name__ == "__main__":
    unittest.main()
