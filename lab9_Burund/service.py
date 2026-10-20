import threading
from dataclasses import replace
from typing import Any

from exceptions import ValidationError
from models import Priority, Status, Task
from repository import TaskRepository

PRIORITY_ORDER = {p: i for i, p in enumerate(Priority)}


def _parse_enum(enum_cls, value: Any, field: str):
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_cls)
        raise ValidationError(f"Поле {field}: недопустимое значение «{value}». "
                              f"Допустимо: {allowed}") from None


def _parse_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Поле {field} должно быть непустой строкой")
    return value.strip()


class TaskService:
    """Бизнес-логика учебных задач. Потокобезопасна: сервер обслуживает клиентов в потоках."""

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository
        self._lock = threading.Lock()

    def list_tasks(self) -> list[Task]:
        with self._lock:
            return sorted(self._repository.get_all(), key=lambda t: t.id)

    def get_task(self, task_id: int) -> Task:
        with self._lock:
            return self._repository.get(task_id)

    def create_task(self, data: dict) -> Task:
        title = _parse_text(data.get("title"), "title")
        assignee = _parse_text(data.get("assignee"), "assignee")
        priority = _parse_enum(Priority, data.get("priority", "medium"), "priority")
        status = _parse_enum(Status, data.get("status", "todo"), "status")
        with self._lock:
            task = Task(self._repository.next_id(), title, priority, status, assignee)
            return self._repository.add(task)

    def update_task(self, task_id: int, data: dict) -> Task:
        changes: dict[str, Any] = {}
        if "title" in data:
            changes["title"] = _parse_text(data["title"], "title")
        if "assignee" in data:
            changes["assignee"] = _parse_text(data["assignee"], "assignee")
        if "priority" in data:
            changes["priority"] = _parse_enum(Priority, data["priority"], "priority")
        if "status" in data:
            changes["status"] = _parse_enum(Status, data["status"], "status")
        if not changes:
            raise ValidationError("Нет полей для изменения")
        with self._lock:
            task = replace(self._repository.get(task_id), **changes)
            return self._repository.update(task)

    def delete_task(self, task_id: int) -> None:
        with self._lock:
            self._repository.delete(task_id)

    def filter_by_priority(self, priority: str, min_level: bool = False) -> list[Task]:
        """Задачи заданного приоритета; при min_level=True — этого приоритета и выше."""
        level = _parse_enum(Priority, priority, "priority")
        tasks = self.list_tasks()
        if min_level:
            result = [t for t in tasks if PRIORITY_ORDER[t.priority] >= PRIORITY_ORDER[level]]
        else:
            result = [t for t in tasks if t.priority == level]
        return sorted(result, key=lambda t: PRIORITY_ORDER[t.priority], reverse=True)

    def statistics(self) -> dict[str, Any]:
        tasks = self.list_tasks()
        return {
            "total": len(tasks),
            "by_status": {s.value: sum(1 for t in tasks if t.status == s) for s in Status},
            "by_priority": {p.value: sum(1 for t in tasks if t.priority == p) for p in Priority},
        }
