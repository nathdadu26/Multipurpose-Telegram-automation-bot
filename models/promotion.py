from dataclasses import dataclass


@dataclass
class Promotion:
    message_id: int
    media_type: str
    enabled: bool = True
