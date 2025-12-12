from pathlib import Path

import pytest

from qram.config import AppConfig


def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    unwanted = [
        'QRAM_BIND_TO',
        'QRAM_PORT',
        'QRAM_PROVIDER',
        'QRAM_GITHUB_APP_ID',
        'QRAM_GITHUB_INSTALLATION_ID',
        'QRAM_GITHUB_PEM',
        'QRAM_GITHUB_PEM_FILE',
        'QRAM_GITHUB_HMAC',
        'QRAM_GITHUB_HMAC_FILE',
    ]
    for k in unwanted:
        monkeypatch.delenv(k, raising=False)


class TestAppConfig:
    class TestLoadFromEnv:
        def test_can_load_literal_secrets(self, monkeypatch: pytest.MonkeyPatch) -> None:
            clear_env(monkeypatch)
            monkeypatch.setenv('QRAM_PROVIDER', 'github')
            monkeypatch.setenv('QRAM_GITHUB_APP_ID', '42')
            monkeypatch.setenv('QRAM_GITHUB_INSTALLATION_ID', '67')
            monkeypatch.setenv('QRAM_GITHUB_PEM', 'ppp')
            monkeypatch.setenv('QRAM_GITHUB_HMAC', 'hhh')

            cfg = AppConfig.config_from_env()

            assert cfg.github is not None
            assert cfg.github.app_id == '42'
            assert cfg.github.installation_id == '67'
            assert cfg.github.pem == 'ppp'
            assert cfg.github.hmac == 'hhh'

        def test_missing_required_env_var_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
            clear_env(monkeypatch)
            monkeypatch.setenv('QRAM_PROVIDER', 'github')
            # intentionally omit QRAM_GITHUB_APP_ID
            monkeypatch.setenv('QRAM_GITHUB_INSTALLATION_ID', '1')
            monkeypatch.setenv('QRAM_GITHUB_PEM', 'pem')
            monkeypatch.setenv('QRAM_GITHUB_HMAC', 'hmac')

            with pytest.raises(RuntimeError) as exc:
                _ = AppConfig.config_from_env()
            assert 'QRAM_GITHUB_APP_ID' in str(exc.value)
            assert 'QRAM_GITHUB_INSTALLATION_ID' not in str(exc.value)

        def test_unsupported_provider_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
            clear_env(monkeypatch)
            monkeypatch.setenv('QRAM_PROVIDER', 'whatever')

            with pytest.raises(RuntimeError, match='unsupported provider'):
                _ = AppConfig.config_from_env()

        class TestReadingFromFiles:
            def test_can_load_secrets_from_files(
                self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
            ) -> None:
                clear_env(monkeypatch)
                monkeypatch.setenv('QRAM_PROVIDER', 'github')
                monkeypatch.setenv('QRAM_GITHUB_APP_ID', '100')
                monkeypatch.setenv('QRAM_GITHUB_INSTALLATION_ID', '200')

                _ = (pem_file := tmp_path / 'pem.txt').write_text('ppp')
                _ = (hmac_file := tmp_path / 'hmac.txt').write_text('hhh')
                monkeypatch.setenv('QRAM_GITHUB_PEM_FILE', str(pem_file))
                monkeypatch.setenv('QRAM_GITHUB_HMAC_FILE', str(hmac_file))

                cfg = AppConfig.config_from_env()

                assert cfg.github is not None
                assert cfg.github.pem == 'ppp'
                assert cfg.github.hmac == 'hhh'

            def test_missing_file_raises(
                self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
            ) -> None:
                clear_env(monkeypatch)
                monkeypatch.setenv('QRAM_PROVIDER', 'github')
                monkeypatch.setenv('QRAM_GITHUB_APP_ID', '100')
                monkeypatch.setenv('QRAM_GITHUB_INSTALLATION_ID', '200')

                pem_file = tmp_path / 'pem.txt'
                monkeypatch.setenv('QRAM_GITHUB_PEM_FILE', str(pem_file))
                hmac_file = tmp_path / 'hmac.txt'
                monkeypatch.setenv('QRAM_GITHUB_HMAC_FILE', str(hmac_file))

                assert not pem_file.exists()
                assert not hmac_file.exists()
                with pytest.raises(ValueError, match='invalid file'):
                    _ = AppConfig.config_from_env()

            def test_empty_file_raises(
                self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
            ) -> None:
                clear_env(monkeypatch)
                monkeypatch.setenv('QRAM_PROVIDER', 'github')
                monkeypatch.setenv('QRAM_GITHUB_APP_ID', '300')
                monkeypatch.setenv('QRAM_GITHUB_INSTALLATION_ID', '400')

                _ = (pem_file := tmp_path / 'empty_pem.txt').write_text('')
                _ = (hmac_file := tmp_path / 'empty_hmac.txt').write_text('')
                monkeypatch.setenv('QRAM_GITHUB_PEM_FILE', str(pem_file))
                monkeypatch.setenv('QRAM_GITHUB_HMAC_FILE', str(hmac_file))

                with pytest.raises(ValueError, match='file is empty'):
                    _ = AppConfig.config_from_env()

            def test_literal_envvar_takes_precedence_over_file(
                self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
            ) -> None:
                clear_env(monkeypatch)
                monkeypatch.setenv('QRAM_PROVIDER', 'github')
                monkeypatch.setenv('QRAM_GITHUB_APP_ID', '500')
                monkeypatch.setenv('QRAM_GITHUB_INSTALLATION_ID', '600')
                monkeypatch.setenv('QRAM_GITHUB_PEM', 'literal_pem')
                monkeypatch.setenv('QRAM_GITHUB_HMAC', 'literal_hmac')
                _ = (pem_file := tmp_path / 'empty_pem.txt').write_text('file_pem')
                _ = (hmac_file := tmp_path / 'empty_hmac.txt').write_text('file_hmac')
                monkeypatch.setenv('QRAM_GITHUB_PEM_FILE', str(pem_file))
                monkeypatch.setenv('QRAM_GITHUB_HMAC_FILE', str(hmac_file))
                cfg = AppConfig.config_from_env()
                assert cfg.github is not None
                assert cfg.github.pem == 'literal_pem'
                assert cfg.github.hmac == 'literal_hmac'
