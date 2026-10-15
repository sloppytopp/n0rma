"""Hidden-microphone sweep (RTL-SDR). A microphone itself is silent; this looks for the transmitter
that would carry its audio.

1. baseline: sweep the quiet house, remember every steady narrowband carrier (broadcast stations,
   your own gear) so they are never flagged.
2. sweep: sweep again, flag steady narrowband carriers that are NOT in the baseline.
3. tone test: for a flagged frequency, play a tone in the room, demodulate that frequency, and check
   whether the tone comes back. A carrier that repeats a tone you just played is carrying room audio.

A clean result never proves a room is free of bugs: recorders that do not transmit, wired mics,
bursting/digital transmitters and anything above ~1.7 GHz are invisible to this.
"""
import json
import math
import os
import random
import shutil
import statistics
import struct
import subprocess
import time
import wave

from .core import DATA_DIR

BASELINE_PATH = os.path.join(DATA_DIR, "mic_baseline.json")
BINS = 25_000                      # Hz per rtl_power bin
RANGES = [                         # (label, low Hz, high Hz) - where analog audio bugs live
    ("VHF low/FM broadcast 30-108 MHz", 30e6, 108e6),
    ("VHF 108-175 MHz (air, handheld, bugs)", 108e6, 175e6),
    ("VHF high 175-300 MHz (wireless mics, TV)", 175e6, 300e6),
    ("UHF 300-520 MHz (bugs, ISM 315/433)", 300e6, 520e6),
    ("UHF wireless mics 520-700 MHz", 520e6, 700e6),
    ("800-960 MHz (ISM 868/915, wireless mics)", 800e6, 960e6),
    ("1.2 GHz analog video/audio TX", 1.08e9, 1.32e9),
]
FLAG_DB = 10.0          # a NEW carrier must sit this far above the local noise floor...
BASE_DB = 6.0           # ...but baseline carriers are recorded at this lower bar, so a faint legit carrier cannot flicker back as "new"
CARRIER_DB = FLAG_DB
GAIN = 30.0             # dB, FIXED: automatic gain moves the noise floor between passes and makes carriers appear and vanish
PERSIST = 0.7           # ...and show up in this fraction of passes to count as steady
MATCH_HZ = 2 * BINS     # baseline match tolerance (drift)
TONE_HZ = 1000.0


def parse_rows(text):
    """rtl_power CSV -> list of (freq_hz, db)."""
    out = []
    for line in text.splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) < 7:
            continue
        try:
            lo, step = float(p[2]), float(p[4])
            dbs = [float(x) for x in p[6:]]
        except ValueError:
            continue
        out += [(lo + i * step, d) for i, d in enumerate(dbs)]
    return out


def carriers(points, over_db=None):
    """One pass: local-peak bins at least CARRIER_DB over the median floor, <=3 bins wide (narrowband).
    -> {rounded_freq_hz: db}"""
    if len(points) < 8:
        return {}
    pts = sorted(points)
    over_db = CARRIER_DB if over_db is None else over_db
    floor = statistics.median(d for _, d in pts)
    found = {}
    for i, (f, d) in enumerate(pts):
        if d < floor + over_db:
            continue
        lo, hi = max(0, i - 1), min(len(pts), i + 2)
        if d < max(x[1] for x in pts[lo:hi]):
            continue                                     # not the local peak
        lo_i = hi_i = i                                  # width of the contiguous run above threshold: a wide hump
        while lo_i > 0 and pts[lo_i - 1][1] >= floor + over_db:   # is noise/data/TV, not a narrowband audio carrier
            lo_i -= 1
        while hi_i < len(pts) - 1 and pts[hi_i + 1][1] >= floor + over_db:
            hi_i += 1
        if hi_i - lo_i + 1 > 3:
            continue
        found[round(f / BINS) * BINS] = d
    return found


def steady(passes):
    """Carriers present in >= PERSIST of the passes -> {freq: mean_db}."""
    n = len(passes)
    seen = {}
    for p in passes:
        for f, d in p.items():
            seen.setdefault(f, []).append(d)
    return {f: statistics.mean(v) for f, v in seen.items() if len(v) / n >= PERSIST}


def diff(current, baseline_freqs):
    """Steady carriers with no baseline carrier within MATCH_HZ -> sorted [(freq, db)]."""
    base = sorted(baseline_freqs)
    return sorted((f, d) for f, d in current.items() if not any(abs(f - b) <= MATCH_HZ for b in base))


def band_of(hz):
    for name, lo, hi in RANGES:
        if lo <= hz <= hi:
            return name
    return "outside swept ranges"


def have_tools():
    return {t: bool(shutil.which(t)) for t in ("rtl_power", "rtl_fm")}


def sweep_once(ranges=RANGES, integ=4):
    pts = []
    for _, lo, hi in ranges:
        r = subprocess.run(["rtl_power", "-f", f"{int(lo)}:{int(hi)}:{BINS}", "-g", str(GAIN), "-i", str(integ), "-1", "-"],
                           capture_output=True, text=True, timeout=900)
        pts += parse_rows(r.stdout)
    return pts


def run_passes(passes=5, ranges=RANGES, progress=print, over_db=None):
    out = []
    for n in range(passes):
        progress(f"  pass {n + 1}/{passes} ...")
        out.append(carriers(sweep_once(ranges), over_db))
    return steady(out)


def save_baseline(freqs, path=BASELINE_PATH, gain=GAIN):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"ts": time.time(), "gain": gain, "carriers": sorted(freqs)}, f)


def load_baseline(path=BASELINE_PATH):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---- tone (feedback) test -------------------------------------------------------------------------

def goertzel(samples, rate, freq):
    """Signal power at one frequency."""
    k = 2 * math.cos(2 * math.pi * freq / rate)
    s1 = s2 = 0.0
    for x in samples:
        s1, s2 = x + k * s1 - s2, s1
    return s1 * s1 + s2 * s2 - k * s1 * s2


def _corr(lp, pat):
    mp, mt = statistics.mean(lp), statistics.mean(pat)
    den = math.sqrt(sum((a - mp) ** 2 for a in lp) * sum((b - mt) ** 2 for b in pat)) or 1e-9
    return sum((a - mp) * (b - mt) for a, b in zip(lp, pat)) / den


def tone_score(samples, rate, pattern, win_s, freq=TONE_HZ, perms=400, seed=7):
    """-> (corr, on_over_off_db, p). Playback starts a little after capture, so the best of several lags is used; the shuffled-pattern
    null takes the best lag too, so searching for the lag cannot inflate the score. p = share of shuffles scoring at least as well."""
    n = int(rate * win_s)
    logs = []
    for lag in range(0, 9):
        off = int(rate * lag * 0.05)
        if off + len(pattern) * n > len(samples):
            break
        logs.append([math.log10(goertzel(samples[off + i * n:off + (i + 1) * n], rate, freq) + 1e-12) for i in range(len(pattern))])
    if not logs or len(set(pattern)) < 2:
        return 0.0, 0.0, 1.0
    best = lambda pat: max(_corr(l, pat) for l in logs)
    real = best(pattern)
    rnd = random.Random(seed)
    ge = 0
    for _ in range(perms):
        sh = list(pattern)
        rnd.shuffle(sh)
        if best(sh) >= real:
            ge += 1
    l = max(logs, key=lambda l: _corr(l, pattern))
    on = [10 ** x for x, t in zip(l, pattern) if t]
    off = [10 ** x for x, t in zip(l, pattern) if not t]
    return real, 10 * math.log10((statistics.mean(on) + 1e-12) / (statistics.mean(off) + 1e-12)), (ge + 1) / (perms + 1)


def random_pattern(windows=16):
    while True:
        p = [random.randint(0, 1) for _ in range(windows)]
        if windows // 4 <= sum(p) <= windows - windows // 4:
            return p


def hit(sc):
    return sc[0] >= 0.8 and sc[1] >= 6 and sc[2] <= 0.01


def verdict(target, controls):
    """Any control that also hears the tone = leak in the phone/dongle chain: inconclusive, never an alert."""
    if not controls:
        return "possible"
    if any(c[0] >= 0.5 or c[2] <= 0.05 for c in controls):
        return "coupling" if hit(target) else "none"
    if hit(target):
        return "confirmed"
    return "possible" if target[0] >= 0.5 and target[2] <= 0.05 else "none"


def pick_control(target, baseline, current=()):
    busy = list(baseline) + list(current)
    for off in (250e3, -250e3, 500e3, -500e3, 1e6, -1e6, 2e6, -2e6):
        f = target + off
        if f > 24e6 and all(abs(b - f) >= 100e3 for b in busy):
            return f
    return None


def pick_carrier_control(target, baseline):
    c = [b for b in baseline if 300e3 <= abs(b - target) <= 20e6]
    return min(c, key=lambda b: abs(b - target)) if c else None


def write_tone_wav(path, pattern, win_s, rate=44100, freq=TONE_HZ):
    n = int(rate * win_s)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for on in pattern:
            w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)) if on else 0)
                                   for i in range(n)))


def measure(freq_hz, mode="fm", win_s=0.8, windows=16, rate=24000, play=None):
    """Play a fresh random pattern in the room while demodulating freq_hz -> (corr, db, p)."""
    pattern = random_pattern(windows)
    wav = os.path.join(DATA_DIR, "tone_test.wav")
    os.makedirs(DATA_DIR, exist_ok=True)
    write_tone_wav(wav, pattern, win_s)
    os.chmod(wav, 0o600)
    cmd = ["rtl_fm", "-f", str(int(freq_hz)), "-M", mode, "-s", str(rate), "-r", str(rate), "-g", str(GAIN), "-E", "dc", "-"]
    rec = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    time.sleep(1.5)                                      # tuner settle
    player = play or shutil.which("paplay") or shutil.which("aplay")
    if not player:
        rec.kill()
        raise RuntimeError("no audio player (paplay/aplay) found")
    subprocess.run([player, wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    rec.terminate()
    data = rec.stdout.read()
    data = data[int(rate * 1.5) * 2:]                    # drop the settle period (capture of audio starts ~1.5 s before playback)
    samples = struct.unpack(f"<{len(data) // 2}h", data[:len(data) // 2 * 2])
    return tone_score(samples, rate, pattern, win_s)


def tone_test(freq_hz, baseline=(), mode="fm", **kw):
    """Target + controls (an empty nearby frequency and a nearby real baseline carrier), each with its own random pattern.
    -> (target_score, [(control_hz, score)], verdict)."""
    target = measure(freq_hz, mode, **kw)
    controls = []
    for f in (pick_control(freq_hz, baseline), pick_carrier_control(freq_hz, baseline)):
        if f:
            controls.append((f, measure(f, mode, **kw)))
    return target, controls, verdict(target, [c[1] for c in controls])
