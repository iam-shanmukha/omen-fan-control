from fanhw import MODE_AUTO, MODE_MAX, smart_target


def test_boosts_at_threshold():
    assert smart_target(80, 80, 8, MODE_AUTO) == MODE_MAX


def test_stays_auto_below_threshold():
    assert smart_target(79, 80, 8, MODE_AUTO) == MODE_AUTO


def test_holds_max_inside_hysteresis_band():
    assert smart_target(75, 80, 8, MODE_MAX) == MODE_MAX


def test_drops_to_auto_once_cooled():
    assert smart_target(72, 80, 8, MODE_MAX) == MODE_AUTO


def test_unknown_state_treated_as_auto():
    assert smart_target(75, 80, 8, "unknown") == MODE_AUTO
