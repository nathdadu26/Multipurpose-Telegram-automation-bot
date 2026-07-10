from dataclasses import dataclass
from typing import Optional


@dataclass
class Group:
    id: int
    title: str
    username: Optional[str] = None
    active: bool = True
