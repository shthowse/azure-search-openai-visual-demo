from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


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
    props: Optional[Dict[str, Any]] = None

@dataclass
class ApproachResult:
    answer: str
    data_points: Dict[str, List[Any]]
    thoughtSteps: List[ThoughtStep]

class Approach:
    def run(self, q: str, overrides: dict[str, Any]) -> ApproachResult:
        raise NotImplementedError
