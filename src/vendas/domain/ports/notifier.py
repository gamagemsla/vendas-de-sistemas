from typing import Protocol


class NotifierPort(Protocol):
    def send_alert(self, message: str) -> bool: ...
