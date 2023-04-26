from qram.git import extract_branches_from_line

class TestBranchExtraction:
    def test_basic(self) -> None:
        assert extract_branches_from_line('') == []
        assert extract_branches_from_line(' ') == []
        assert extract_branches_from_line('main') == ['main']
        assert extract_branches_from_line('main, dev, test') == ['main', 'dev', 'test']
        assert extract_branches_from_line('foo/bar, top/kek') == ['foo/bar', 'top/kek']

    def test_ignore_origin(self) -> None:
        assert extract_branches_from_line('origin/main, origin/foo') == []
        assert extract_branches_from_line('main, origin/main, origin/foo, bar') == ['main', 'bar']
        assert extract_branches_from_line('main, origin/main, foo/bar, top/kek/cheburek, origin/foo/bar, origin/top/kek/cheburek') \
            == ['main', 'foo/bar', 'top/kek/cheburek']

    def test_ignore_tags(self) -> None:
        assert extract_branches_from_line('tag: root, tag: v1.2.3') == []
        assert extract_branches_from_line('main, origin/main, origin/foo, bar') == ['main', 'bar']

    def test_ignore_head(self) -> None:
        assert extract_branches_from_line('HEAD') == []
        assert extract_branches_from_line('HEAD, main') == ['main']
        assert extract_branches_from_line('HEAD -> main, origin/main') == ['main']
        assert extract_branches_from_line('main, origin/main, tag: v1.2.3, origin/foo, HEAD -> bar') == ['main', 'bar']
