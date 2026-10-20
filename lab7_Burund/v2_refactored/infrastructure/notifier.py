"""Реализации уведомлений клиента. Новая реализация — новый класс (OCP)."""

from datetime import datetime


class ConsoleNotifier:
    def notify(self, recipient: str, message: str) -> None:
        print(f"[УВЕДОМЛЕНИЕ -> {recipient}] {message}")


class FileNotifier:
    def __init__(self, path: str) -> None:
        self._path = path

    def notify(self, recipient: str, message: str) -> None:
        with open(self._path, "a", encoding="utf-8") as file:
            file.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {recipient}: {message}\n")


class CompositeNotifier:
    def __init__(self, *notifiers) -> None:
        self._notifiers = notifiers

    def notify(self, recipient: str, message: str) -> None:
        for notifier in self._notifiers:
            notifier.notify(recipient, message)
