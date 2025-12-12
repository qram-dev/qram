import pytest
from dotenv import load_dotenv

from qram.config import AppConfig
from qram.web.github import GithubApi


@pytest.fixture(scope='module')
def config() -> AppConfig:
    _ = load_dotenv()
    return AppConfig.config_from_env()


def test_can_access_github_app_endpoint(config: AppConfig) -> None:
    assert config.github

    api = GithubApi(config)
    response = api.http_get('app', use_jwt=True)

    assert response.is_success, f'request failed with {response.status_code}: {response.text}'
    data = response.json()
    assert 'id' in data, 'expected "id" in app response'
    assert data['id'] == int(config.github.app_id), (
        f'app ID mismatch: {data["id"]} should be {config.github.app_id}'
    )


# TODO: test token reinitialization after expiry
# would need configurable expiration time?
#  init expiration=1s
#  sleep 2s
#  with pytest.rises:
#    http_get 'app', __reinit=False
#  assert http_get 'app' == app_id
