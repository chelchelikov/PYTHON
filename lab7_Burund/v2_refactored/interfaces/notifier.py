from typing import Protocol


class Notifier(Protocol):
    def notify(self, recipient: str, message: str) -> None:
        ...
