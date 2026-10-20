import unittest

from exceptions import TaskNotFoundError, ValidationError
from models import Priority, Status
from repository import TaskRepository
from service import TaskService


def make_service() -> TaskService:
    service = TaskService(TaskRepository())
    for title, priority in (("A", "low"), ("B", "high"), ("C", "critical"), ("D", "high")):
        service.create_task({"title": title, "priority": priority, "assignee": "X"})
    return service


class ServiceTests(unittest.TestCase):
    def test_create_with_defaults(self):
        task = TaskService(TaskRepository()).create_task({"title": "T", "assignee": "Y"})
        self.assertEqual((task.priority, task.status), (Priority.MEDIUM, Status.TODO))

    def test_invalid_object(self):
        service = make_service()
        with self.assertRaises(ValidationError):
            service.create_task({"title": "", "assignee": "X"})
        with self.assertRaises(ValidationError):
            service.create_task({"title": "T", "assignee": "X", "priority": "urgent"})

    def test_update_and_missing(self):
        service = make_service()
        task = service.update_task(1, {"status": "done", "title": "A2"})
        self.assertEqual((task.status, task.title), (Status.DONE, "A2"))
        with self.assertRaises(TaskNotFoundError):
            service.update_task(99, {"status": "done"})

    def test_filter_by_priority(self):
        service = make_service()
        self.assertEqual([t.title for t in service.filter_by_priority("high")], ["B", "D"])
        self.assertEqual([t.title for t in service.filter_by_priority("high", min_level=True)],
                         ["C", "B", "D"])
