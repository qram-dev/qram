from meiga import Error


class ExpectedError(Error):
    def __init__(self, message: str):
        self.message = message
