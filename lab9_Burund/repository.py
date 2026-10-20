from exceptions import TaskNotFoundError
from models import Task


class TaskRepository:
    """Хранение задач в памяти процесса."""

    def __init__(self) -> None:
        self._tasks: dict[int, Task] = {}
        self._next_id = 1

    def next_id(self) -> int:
        task_id = self._next_id
        self._next_id += 1
        return task_id

    def add(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    def get(self, task_id: int) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise TaskNotFoundError(f"Задача с id={task_id} не найдена") from None

    def get_all(self) -> list[Task]:
        return list(self._tasks.values())

    def update(self, task: Task) -> Task:
        self.get(task.id)
        self._tasks[task.id] = task
        return task

    def delete(self, task_id: int) -> None:
        self.get(task_id)
        del self._tasks[task_id]
