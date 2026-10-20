import unittest

from exceptions import TaskNotFoundError
from models import Priority, Status, Task
from repository import TaskRepository


def make_task(repo: TaskRepository, title: str = "Задача") -> Task:
    return repo.add(Task(repo.next_id(), title, Priority.HIGH, Status.TODO, "Бурунд"))


class RepositoryTests(unittest.TestCase):
    def test_add_and_get(self):
        repo = TaskRepository()
        task = make_task(repo)
        self.assertIs(repo.get(task.id), task)
        self.assertEqual(len(repo.get_all()), 1)

    def test_delete_object(self):
        repo = TaskRepository()
        task = make_task(repo)
        repo.delete(task.id)
        with self.assertRaises(TaskNotFoundError):
            repo.get(task.id)

    def test_ids_are_unique(self):
        repo = TaskRepository()
        first, second = make_task(repo), make_task(repo)
        repo.delete(second.id)
        self.assertNotEqual(make_task(repo).id, second.id)
        self.assertEqual(first.id, 1)
