import xmu_rollcall.rollcall_handler as handler


class FakeSession:
    pass


def test_wait_for_classmates_returns_true_at_threshold(monkeypatch):
    counts = iter([(6, 134), (7, 134)])
    monkeypatch.setattr(handler, "_fetch_signed_count", lambda *_: next(counts))
    monkeypatch.setattr(handler.time, "sleep", lambda *_: None)

    assert handler.wait_for_classmates(
        FakeSession(), 1, {"wait_fraction_percent": 5, "wait_max_seconds": 1}
    ) is True


def test_wait_for_classmates_returns_false_when_threshold_is_not_met(monkeypatch):
    monkeypatch.setattr(handler, "_fetch_signed_count", lambda *_: (3, 134))
    monkeypatch.setattr(handler.time, "sleep", lambda *_: None)
    monkeypatch.setattr(handler.time, "monotonic", iter([0, 0, 2]).__next__)

    assert handler.wait_for_classmates(
        FakeSession(), 1, {"wait_fraction_percent": 5, "wait_max_seconds": 1}
    ) is False