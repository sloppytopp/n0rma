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


def test_baseline_needs_a_full_history_for_that_band():
    full = [(5.0, 1.0, 0.0)] * det_sdr.LEARN_SWEEPS
    assert det_sdr.baseline_for([], learned=True) is None           # recovered dead band: no history yet
    assert det_sdr.baseline_for(full[:-1], learned=True) is None    # half-learned
    assert det_sdr.baseline_for(full, learned=False) is None        # global gate still closed
    assert det_sdr.baseline_for(full, learned=True) == 5.0


def test_gate_latches_open_so_a_flapping_band_cannot_close_it_again():
    full = [(0.0, 1.0, 0.0)] * det_sdr.LEARN_SWEEPS
    d = det_sdr.SdrDetector(eng=None)
    assert not d.is_armed()
    for h in d.hist.values():
        h.extend(full)
    assert d.is_armed()
    d.hist[det_sdr.BANDS[0][0]].clear()   # one band later drops out and has to relearn
    assert d.is_armed()


def test_all_bands_dead_is_not_learned_and_status_is_degraded():
    hist = {b[0]: [] for b in det_sdr.BANDS}
    dead = {b[0] for b in det_sdr.BANDS}
    assert not det_sdr.learning_done(hist, dead)
    level, msg = det_sdr.rf_summary(hist, dead)
    assert level == "watch" and "degraded" in msg


def test_status_is_never_ok_while_a_live_band_has_no_baseline():
    full = [(0.0, 1.0, 0.0)] * det_sdr.LEARN_SWEEPS
    hist = {b[0]: list(full) for b in det_sdr.BANDS}
    assert det_sdr.rf_summary(hist, set())[0] == "ok"
    hist[det_sdr.BANDS[0][0]] = []   # a recovered band relearning
    level, msg = det_sdr.rf_summary(hist, set())
    assert level == "watch" and "learning" in msg
