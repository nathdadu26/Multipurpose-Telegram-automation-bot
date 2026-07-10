from dataclasses import dataclass
from typing import Optional


@dataclass
class CopyJob:
    job_id: str
    source_channel_id: int
    start_message: int
    end_message: int
    current_message: int
    copied: int = 0
    skipped: int = 0
    status: str = "running"
    current_target_channel: Optional[int] = None
