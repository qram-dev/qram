from unittest.mock import Mock

from qram.github import Pr

def get_pr(num: int) -> Pr:
    body = None
    title = head = f'do-{num}'
    username='VictorQram',
    authorid = None
    if num == 1:
        title = 'add stuff'
        body = 'explanation about stuff'
        authorid = 123
    return Pr(
        number=num,
        title=title,
        body=body,
        author=dict(
            username=username,
            id=authorid
        ),
        branch_head=head
    )

def GithubMock() -> Mock:
    m = Mock()
    m.get = Mock()
    m.post = Mock()
    m.put = Mock()
    m.create_pr = Mock()
    m.get_pr = Mock(side_effect=get_pr)
    return m
