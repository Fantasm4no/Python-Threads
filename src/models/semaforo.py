from dataclasses import dataclass, field
from typing import List
from .vehiculo import Vehiculo

@dataclass
class Semaforo:
    direccion: str
    estado: str = "ROJO"
    cola: List[Vehiculo] = field(default_factory=list)

    cruzaron: int = 0
    suma_espera: float = 0.0

    def enqueue(self, v: Vehiculo) -> None:
        self.cola.append(v)

    def puede_avanzar(self) -> bool:
        return self.estado == "VERDE" and len(self.cola) > 0

    def avanzar_uno(self, now: float) -> None:
        """Simula que 1 vehículo cruza si está en verde."""
        if not self.puede_avanzar():
            return
        v = self.cola.pop(0)
        self.cruzaron += 1
        self.suma_espera += v.tiempo_espera(now)

    def espera_promedio(self) -> float:
        if self.cruzaron == 0:
            return 0.0
        return self.suma_espera / self.cruzaron