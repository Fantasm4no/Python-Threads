from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseSimulation(ABC):
    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def get_snapshot(self) -> Dict[str, Any]:
        ...