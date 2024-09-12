def stub_unit() -> int:
    return 0


def stub_integration() -> int:
    return stub_unit() + 1


def stub_behavior() -> float:
    return stub_integration() * 2.0


def stub_e2e() -> str:
    return str(stub_behavior() ** 2)
