import pytest

from qram.web import get_cors_headers


class TestGetCorsHeaders:
    def test_missing_origin_ignores_headers(self) -> None:
        result = get_cors_headers(cors_origin='', additional_headers=['header'])

        assert result == {}

    def test_single_origin_gives_acao(self) -> None:
        result = get_cors_headers(cors_origin='origin', additional_headers=[])

        assert result == {'Access-Control-Allow-Origin': 'origin'}

    def test_origin_with_headers_gives_acao_and_acah(self) -> None:
        result = get_cors_headers(cors_origin='origin', additional_headers=['header', 'another'])

        assert result == {
            'Access-Control-Allow-Origin': 'origin',
            'Access-Control-Allow-Headers': 'header, another',
        }

    def test_duplicated_headers_raise(self) -> None:
        with pytest.raises(Exception, match='duplicate headers'):
            _ = get_cors_headers(
                cors_origin='origin', additional_headers=['header', 'HEADER', 'Header']
            )
