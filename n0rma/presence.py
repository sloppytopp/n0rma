"""Presence log: when hidden or private-address Wi-Fi sources come and go (same rules as the Android app)."""
SEEN, NAME, GONE, START, STOP = "seen", "name", "gone", "start", "stop"
GONE_AFTER = 150.0   # a source is gone once it has missed scans this long (seconds)


def locally_administered(bssid):
    try:
        return bool(int(bssid[:2], 16) & 2)
    except ValueError:
        return False


def is_logged(b):
    """Worth logging over time: it hides its name, or uses a private (locally administered) address."""
    ssid = b.get("ssid") or ""
    return ssid.strip() == "" or ssid == "(hidden)" or locally_administered(b["bssid"])


class PresenceTracker:
    def __init__(self, gone_after=GONE_AFTER):
        self.gone_after = gone_after
        self.live = {}   # key -> {last, rssi, label, freq}

    def on_scan(self, now, rows):
        out, here = [], set()
        for b in rows:
            if not is_logged(b):
                continue
            k = "wifi:" + b["bssid"]
            here.add(k)
            ssid = (b.get("ssid") or "").strip()
            l = self.live.get(k)
            if l is None:
                label = ssid or "(hidden)"
                self.live[k] = {"last": now, "rssi": b["signal"], "label": label, "freq": b.get("freq", 0)}
                out.append((now, k, label, SEEN, b["signal"], b.get("freq", 0)))
            else:
                l.update(last=now, rssi=b["signal"], freq=b.get("freq", 0))
                if ssid and ssid != "(hidden)" and ssid != l["label"]:   # a hidden source now shows a name: keep it
                    l["label"] = ssid
                    out.append((now, k, ssid, NAME, b["signal"], b.get("freq", 0)))
        for k in [k for k, l in self.live.items() if k not in here and now - l["last"] >= self.gone_after]:
            l = self.live.pop(k)
            out.append((l["last"], k, l["label"], GONE, l["rssi"], l["freq"]))
        return out


def summarize(events, now, window, scanning_now):
    """Per-source presence intervals inside [now-window, now]. events: (ts,key,label,kind) sorted by ts.
    Open intervals run to now while scanning, otherwise to the last logged event."""
    lo = now - window
    end_open = now if scanning_now else (events[-1][0] if events else now)
    open_, labels, hidden, ivs = {}, {}, set(), {}

    def close(k, end):
        s = open_.pop(k, None)
        if s is None:
            return
        a, b = max(s, lo), min(end, now)
        if b >= a and end >= lo:
            ivs.setdefault(k, []).append((a, b))

    last = 0.0
    for ts, k, label, kind in events:
        if kind == SEEN:
            open_.setdefault(k, ts)
            labels[k] = label
            if label == "(hidden)":
                hidden.add(k)
        elif kind == NAME:
            labels[k] = label
        elif kind == GONE:
            close(k, ts)
        elif kind == STOP:
            for kk in list(open_):
                close(kk, ts)
        elif kind == START:   # previous run died without saying so: nothing is known after the last thing logged
            for kk in list(open_):
                close(kk, last)
        last = ts
    for kk in list(open_):
        close(kk, end_open)
    return [{"key": k, "label": labels.get(k, k), "hidden": k in hidden, "appearances": len(v),
             "total": sum(b - a for a, b in v), "last": max(b for _a, b in v), "intervals": v}
            for k, v in ivs.items()]


def scanning_seconds(events, now, window, scanning_now):
    """How long N0RMA was actually scanning in the window, so a quiet log isn't mistaken for a quiet house."""
    lo = now - window
    start, total, last = None, 0.0, 0.0
    for ts, k, _label, kind in events:
        if k == "*" and kind == START:
            if start is not None:
                total += max(0.0, min(last, now) - max(start, lo))
            start = ts
        elif k == "*" and kind == STOP and start is not None:
            total += max(0.0, min(ts, now) - max(start, lo))
            start = None
        last = ts
    if start is not None and scanning_now:
        total += max(0.0, now - max(start, lo))
    return total
