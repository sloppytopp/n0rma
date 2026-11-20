"""Should this Remote ID broadcast be believed? Verdicts from the optional `remoteid` package.

remoteid.py reads what a broadcast claims. Nothing in Remote ID proves it: a laptop script or a
cheap ESP8266 can claim any serial, position and operator location. With the `trust` extra
(`pip install 'n0rma-sec[trust]'`) every transmitter also gets a verdict built from its history:
spoofed, suspicious, plausible or authenticated (DRIP signature), with the reasons (a position that
jumps further than an aircraft can fly, a frozen clock, counter reuse, two radios claiming one
identity, the fingerprint of a public spoofing tool). Without the package nothing changes and the
alert keeps saying "unverified".
"""
import threading

try:
    import remoteid as _rid
except ImportError:  # optional dependency
    _rid = None

AVAILABLE = _rid is not None
WIFI_OUI = bytes.fromhex("fa0bbc")
_lock = threading.Lock()
_tracker = None


def _get():
    global _tracker
    if _tracker is None:
        _tracker = _rid.Tracker()
    return _tracker


def judge(data, transport, address, rssi=None, now=None):
    """Add one frame from `address` -> {'trust', 'trust_reasons'}, or {} without remoteid.

    transport: 'ble_service_data' (0xFFFA service data) or 'wifi_vendor_ie' (OUI + body).
    `now` is time.time(). Radio input is attacker-controlled: never raises.
    """
    if _rid is None or not data:
        return {}
    try:
        ms = None if now is None else int(now * 1000)
        r = None if rssi is None else max(-128, min(127, int(rssi)))
        with _lock:
            v = _get().ingest(bytes(data), transport, address=address, now_ms=ms, unix_ms=ms, rssi=r)
        return {"trust": v.verdict, "trust_reasons": list(v.reasons)}
    except Exception:
        return {}


def judge_wifi_ie(data_hex, bssid, signal=None, now=None):
    """`iw` vendor IE data (hex after OUI FA:0B:BC) -> same as judge()."""
    try:
        body = bytes(int(x, 16) for x in data_hex.split())
    except ValueError:
        return {}
    return judge(WIFI_OUI + body, "wifi_vendor_ie", bssid, signal, now)


def describe(extra, medium):
    """The words after 'CLAIMS a drone' in an alert: '(Bluetooth; unverified)' or the verdict."""
    t = extra.get("trust")
    if not t:
        return f"({medium}; unverified)"
    why = ", ".join(extra.get("trust_reasons") or [])
    word = {"spoofed": "SPOOFED", "authenticated": "signature verified"}.get(t, t)
    return f"({medium}; remoteid: {word}{' - ' + why if why else ''})"
