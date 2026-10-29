import json
import random

from n0rma import spectrum


def grid(extra=None, gain=40.0, n=8900, f0=24.0, step=0.2, seed=1):
    rnd = random.Random(seed)
    f = [round(f0 + i * step, 3) for i in range(n)]
    db = [-20 + rnd.uniform(-0.7, 0.7) for _ in f]
    for mhz, boost in (extra or {}).items():
        i = min(range(n), key=lambda k: abs(f[k] - mhz))
        db[i] += boost
        if i + 1 < n: db[i + 1] += boost / 2
    return {"f": f, "db": db, "gain": gain}


def test_new_carrier_is_found_and_labelled():
    base = grid()
    new = grid({433.8: 15}, seed=2)
    r = spectrum.compare_overview(base, new)
    assert r["ok"]
    assert [round(x["f"]) for x in r["new"]] == [434]
    assert r["new"][0]["rise"] >= 8
    assert r["new"][0]["label"] == "433 MHz remotes/sensors"
    assert r["gone"] == []


def test_unchanged_strong_signal_is_not_reported():
    base = grid({98.0: 20})
    new = grid({98.0: 20}, seed=2)
    assert spectrum.compare_overview(base, new)["new"] == []


def test_carrier_that_disappears_is_reported_as_gone():
    base = grid({146.6: 18})
    new = grid(seed=2)
    r = spectrum.compare_overview(base, new)
    assert r["new"] == [] and [round(x["f"]) for x in r["gone"]] == [147]


def test_small_changes_are_ignored():
    r = spectrum.compare_overview(grid(), grid({433.8: 4}, seed=2))
    assert r["new"] == []


def test_refuses_to_compare_scans_made_at_different_gain():
    r = spectrum.compare_overview(grid(gain=30.0), grid(gain=40.7, seed=2))
    assert not r["ok"] and "gain" in r["error"]


def test_nearby_points_of_one_carrier_are_merged():
    r = spectrum.compare_overview(grid(), grid({700.0: 14}, seed=2))
    assert len(r["new"]) == 1


def test_missing_data_gives_a_plain_message():
    assert not spectrum.compare_overview(None, grid())["ok"]
    assert not spectrum.compare_overview(grid(), {"f": [], "db": [], "gain": 40.0})["ok"]


def test_baseline_round_trips_through_a_file(tmp_path):
    p = str(tmp_path / "base.json")
    spectrum.save_baseline(p, grid({433.8: 5}), 1793311791)
    back = spectrum.load_baseline(p)
    assert back["f"][0] == 24.0 and back["t"] == 1793311791 and back["gain"] == 40.0


def test_load_baseline_missing_or_corrupt_is_none(tmp_path):
    assert spectrum.load_baseline(str(tmp_path / "nope.json")) is None
    bad = tmp_path / "bad.json"; bad.write_text("{not json")
    assert spectrum.load_baseline(str(bad)) is None


def test_band_labels_cover_the_gaps_found_in_the_overview():
    assert spectrum.label_for(868.436) == "800 MHz public safety / trunking"
    assert spectrum.label_for(852.883) == "800 MHz public safety / trunking"
    assert spectrum.label_for(960.01) == "Aviation (DME / TACAN)"
    assert spectrum.label_for(296.974) == "Federal / military UHF air"
    assert spectrum.label_for(881.0) == "Cell 850 downlink"      # narrower band still wins inside the wide one
