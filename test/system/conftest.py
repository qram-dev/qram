import pytest

from test.system import BetterCaplog


@pytest.fixture()
def better_caplog(caplog: pytest.LogCaptureFixture) -> BetterCaplog:
    return BetterCaplog(caplog)
