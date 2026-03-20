from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DetectionResult:
    score: float  # 0-100
    flag: str | None = None  # "semantic_loop", "error_cascade", etc.
    detail: str = ""
    metadata: dict = field(default_factory=dict)


class BaseDetector(ABC):
    name: str
    default_weight: float

    @abstractmethod
    async def analyze(
        self, steps: list, thresholds: dict | None = None
    ) -> DetectionResult:
        ...
