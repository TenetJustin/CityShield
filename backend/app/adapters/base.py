from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class AdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def validate(self) -> None:
        if not (-180 <= self.west < self.east <= 180):
            raise ValueError("invalid west/east bounds")
        if not (-90 <= self.south < self.north <= 90):
            raise ValueError("invalid south/north bounds")

    def csv(self) -> str:
        self.validate()
        return f"{self.west},{self.south},{self.east},{self.north}"


class RawAdapter(Protocol):
    source_id: str

    async def fetch(self, **kwargs: Any) -> list[dict[str, Any]]: ...

