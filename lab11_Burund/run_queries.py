"""Выполняет запросы из db/queries.sql на временной копии БД и печатает результаты."""

import os
import re
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))


def load_queries(path: str) -> list[tuple[str, str]]:
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"^-- (\d+\. .+)$", text, flags=re.MULTILINE)
    return [(parts[i], parts[i + 1].strip()) for i in range(1, len(parts), 2)]


def main() -> None:
    connection = sqlite3.connect(":memory:")
    for name in ("schema.sql", "seed.sql"):
        connection.executescript(open(os.path.join(BASE, "db", name), encoding="utf-8").read())

    for title, sql in load_queries(os.path.join(BASE, "db", "queries.sql")):
        print(f"\n=== {title}")
        cursor = connection.execute(sql)
        if cursor.description is None:
            print(f"Изменено строк: {cursor.rowcount}")
            continue
        columns = [c[0] for c in cursor.description]
        rows = cursor.fetchall()
        print(" | ".join(columns))
        for row in rows:
            print(" | ".join(str(value) for value in row))
    connection.commit()


if __name__ == "__main__":
    main()
