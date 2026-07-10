from dataclasses import dataclass
from typing import Optional


@dataclass
class Channel:
    id: int
    title: str
    username: Optional[str] = None
    total_uploaded: int = 0
    active: bool = True
