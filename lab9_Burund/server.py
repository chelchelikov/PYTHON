"""Лабораторная работа №9. Вариант 5. Учебные задачи — TCP-сервер.

Каждый клиент обслуживается в отдельном потоке. Дополнительно по UDP
отдаётся краткая статистика сервера (команда stats).
"""

import argparse
import json
import logging
import socket
import threading
from typing import Any, Callable

import protocol
from exceptions import ProtocolError, TaskError
from models import Task
from repository import TaskRepository
from service import TaskService

HOST = "127.0.0.1"
TCP_PORT = 9090
UDP_PORT = 9091
CLIENT_TIMEOUT = 120  # секунд бездействия клиента до отключения

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("server")


def _task_id(data: dict[str, Any]) -> int:
    value = data.get("id")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError("Обязательное поле id должно быть целым числом")
    return value


def _tasks(tasks: list[Task]) -> list[dict]:
    return [task.to_dict() for task in tasks]


class RequestHandler:
    """Сопоставляет команды протокола с методами сервиса."""

    def __init__(self, service: TaskService) -> None:
        self.service = service
        self.commands: dict[str, Callable[[dict], Any]] = {
            "list": lambda d: _tasks(self.service.list_tasks()),
            "get": lambda d: self.service.get_task(_task_id(d)).to_dict(),
            "create": lambda d: self.service.create_task(d).to_dict(),
            "update": lambda d: self.service.update_task(_task_id(d), d).to_dict(),
            "delete": self._delete,
            "filter_by_priority": self._filter,
            "stats": lambda d: self.service.statistics(),
            "ping": lambda d: "pong",
        }

    def _delete(self, data: dict) -> dict:
        task_id = _task_id(data)
        self.service.delete_task(task_id)
        return {"deleted": task_id}

    def _filter(self, data: dict) -> list[dict]:
        if "priority" not in data:
            raise ProtocolError("Обязательное поле priority отсутствует")
        return _tasks(self.service.filter_by_priority(data["priority"],
                                                      bool(data.get("min_level"))))

    def handle(self, raw: bytes) -> dict[str, Any]:
        try:
            command, data = protocol.parse_request(protocol.decode(raw))
            handler = self.commands.get(command)
            if handler is None:
                raise ProtocolError(f"Неизвестная команда: {command}")
            log.info("Command: %s %s", command, data or "")
            result = handler(data)
            log.info("Command %s executed", command)
            return protocol.ok(result)
        except (ProtocolError, TaskError) as error:
            log.warning("Bad request: %s", error)
            return protocol.error(str(error))
        except Exception:
            log.exception("Unexpected error")
            return protocol.error("Внутренняя ошибка сервера")


class TaskServer:
    def __init__(self, handler: RequestHandler, host: str = HOST, port: int = TCP_PORT,
                 udp_port: int | None = UDP_PORT) -> None:
        self.handler = handler
        self.host = host
        self.port = port
        self.udp_port = udp_port
        self._running = threading.Event()
        self._sock: socket.socket | None = None

    def serve_client(self, conn: socket.socket, address: tuple) -> None:
        peer = f"{address[0]}:{address[1]}"
        log.info("Client connected: %s", peer)
        conn.settimeout(CLIENT_TIMEOUT)
        stream = protocol.MessageStream(conn)
        try:
            while self._running.is_set():
                raw = stream.receive()
                if raw is None:
                    break
                if raw.strip():
                    stream.send(self.handler.handle(raw))
        except socket.timeout:
            log.info("Client %s timed out", peer)
        except ProtocolError as error:
            log.warning("Client %s protocol error: %s", peer, error)
        except (ConnectionResetError, BrokenPipeError):
            log.warning("Connection with %s was reset", peer)
        finally:
            conn.close()
            log.info("Client disconnected: %s", peer)

    def serve_udp(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((self.host, self.udp_port))
            sock.settimeout(1)
            log.info("UDP stats endpoint on %s:%s", self.host, self.udp_port)
            while self._running.is_set():
                try:
                    payload, address = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                response = self.handler.handle(payload.strip() or b'{"command": "stats"}')
                sock.sendto(json.dumps(response, ensure_ascii=False).encode(), address)

    def start(self) -> None:
        self._running.set()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self.port = self._sock.getsockname()[1]
        self._sock.listen()
        self._sock.settimeout(1)
        log.info("Server started on %s:%s", self.host, self.port)
        if self.udp_port is not None:
            threading.Thread(target=self.serve_udp, daemon=True).start()

    def serve_forever(self) -> None:
        while self._running.is_set():
            try:
                conn, address = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self.serve_client, args=(conn, address), daemon=True).start()

    def stop(self) -> None:
        self._running.clear()
        if self._sock:
            self._sock.close()
        log.info("Server stopped")


def create_server(port: int = TCP_PORT, udp_port: int | None = UDP_PORT,
                  demo_data: bool = True) -> TaskServer:
    service = TaskService(TaskRepository())
    if demo_data:
        for title, priority, status, assignee in (
            ("Лабораторная по сетям", "high", "in_progress", "Бурунд"),
            ("Подготовить отчёт", "medium", "todo", "Бурунд"),
            ("Курсовой проект", "critical", "todo", "Иванов"),
            ("Прочитать главу 5", "low", "done", "Петрова"),
        ):
            service.create_task({"title": title, "priority": priority,
                                 "status": status, "assignee": assignee})
    return TaskServer(RequestHandler(service), port=port, udp_port=udp_port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Сервер учебных задач")
    parser.add_argument("--port", type=int, default=TCP_PORT)
    parser.add_argument("--udp-port", type=int, default=UDP_PORT)
    args = parser.parse_args()
    server = create_server(args.port, args.udp_port)
    server.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
