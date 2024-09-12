from qram import stub_e2e


def test_e2e() -> None:
    assert stub_e2e() == '4.0'
