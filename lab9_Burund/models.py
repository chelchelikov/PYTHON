from dataclasses import asdict, dataclass
from enum import Enum


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Status(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass
class Task:
    id: int
    title: str
    priority: Priority
    status: Status
    assignee: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["priority"] = self.priority.value
        data["status"] = self.status.value
        return data
