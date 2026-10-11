"""Bluetooth "pairing pop-up flood" detector (Flipper Zero / phone-app Bluetooth spam).

A flood is many DIFFERENT, randomly changing addresses sending pairing advertisements (Apple, Google Fast Pair, Windows Swift Pair) within a short
window, with almost every advertisement coming from a new address. Real devices repeat one address. This is a behaviour test, not a fingerprint of
one tool, so it keeps working when the attacking tool changes its payloads. Same logic and thresholds as the Android app."""
import threading
from collections import Counter, deque
from dataclasses import dataclass

APPLE, MICROSOFT, FAST_PAIR = 0x004C, 0x0006, "fe2c"


def family(manufacturer_data, service_data):
    """Which pop-up family an advertisement belongs to, or None. Apple 0x07 = Proximity Pairing, 0x0F = Nearby Action; Google Fast Pair = service
    data 0xFE2C; Windows Swift Pair = Microsoft beacon 0x03 0x00."""
    mfr = manufacturer_data or {}
    a = mfr.get(APPLE)
    if a:
        if a[0] == 0x07:
            return "Apple pairing pop-up"
        if a[0] == 0x0F:
            return "Apple setup pop-up"
    for k in (service_data or {}):
        k = k.lower()
        if (k.startswith("0000") and k[4:8] == FAST_PAIR and k.endswith("-0000-1000-8000-00805f9b34fb")) or k == FAST_PAIR:
            return "Google Fast Pair pop-up"
    m = mfr.get(MICROSOFT)
    if m and len(m) >= 2 and m[0] == 0x03 and m[1] == 0x00:
        return "Windows Swift Pair pop-up"
    return None


@dataclass
class SpamState:
    level: str
    message: str
    distinct: int = 0
    family: str = ""
    strongest: int = -127


class SpamDetector:
    def __init__(self, window=30.0, watch_distinct=12, alert_distinct=30, alert_sustain=60.0, min_unique_ratio=0.6):
        self.window, self.watch, self.alert_n = window, watch_distinct, alert_distinct
        self.sustain, self.ratio = alert_sustain, min_unique_ratio
        self.ads = deque()          # (addr, family, rssi, ts)
        self.flood_since = 0.0
        self.quiet_since = 0.0
        self.lock = threading.Lock()

    def on_ad(self, addr, fam, rssi, now):
        with self.lock:
            self.ads.append((addr, fam, rssi, now))
            while len(self.ads) > 5000:
                self.ads.popleft()

    def _settle(self, now, flood):
        if flood:
            if not self.flood_since:
                self.flood_since = now
            self.quiet_since = 0.0
        elif self.flood_since:
            if not self.quiet_since:
                self.quiet_since = now
            if now - self.quiet_since > 15:
                self.flood_since = self.quiet_since = 0.0

    def evaluate(self, now):
        ok = SpamState("ok", "No Bluetooth pop-up flood heard (watching Apple, Google and Windows pairing signals)")
        with self.lock:
            while self.ads and now - self.ads[0][3] > self.window:
                self.ads.popleft()
            if not self.ads:
                self._settle(now, False)
                return ok
            distinct = len({a[0] for a in self.ads})
            flood = distinct >= self.watch and distinct / len(self.ads) >= self.ratio
            self._settle(now, flood)
            if not flood:
                return ok
            fam = Counter(a[1] for a in self.ads).most_common(1)[0][0]
            strongest = max(a[2] for a in self.ads)
            alert = distinct >= self.alert_n and now - self.flood_since >= self.sustain
        msg = (f"{distinct} different fake pairing signals in {int(self.window)} s ({fam}), strongest {strongest} dBm. Consistent with a Bluetooth spam tool "
               "(for example a Flipper Zero or a phone app). Nothing is connecting to you; turn Bluetooth off if pop-ups appear.")
        return SpamState("alert" if alert else "watch", msg, distinct, fam, strongest)
