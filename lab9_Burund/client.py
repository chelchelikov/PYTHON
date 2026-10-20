"""Лабораторная работа №9. Вариант 5. Учебные задачи — TCP-клиент."""

import argparse
import json
import socket
from typing import Any

import protocol
from exceptions import ProtocolError

HOST = "127.0.0.1"
TCP_PORT = 9090
UDP_PORT = 9091
RESPONSE_TIMEOUT = 5

PRIORITIES = "low, medium, high, critical"
STATUSES = "todo, in_progress, done"


class ServerError(Exception):
    """Сервер вернул status=error."""


class TaskClient:
    def __init__(self, host: str = HOST, port: int = TCP_PORT,
                 timeout: float = RESPONSE_TIMEOUT) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._stream: protocol.MessageStream | None = None

    def connect(self) -> None:
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._stream = protocol.MessageStream(self._sock)

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def request(self, command: str, data: dict | None = None) -> Any:
        if self._stream is None:
            raise ConnectionError("Нет соединения с сервером")
        self._stream.send(protocol.make_request(command, data))
        raw = self._stream.receive()
        if raw is None:
            raise ConnectionError("Сервер закрыл соединение")
        response = protocol.decode(raw)
        if response.get("status") == "ok":
            return response.get("data")
        raise ServerError(response.get("error", "неизвестная ошибка"))

    def send_raw(self, text: str) -> dict:
        """Отправляет произвольную строку (для демонстрации обработки ошибок сервером)."""
        if self._sock is None:
            raise ConnectionError("Нет соединения с сервером")
        self._sock.sendall(text.encode(protocol.ENCODING) + protocol.DELIMITER)
        raw = self._stream.receive()
        if raw is None:
            raise ConnectionError("Сервер закрыл соединение")
        return protocol.decode(raw)

    def __enter__(self) -> "TaskClient":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def udp_stats(host: str = HOST, port: int = UDP_PORT, timeout: float = 2) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(protocol.encode(protocol.make_request("stats")), (host, port))
        payload, _ = sock.recvfrom(65535)
    return json.loads(payload.decode())


def print_tasks(tasks: list[dict]) -> None:
    if not tasks:
        print("Задач нет")
        return
    print(f"{'id':<4}{'Название':<28}{'Приоритет':<11}{'Статус':<13}Исполнитель")
    for t in tasks:
        print(f"{t['id']:<4}{t['title']:<28}{t['priority']:<11}{t['status']:<13}{t['assignee']}")


def read_int(prompt: str) -> int:
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            print("Ошибка: введите целое число")


def ask_fields(required: bool) -> dict:
    data = {}
    for key, label in (("title", "Название"), ("priority", f"Приоритет ({PRIORITIES})"),
                       ("status", f"Статус ({STATUSES})"), ("assignee", "Исполнитель")):
        value = input(f"{label}{'' if required else ' [Enter — не менять]'}: ").strip()
        if value:
            data[key] = value
    return data


MENU = """
=== CLIENT: учебные задачи ===
1. Получить список
2. Получить задачу
3. Создать
4. Изменить
5. Удалить
6. Фильтр по приоритету (filter_by_priority)
7. Статистика (TCP)
8. Статистика по UDP
9. Отправить произвольный JSON
0. Выход"""


def run(client: TaskClient, host: str, udp_port: int) -> None:
    while True:
        print(MENU)
        choice = input("Введите команду: ").strip()
        try:
            if choice == "0":
                return
            elif choice == "1":
                print_tasks(client.request("list"))
            elif choice == "2":
                print_tasks([client.request("get", {"id": read_int("id: ")})])
            elif choice == "3":
                print_tasks([client.request("create", ask_fields(True))])
            elif choice == "4":
                task_id = read_int("id: ")
                print_tasks([client.request("update", {"id": task_id, **ask_fields(False)})])
            elif choice == "5":
                print("Удалено:", client.request("delete", {"id": read_int("id: ")}))
            elif choice == "6":
                priority = input(f"Приоритет ({PRIORITIES}): ").strip()
                min_level = input("Включать более высокие приоритеты? (д/н): ").strip() == "д"
                print_tasks(client.request("filter_by_priority",
                                           {"priority": priority, "min_level": min_level}))
            elif choice == "7":
                print(json.dumps(client.request("stats"), ensure_ascii=False, indent=2))
            elif choice == "8":
                print(json.dumps(udp_stats(host, udp_port), ensure_ascii=False, indent=2))
            elif choice == "9":
                print(client.send_raw(input("JSON-запрос: ")))
            else:
                print("Неизвестная команда")
        except ServerError as error:
            print("Ошибка сервера:", error)
        except socket.timeout:
            print("Ошибка: сервер не ответил за отведённое время (тайм-аут)")
        except ProtocolError as error:
            print("Ошибка протокола:", error)


def main() -> None:
    parser = argparse.ArgumentParser(description="Клиент учебных задач")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=TCP_PORT)
    parser.add_argument("--udp-port", type=int, default=UDP_PORT)
    parser.add_argument("--timeout", type=float, default=RESPONSE_TIMEOUT)
    args = parser.parse_args()
    client = TaskClient(args.host, args.port, args.timeout)
    try:
        client.connect()
        print(f"Подключено к {args.host}:{args.port}")
        run(client, args.host, args.udp_port)
    except ConnectionRefusedError:
        print("Ошибка: сервер недоступен")
    except (ConnectionError, OSError) as error:
        print("Ошибка соединения:", error)
    finally:
        client.close()


if __name__ == "__main__":
    main()
