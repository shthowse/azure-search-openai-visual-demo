from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional


class ChatApproach(ABC):
    @abstractmethod
    async def run(self, history: list[dict], overrides: dict[str, Any]) -> Any:
        ...


class AskApproach(ABC):
    @abstractmethod
    async def run(self, q: str, overrides: dict[str, Any]) -> Any:
        ...


@dataclass
class ThoughtStep:
    title: str
    description: str
    props: Optional[dict[str, Any]] = None


@dataclass
class ApproachResult:
    answer: str
    data_points: dict[str, List[Any]]
    thought_steps: List[ThoughtStep]


class Approach:
    def run(self, q: str, overrides: dict[str, Any]) -> ApproachResult:
        raise NotImplementedError
