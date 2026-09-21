from backend.ml.attention_model import (
    AttentionDetector,
    attention_detector,
    get_session_detector,
    _session_detectors,
)


def main():
    print("\n=== Attention Detector Isolation Test ===\n")

    # Start clean
    _session_detectors.clear()

    # ---------------------------------------------------------
    # 1. Different participant + session => different instances
    # ---------------------------------------------------------
    a = get_session_detector("student_A", "session_1")
    b = get_session_detector("student_B", "session_1")

    assert a is not b
    print("[PASS] Different participants get different detectors")

    # ---------------------------------------------------------
    # 2. Same participant + same session => same instance
    # ---------------------------------------------------------
    a_again = get_session_detector("student_A", "session_1")

    assert a_again is a
    print("[PASS] Same participant/session reuses the same detector")

    # ---------------------------------------------------------
    # 3. State remains isolated
    # ---------------------------------------------------------
    a.blink_timestamps.append(123.456)

    assert 123.456 in a.blink_timestamps
    assert 123.456 not in b.blink_timestamps

    print("[PASS] State mutation in student_A does not affect student_B")

    # ---------------------------------------------------------
    # 4. Test additional mutable state if present
    # ---------------------------------------------------------
    if hasattr(a, "_smoothed_score"):
        original_b_score = getattr(b, "_smoothed_score", None)

        a._smoothed_score = 999.0

        assert getattr(b, "_smoothed_score", None) == original_b_score

        print("[PASS] _smoothed_score is isolated")

    if hasattr(a, "_prev_ear"):
        original_b_ear = getattr(b, "_prev_ear", None)

        a._prev_ear = 999.0

        assert getattr(b, "_prev_ear", None) == original_b_ear

        print("[PASS] _prev_ear is isolated")

    # ---------------------------------------------------------
    # 5. Same participant, different sessions => isolated
    # ---------------------------------------------------------
    c = get_session_detector("student_A", "session_2")

    assert c is not a
    assert c is not b

    assert len(c.blink_timestamps) == 0

    print("[PASS] Different sessions get isolated detectors")

    # ---------------------------------------------------------
    # 6. Dev singleton must be separate
    # ---------------------------------------------------------
    assert attention_detector is not a
    assert attention_detector is not b
    assert attention_detector is not c

    print("[PASS] Dev singleton is separate from session detectors")

    # ---------------------------------------------------------
    # 7. Check registry
    # ---------------------------------------------------------
    expected_keys = {
        ("student_A", "session_1"),
        ("student_B", "session_1"),
        ("student_A", "session_2"),
    }

    assert set(_session_detectors.keys()) == expected_keys

    print("[PASS] Registry contains exactly the expected sessions")

    print("\n=== ALL TESTS PASSED ===\n")


if __name__ == "__main__":
    main()