from n0rma import det_sdr


def test_learning_done_needs_every_band():
    full = [(0.0, 1.0, 0.0)] * det_sdr.LEARN_SWEEPS
    hist = {b[0]: list(full) for b in det_sdr.BANDS}
    assert det_sdr.learning_done(hist)
    hist[det_sdr.BANDS[-1][0]] = full[:-1]   # one band still one sweep short
    assert not det_sdr.learning_done(hist)


def test_dead_band_does_not_hold_back_the_others():
    full = [(0.0, 1.0, 0.0)] * det_sdr.LEARN_SWEEPS
    hist = {b[0]: list(full) for b in det_sdr.BANDS}
    dead_name = det_sdr.BANDS[0][0]
    hist[dead_name] = []   # this band never returned data
    assert not det_sdr.learning_done(hist)
    assert det_sdr.learning_done(hist, dead={dead_name})


def test_band_is_dead_after_consecutive_failures_and_recovers():
    fails = {}
    for _ in range(det_sdr.FAIL_LIMIT):
        det_sdr.note_sweep(fails, "b", ok=False)
    assert det_sdr.dead_bands(fails) == {"b"}
    det_sdr.note_sweep(fails, "b", ok=True)
    assert det_sdr.dead_bands(fails) == set()
