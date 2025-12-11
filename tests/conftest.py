import pytest

# session and config are unused but are required to be named exactly this way by pytest innards
# ruff: noqa: ARG001


# enforce unit tests run first and e2e last
def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    directory_order = ['unit', 'integration', 'behavior', 'e2e']

    def get_sort_key(item: pytest.Item) -> tuple[int, int]:
        # nodeid is like "tests/unit/test_web.py::test_function"
        parts = item.nodeid.split('/')
        assert len(parts) > 1, f'{item.nodeid}: test files should belong to a directory'
        test_dir = parts[1]
        priority = directory_order.index(test_dir)
        return (priority, items.index(item))

    items[:] = sorted(items, key=get_sort_key)
