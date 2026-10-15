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
CARRIER_DB = 10.0       # a carrier must sit this far above the local noise floor
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


def carriers(points):
    """One pass: local-peak bins at least CARRIER_DB over the median floor, <=3 bins wide (narrowband).
    -> {rounded_freq_hz: db}"""
    if len(points) < 8:
        return {}
    pts = sorted(points)
    floor = statistics.median(d for _, d in pts)
    found = {}
    for i, (f, d) in enumerate(pts):
        if d < floor + CARRIER_DB:
            continue
        lo, hi = max(0, i - 1), min(len(pts), i + 2)
        if d < max(x[1] for x in pts[lo:hi]):
            continue                                     # not the local peak
        lo_i = hi_i = i                                  # width of the contiguous run above threshold: a wide hump
        while lo_i > 0 and pts[lo_i - 1][1] >= floor + CARRIER_DB:   # is noise/data/TV, not a narrowband audio carrier
            lo_i -= 1
        while hi_i < len(pts) - 1 and pts[hi_i + 1][1] >= floor + CARRIER_DB:
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
        r = subprocess.run(["rtl_power", "-f", f"{int(lo)}:{int(hi)}:{BINS}", "-i", str(integ), "-1", "-"],
                           capture_output=True, text=True, timeout=900)
        pts += parse_rows(r.stdout)
    return pts


def run_passes(passes=5, ranges=RANGES, progress=print):
    out = []
    for n in range(passes):
        progress(f"  pass {n + 1}/{passes} ...")
        out.append(carriers(sweep_once(ranges)))
    return steady(out)


def save_baseline(freqs, path=BASELINE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"ts": time.time(), "carriers": sorted(freqs)}, f)


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


def tone_correlation(samples, rate, pattern, win_s, freq=TONE_HZ):
    """samples = demodulated audio, pattern = [1,0,1,0..] (tone on/off per window).
    Returns (corr, on_over_off_db). corr near 1 = the demodulated audio follows the on/off tone pattern."""
    n = int(rate * win_s)
    pw = [goertzel(samples[i * n:(i + 1) * n], rate, freq) for i in range(len(pattern)) if (i + 1) * n <= len(samples)]
    pat = pattern[:len(pw)]
    if len(pw) < 4 or len(set(pat)) < 2:
        return 0.0, 0.0
    lp = [math.log10(p + 1e-9) for p in pw]
    mp, mt = statistics.mean(lp), statistics.mean(pat)
    num = sum((a - mp) * (b - mt) for a, b in zip(lp, pat))
    den = math.sqrt(sum((a - mp) ** 2 for a in lp) * sum((b - mt) ** 2 for b in pat)) or 1e-9
    on = [p for p, t in zip(pw, pat) if t]
    off = [p for p, t in zip(pw, pat) if not t]
    db = 10 * math.log10((statistics.mean(on) + 1e-9) / (statistics.mean(off) + 1e-9))
    return num / den, db


def write_tone_wav(path, pattern, win_s, rate=44100, freq=TONE_HZ):
    n = int(rate * win_s)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for on in pattern:
            w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / rate)) if on else 0)
                                   for i in range(n)))


def tone_test(freq_hz, mode="fm", win_s=1.0, pattern=(0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0), rate=24000, play=None):
    """Play the pattern in the room, record the demodulated frequency meanwhile. -> (corr, db, verdict)."""
    pattern = list(pattern)
    wav = os.path.join(DATA_DIR, "tone_test.wav")
    write_tone_wav(wav, pattern, win_s)
    os.chmod(wav, 0o600)
    total = len(pattern) * win_s
    cmd = ["rtl_fm", "-f", str(int(freq_hz)), "-M", mode, "-s", str(rate), "-r", str(rate), "-E", "dc", "-"]
    rec = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    time.sleep(1.0)                                      # let the tuner settle
    player = play or shutil.which("paplay") or shutil.which("aplay")
    if not player:
        rec.kill()
        raise RuntimeError("no audio player (paplay/aplay) found")
    subprocess.run([player, wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rec.terminate()
    raw = rec.stdout.read()
    skip = int(rate * 1.0) * 2                           # drop settle period
    data = raw[skip:]
    samples = struct.unpack(f"<{len(data) // 2}h", data[:len(data) // 2 * 2])
    corr, db = tone_correlation(samples, rate, pattern, win_s)
    if corr > 0.8 and db > 6:
        v = "TONE RETURNED - this signal is carrying audio from the room"
    elif corr > 0.5:
        v = "possible - repeat closer to the source"
    else:
        v = "no tone returned - not carrying room audio (or not an FM audio signal)"
    return corr, db, v
