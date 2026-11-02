from n0rma import det_sdr


def test_learning_done_needs_every_band():
    full = [(0.0, 1.0, 0.0)] * det_sdr.LEARN_SWEEPS
    hist = {b[0]: list(full) for b in det_sdr.BANDS}
    assert det_sdr.learning_done(hist)
    hist[det_sdr.BANDS[-1][0]] = full[:-1]   # one band still one sweep short
    assert not det_sdr.learning_done(hist)
