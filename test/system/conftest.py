from test.system import BetterCaplog

import pytest


@pytest.fixture()
def better_caplog(caplog: pytest.LogCaptureFixture) -> BetterCaplog:
    return BetterCaplog(caplog)
