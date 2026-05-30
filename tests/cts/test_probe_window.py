from datetime import time

from seektalent_keyword_graph.cts.probe_window import can_run_real_probe, is_within_probe_window


def test_probe_window_allows_daytime():
    assert is_within_probe_window(time(10, 0), time(9, 0), time(21, 0))


def test_probe_window_blocks_night():
    assert not is_within_probe_window(time(22, 0), time(9, 0), time(21, 0))


def test_real_probe_allowed_when_dry_run_outside_window():
    assert can_run_real_probe(
        dry_run=True,
        now=time(22, 0),
        start=time(9, 0),
        end=time(21, 0),
    )


def test_real_probe_blocked_outside_window_without_dry_run():
    assert not can_run_real_probe(
        dry_run=False,
        now=time(22, 0),
        start=time(9, 0),
        end=time(21, 0),
    )
