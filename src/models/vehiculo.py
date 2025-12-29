from dataclasses import dataclass
import time

@dataclass
class Vehiculo:
    id: int
    origen: str
    t_llegada: float

    def tiempo_espera(self, now: float | None = None) -> float:
        now = now if now is not None else time.time()
        return max(0.0, now - self.t_llegada)
