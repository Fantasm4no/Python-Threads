from typing import Dict, Any
from .base import BaseSimulation

class ProcessesSimulation(BaseSimulation):
    def __init__(self, cycles: int = 10):
        self.cycles_target = cycles

    def start(self) -> None:
        raise NotImplementedError("Implementaremos multiprocessing en el siguiente paso.")

    def stop(self) -> None:
        pass

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "cycle": 0,
            "phase": 0,
            "semaforos": {d: {"estado": "ROJO", "cola": 0, "cruzaron": 0, "espera_prom": 0.0}
                         for d in ["N","S","E","O"]}
        }
