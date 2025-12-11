def get_cors_headers(cors_origin: str, additional_headers: list[str]) -> dict[str, str]:
    """Generate CORS headers from config.

    Returns ACAO from configured origin and optionally ACAH from additional_headers.
    Returns empty dict if no CORS origin is configured.
    """
    if not cors_origin:
        return {}

    additional_headers = [h.lower() for h in additional_headers]
    headers = {'Access-Control-Allow-Origin': cors_origin}

    if additional_headers:
        # assert no duplicates
        assert len(additional_headers) == len(set(additional_headers)), (
            f'duplicate headers found: {additional_headers}'
        )
        headers['Access-Control-Allow-Headers'] = ', '.join(additional_headers)

    return headers
