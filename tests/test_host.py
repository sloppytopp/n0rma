import unittest

from n0rma import det_host


class PortClassTest(unittest.TestCase):
    def test_tailscale_ports_are_info_only_when_owned_by_tailscaled(self):
        self.assertEqual(det_host.port_class("tcp 100.118.105.60%tailscale0:57753 tailscaled"), "info")
        self.assertEqual(det_host.port_class("tcp [fd7a:115c:a1e0::7601:69dd]%tailscale0:52642 tailscaled"), "info")

    def test_unknown_or_other_owner_on_tailscale_still_alerts(self):   # a backdoor on the tailnet address must not be silenced
        self.assertEqual(det_host.port_class("tcp 100.118.105.60%tailscale0:57753 ?"), "alert")
        self.assertEqual(det_host.port_class("tcp 100.118.105.60%tailscale0:4444 nc"), "alert")
        self.assertEqual(det_host.port_class("tcp 10.0.0.5%tailscale-evil:57753 tailscaled"), "alert")

    def test_real_lan_ports_still_alert(self):
        self.assertEqual(det_host.port_class("tcp 192.168.1.20:8080 python3"), "alert")
        self.assertEqual(det_host.port_class("tcp 0.0.0.0:80 nginx"), "alert")
        self.assertEqual(det_host.port_class("tcp 192.168.1.20%wlan0:2222 sshd"), "alert")

    def test_loopback_and_virtual_bridges_are_info(self):
        self.assertEqual(det_host.port_class("tcp 127.0.0.1:8777 n0rma"), "info")
        self.assertEqual(det_host.port_class("udp 0.0.0.0%pan1:67 dnsmasq"), "info")


if __name__ == "__main__":
    unittest.main()


class SettingsLevelMeterTest(unittest.TestCase):
    BLK = '\n\t\tapplication.name = "cinnamon"\n\t\tapplication.process.id = "42"\n\t\tmedia.name = "Peak detect"\n\t\tstream.monitor = "true"\n'
    REAL = staticmethod(lambda pid: ("cinnamon-settings", "/usr/bin/python3.12"))

    def test_real_settings_window_is_a_notice_not_an_alert(self):
        from n0rma.det_host import is_level_meter
        self.assertEqual(is_level_meter(self.BLK, self.REAL), "cinnamon-settings")

    def test_other_program_or_labels_stay_alerts(self):
        from n0rma.det_host import is_level_meter
        self.assertIsNone(is_level_meter(self.BLK, lambda pid: ("cinnamon-settings", "/tmp/evil")))
        self.assertIsNone(is_level_meter(self.BLK, lambda pid: ("evil", "/usr/bin/python3.12")))
        self.assertIsNone(is_level_meter(self.BLK.replace("Peak detect", "Capture"), self.REAL))

    def test_duplicate_or_missing_properties_are_never_a_meter(self):
        from n0rma.det_host import is_level_meter
        self.assertIsNone(is_level_meter(self.BLK + '\t\tapplication.process.id = "99"\n', self.REAL))
        self.assertIsNone(is_level_meter(self.BLK.replace('application.process.id = "42"', ''), self.REAL))
