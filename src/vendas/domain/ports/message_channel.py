from typing import Any, Protocol


class MessageChannel(Protocol):
    def send(self, msg: dict[str, Any]) -> dict[str, Any]: ...
