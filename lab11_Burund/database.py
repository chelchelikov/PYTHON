import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "hotel.db")


class Database:
    """Фабрика соединений с SQLite. Каждое обращение получает своё соединение."""

    def __init__(self, path: str = DEFAULT_DB_PATH) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        # isolation_level=None — транзакциями управляем явно (BEGIN / COMMIT / ROLLBACK)
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            else:
                connection.execute("COMMIT")

    def init(self, seed: bool = True) -> None:
        scripts = ["schema.sql"] + (["seed.sql"] if seed else [])
        with self.connect() as connection:
            for name in scripts:
                with open(os.path.join(BASE_DIR, "db", name), encoding="utf-8") as file:
                    connection.executescript(file.read())

    def exists(self) -> bool:
        return os.path.exists(self.path)
