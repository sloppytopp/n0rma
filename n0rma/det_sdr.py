"""RTL-SDR RF watch. Dormant until an RTL-SDR dongle + rtl_power are present.

Sweeps the bands where bugs, trackers, handhelds and analog 1.2 GHz video transmitters live,
learns a per-band baseline, and flags carriers well above it.
"""
import shutil
import statistics
import subprocess
import time

BANDS = [
    ("VHF handheld/FRS 136-174 MHz", 136e6, 174e6),
    ("300-330 MHz (315 remotes, key fobs)", 300e6, 330e6),
    ("UHF 400-470 MHz (GMRS, bugs)", 400e6, 470e6),
    ("ISM 433 MHz (sensors, key fobs, bugs)", 430e6, 440e6),
    ("800 MHz (public safety trunking, ESMR)", 806e6, 869e6),
    ("ISM 868 MHz (EU trackers/sensors)", 863e6, 870e6),
    ("ISM 915 MHz (US trackers/sensors/LoRa)", 902e6, 928e6),
    ("928-1000 MHz (pagers, 960 aero band)", 928e6, 1000e6),
    ("1.2 GHz analog video / spy-cam TX", 1.08e9, 1.32e9),
]
LEARN_SWEEPS = 12
JUMP_DB = 12.0
FAIL_LIMIT = 3   # consecutive empty sweeps before a band is treated as unavailable


def parse_rtl_power(text):
    """-> (peak_db, peak_hz, median_db) over all rows of an rtl_power CSV."""
    peak, peak_hz, vals = -999.0, 0.0, []
    for line in text.splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) < 7:
            continue
        try:
            lo, step = float(p[2]), float(p[4])
            dbs = [float(x) for x in p[6:]]
        except ValueError:
            continue
        for i, d in enumerate(dbs):
            vals.append(d)
            if d > peak:
                peak, peak_hz = d, lo + i * step
    if not vals:
        return None
    return peak, peak_hz, statistics.median(vals)


def learning_done(hist, dead=frozenset()):
    """True once every working band has a full baseline; a band that returns no data (dead) cannot hold the others back."""
    return all(len(h) >= LEARN_SWEEPS for n, h in hist.items() if n not in dead)


def baseline_for(h, learned):
    """Mean peak of this band's own history, or None while the band (or the global gate) is not ready."""
    if not learned or len(h) < LEARN_SWEEPS:
        return None
    return statistics.mean(x[0] for x in h)


def note_sweep(fails, name, ok):
    fails[name] = 0 if ok else fails.get(name, 0) + 1


def dead_bands(fails):
    return {n for n, c in fails.items() if c >= FAIL_LIMIT}


def dongle_present():
    if not shutil.which("rtl_power"):
        return False
    try:
        r = subprocess.run(["lsusb"], capture_output=True, text=True).stdout
        return "0bda:2838" in r or "0bda:2832" in r or "RTL28" in r
    except Exception:
        return False


class SdrDetector:
    def __init__(self, eng):
        self.eng = eng
        self.hist = {b[0]: [] for b in BANDS}
        self.fails = {}
        self.armed = False   # latches once every working band has learned; later a band that relearns cannot close it again

    def is_armed(self):
        if not self.armed and learning_done(self.hist, dead_bands(self.fails)):
            self.armed = True
        return self.armed

    def start(self):
        import threading
        if not dongle_present():
            self.eng.status("rf", "off", "RTL-SDR not detected (install rtl-sdr, plug in dongle, restart)")
            return False
        threading.Thread(target=self._loop, daemon=True, name="sdr").start()
        return True

    def _sweep_band(self, name, lo, hi, learned, hot):
        try:
            r = subprocess.run(["rtl_power", "-f", f"{int(lo)}:{int(hi)}:25k", "-i", "4", "-1", "-"],
                               capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            note_sweep(self.fails, name, ok=False)
            return
        res = parse_rtl_power(r.stdout)
        note_sweep(self.fails, name, ok=bool(res))
        if not res:
            self.eng.status("rf", "watch", f"rtl_power returned no data: {r.stderr.strip()[:80]}")
            return
        peak, hz, floor = res
        h = self.hist[name]
        base = baseline_for(h, learned)
        if base is not None and peak > base + JUMP_DB:
            hot.append((name, hz, peak, base))
            self.eng.emit("rf", "alert", "rf_spike", name,
                          f"RF carrier in {name}: {hz/1e6:.3f} MHz at {peak:.0f} dB "
                          f"(baseline {base:.0f} dB)", {"hz": hz, "peak": peak, "base": base}, 600)
        h.append((peak, hz, floor))
        del h[:-200]
        self.eng.live.setdefault("rf", {})[name] = {"peak_db": round(peak, 1), "mhz": round(hz / 1e6, 3),
                                                     "floor_db": round(floor, 1), "samples": len(h)}

    def _loop(self):
        while not self.eng.stop.is_set():
            hot = []
            learned = self.is_armed()   # decided once per cycle
            for name, lo, hi in BANDS:
                try:
                    self._sweep_band(name, lo, hi, learned, hot)
                except Exception as e:   # one bad band must not kill the RF thread
                    note_sweep(self.fails, name, ok=False)
                    self.eng.status("rf", "watch", f"RF degraded: {name}: {type(e).__name__}")
            dead = dead_bands(self.fails)
            if hot:
                n, hz, p, b = hot[0]
                self.eng.status("rf", "alert", f"RF jump in {n}: {hz/1e6:.3f} MHz, +{p-b:.0f} dB over baseline")
            elif dead:
                self.eng.status("rf", "watch", "RF degraded: no data from " + ", ".join(sorted(dead)))
            elif not learned:
                self.eng.status("rf", "watch", "RF baseline learning (leave running ~10 min)")
            else:
                self.eng.status("rf", "ok", "RF levels within baseline in all watched bands")
        return
