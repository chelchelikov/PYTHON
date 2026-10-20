"""Протоколы (структурные интерфейсы)."""

from typing import Protocol


class Reportable(Protocol):
    def get_report_data(self) -> str:
        ...


def print_report(items: list[Reportable]) -> None:
    for item in items:
        print(" ", item.get_report_data())
