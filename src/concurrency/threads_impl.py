import threading
import time
import random
from typing import Dict, Any

from ..config import GREEN_TIME, YELLOW_TIME, TICK, ARRIVAL_PROB
from ..models.semaforo import Semaforo
from ..models.vehiculo import Vehiculo
from ..models.controlador import ControladorTrafico
from .base import BaseSimulation

class ThreadsSimulation(BaseSimulation):
    def __init__(self, cycles: int = 10):
        self.cycles_target = cycles
        self._running = False

        self.semaforos: Dict[str, Semaforo] = {d: Semaforo(d) for d in ["N", "S", "E", "O"]}
        self.controlador = ControladorTrafico()

        self._lock = threading.RLock()  # requerido
        self._threads: list[threading.Thread] = []
        self._veh_id = 0

        self._phase_thread: threading.Thread | None = None
        self._last_logged_cycle = -1
        self._last_logged_phase = -1
        self._start_ts: float | None = None
        self._total_time: float | None = None

    def start(self) -> None:
        self._running = True
        self._start_ts = None
        self._total_time = None

        # Un hilo por semáforo
        for d in ["N", "S", "E", "O"]:
            t = threading.Thread(target=self._run_semaforo, args=(d,), daemon=True)
            self._threads.append(t)
            t.start()

        # Hilo controlador de fases
        self._phase_thread = threading.Thread(target=self._run_controlador, daemon=True)
        self._phase_thread.start()

    def stop(self) -> None:
        self._running = False

    def _run_controlador(self) -> None:
        # fase inicial
        with self._lock:
            self.controlador.aplicar_fase(self.semaforos)
            if self._start_ts is None:
                self._start_ts = time.time()

        while self._running and self.controlador.ciclo < self.cycles_target:
            # Verde
            t0 = time.time()
            while self._running and (time.time() - t0) < GREEN_TIME:
                time.sleep(TICK)

            # Amarillo (solo para los que estaban en verde)
            with self._lock:
                verdes, _ = self.controlador.fase_actual()
                for d in verdes:
                    self.semaforos[d].estado = "AMARILLO"

            t1 = time.time()
            while self._running and (time.time() - t1) < YELLOW_TIME:
                time.sleep(TICK)

            # Cambiar fase
            with self._lock:
                self.controlador.siguiente_fase()
                self.controlador.aplicar_fase(self.semaforos)

        self._running = False
        if self._start_ts is not None and self._total_time is None:
            self._total_time = time.time() - self._start_ts
            print(f"[THREADS] tiempo_total_threads_s = {self._total_time:.2f}")

    def _run_semaforo(self, direccion: str) -> None:
        while self._running:
            now = time.time()
            with self._lock:
                # llegada de vehículos
                if random.random() < ARRIVAL_PROB:
                    self._veh_id += 1
                    self.semaforos[direccion].enqueue(Vehiculo(self._veh_id, direccion, now))

                # cruza 1 si verde
                self.semaforos[direccion].avanzar_uno(now)

            time.sleep(TICK)

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            snap = {
                "cycle": self.controlador.ciclo,
                "phase": self.controlador.fase_idx,
                "total_time": round(self._total_time, 2) if self._total_time is not None else None,
                "semaforos": {
                    d: {
                        "estado": s.estado,
                        "cola": len(s.cola),
                        "cruzaron": s.cruzaron,
                        "espera_prom": round(s.espera_promedio(), 2),
                    } for d, s in self.semaforos.items()
                }
            }
            if (
                snap["cycle"] != self._last_logged_cycle
                or snap["phase"] != self._last_logged_phase
            ):
                self._log_snapshot(snap)
                self._last_logged_cycle = snap["cycle"]
                self._last_logged_phase = snap["phase"]
            return snap

    def _log_snapshot(self, snap: Dict[str, Any]) -> None:
        total_cruzaron = sum(s["cruzaron"] for s in snap["semaforos"].values())
        print(
            f"[THREADS] Ciclo {snap['cycle']} | Fase {snap['phase']} | "
            f"Total vehículos que cruzaron: {total_cruzaron}"
        )
        for d in ["N", "S", "E", "O"]:
            datos = snap["semaforos"][d]
            print(
                "    "
                f"{d}: estado={datos['estado']} | cola={datos['cola']} | "
                f"cruzaron={datos['cruzaron']} | espera_prom={datos['espera_prom']}s"
            )
    
