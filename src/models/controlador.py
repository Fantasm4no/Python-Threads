from dataclasses import dataclass
from typing import Dict, List, Tuple

FASES: List[Tuple[List[str], List[str]]] = [
    (["N", "S"], ["E", "O"]),
    (["E", "O"], ["N", "S"]),
]

@dataclass
class ControladorTrafico:
    fase_idx: int = 0
    ciclo: int = 0

    def siguiente_fase(self) -> Tuple[List[str], List[str]]:
        self.fase_idx = (self.fase_idx + 1) % len(FASES)
        self.ciclo += 1
        return FASES[self.fase_idx]

    def fase_actual(self) -> Tuple[List[str], List[str]]:
        return FASES[self.fase_idx]

    def aplicar_fase(self, semaforos: Dict[str, "Semaforo"]) -> None:
        verdes, rojos = self.fase_actual()
        for d in verdes:
            semaforos[d].estado = "VERDE"
        for d in rojos:
            semaforos[d].estado = "ROJO"