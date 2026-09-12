from app import throttle


def setup_function():
    throttle.reset()


def test_a_few_wrong_codes_are_tolerated():
    for _ in range(throttle.MAX_FAILURES - 1):
        throttle.record_failure("1.2.3.4")
    assert not throttle.is_blocked("1.2.3.4")


def test_too_many_wrong_codes_blocks_that_address():
    for _ in range(throttle.MAX_FAILURES):
        throttle.record_failure("1.2.3.4")
    assert throttle.is_blocked("1.2.3.4")


def test_one_address_does_not_block_another():
    for _ in range(throttle.MAX_FAILURES):
        throttle.record_failure("1.2.3.4")
    assert not throttle.is_blocked("5.6.7.8")


def test_a_correct_code_clears_the_count():
    """Getting it right proves the caller is not guessing."""
    for _ in range(throttle.MAX_FAILURES - 1):
        throttle.record_failure("1.2.3.4")
    throttle.clear("1.2.3.4")
    for _ in range(throttle.MAX_FAILURES - 1):
        throttle.record_failure("1.2.3.4")
    assert not throttle.is_blocked("1.2.3.4")


def test_failures_age_out_of_the_window(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(throttle.time, "monotonic", lambda: clock[0])

    for _ in range(throttle.MAX_FAILURES):
        throttle.record_failure("1.2.3.4")
    assert throttle.is_blocked("1.2.3.4")

    clock[0] += throttle.WINDOW_SECONDS + 1
    assert not throttle.is_blocked("1.2.3.4")
