from qram import stub_integration


def test_integration() -> None:
    assert stub_integration() == 1
