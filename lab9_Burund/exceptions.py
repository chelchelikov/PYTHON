class TaskError(Exception):
    """Базовое исключение предметной области."""


class TaskNotFoundError(TaskError):
    pass


class ValidationError(TaskError):
    pass


class ProtocolError(Exception):
    """Нарушение формата сообщений протокола."""
