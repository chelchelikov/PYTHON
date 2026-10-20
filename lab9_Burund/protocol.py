"""JSON-протокол. Границы сообщений — символ перевода строки (JSON Lines).

Запрос:  {"command": "...", "data": {...}}
Ответ:   {"status": "ok", "data": ...}  или  {"status": "error", "error": "..."}
"""

import json
import socket
from typing import Any

from exceptions import ProtocolError

ENCODING = "utf-8"
DELIMITER = b"\n"
MAX_MESSAGE_SIZE = 1024 * 1024


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, ensure_ascii=False).encode(ENCODING) + DELIMITER


def decode(raw: bytes) -> dict[str, Any]:
    try:
        message = json.loads(raw.decode(ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError(f"Некорректный JSON: {error}") from None
    if not isinstance(message, dict):
        raise ProtocolError("Сообщение должно быть JSON-объектом")
    return message


def make_request(command: str, data: dict | None = None) -> dict[str, Any]:
    return {"command": command, "data": data or {}}


def parse_request(message: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    command = message.get("command")
    if not isinstance(command, str) or not command:
        raise ProtocolError("Отсутствует обязательное поле command")
    data = message.get("data", {})
    if not isinstance(data, dict):
        raise ProtocolError("Поле data должно быть объектом")
    return command, data


def ok(data: Any = None) -> dict[str, Any]:
    return {"status": "ok", "data": data}


def error(text: str) -> dict[str, Any]:
    return {"status": "error", "error": text}


class MessageStream:
    """Чтение сообщений из TCP-потока с учётом границ."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buffer = b""

    def receive(self) -> bytes | None:
        """Возвращает одно сообщение без разделителя или None, если соединение закрыто."""
        while DELIMITER not in self._buffer:
            chunk = self._sock.recv(4096)
            if not chunk:
                return None
            self._buffer += chunk
            if len(self._buffer) > MAX_MESSAGE_SIZE:
                raise ProtocolError("Слишком большое сообщение")
        line, self._buffer = self._buffer.split(DELIMITER, 1)
        return line

    def send(self, message: dict[str, Any]) -> None:
        self._sock.sendall(encode(message))
