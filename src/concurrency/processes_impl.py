import multiprocessing
import time
import random
from typing import Dict, Any

from ..config import GREEN_TIME, YELLOW_TIME, TICK, ARRIVAL_PROB
from ..models.semaforo import Semaforo
from ..models.vehiculo import Vehiculo
from ..models.controlador import ControladorTrafico
from .base import BaseSimulation

def worker_semaforo(direccion: str, 
                    shared_sem_dict: Any, 
                    lock: Any, 
                    running_event: Any, 
                    start_barrier: Any,
                    proc_idx: int) -> None:
    
    # Wait for all to be ready
    start_barrier.wait()
    
    local_veh_counter = 0
    base_id = proc_idx * 1_000_000
    
    while running_event.is_set():
        now = time.time()
        
        # Access shared state with Lock
        # We must acquire lock because we are updating the Semaforo object inside the dict
        with lock:
            # COPY: Get the object from shared dict (unpickled copy)
            sem_obj = shared_sem_dict[direccion]
            
            # 1. Arrival Logic
            if random.random() < ARRIVAL_PROB:
                local_veh_counter += 1
                v_id = base_id + local_veh_counter
                v = Vehiculo(v_id, direccion, now)
                sem_obj.enqueue(v)
            
            # 2. Crossing Logic
            # The controller (other process) updates 'sem_obj.estado' in the shared dict
            # We must use the state from the copy we just got.
            sem_obj.avanzar_uno(now)
            
            # WRITE BACK: Update the shared dict so others (GUI, Controller) see changes
            shared_sem_dict[direccion] = sem_obj
            
        time.sleep(TICK)

def worker_controlador(shared_sem_dict: Any, 
                       shared_ctrl_state: Any, 
                       lock: Any, 
                       running_event: Any, 
                       start_barrier: Any,
                       cycles_target: int) -> None:
    
    ctrl = ControladorTrafico()
    
    # Wait for start
    start_barrier.wait()
    
    # Initial phase application
    with lock:
        current_semas = {d: shared_sem_dict[d] for d in ["N", "S", "E", "O"]}
        ctrl.aplicar_fase(current_semas)
        for d, s in current_semas.items():
            shared_sem_dict[d] = s
        
        shared_ctrl_state['cycle'] = ctrl.ciclo
        shared_ctrl_state['phase'] = ctrl.fase_idx

    while running_event.is_set() and ctrl.ciclo < cycles_target:
        
        # GREEN PERIOD
        t0 = time.time()
        while running_event.is_set() and (time.time() - t0) < GREEN_TIME:
            time.sleep(TICK)
            
        # YELLOW PERIOD
        with lock:
            verdes, _ = ctrl.fase_actual()
            current_semas = {d: shared_sem_dict[d] for d in ["N", "S", "E", "O"]}
            for d in verdes:
                current_semas[d].estado = "AMARILLO"
                shared_sem_dict[d] = current_semas[d]
        
        t1 = time.time()
        while running_event.is_set() and (time.time() - t1) < YELLOW_TIME:
            time.sleep(TICK)
            
        # NEXT PHASE
        with lock:
            ctrl.siguiente_fase()
            
            current_semas = {d: shared_sem_dict[d] for d in ["N", "S", "E", "O"]}
            ctrl.aplicar_fase(current_semas)
            
            for d, s in current_semas.items():
                shared_sem_dict[d] = s
                
            shared_ctrl_state['cycle'] = ctrl.ciclo
            shared_ctrl_state['phase'] = ctrl.fase_idx

    # End of cycles
    running_event.clear()

class ProcessesSimulation(BaseSimulation):
    def __init__(self, cycles: int = 10):
        self.cycles_target = cycles
        self.manager = multiprocessing.Manager()
        
        # Shared State
        # Initial Semaforos
        initial_semas = {d: Semaforo(d) for d in ["N", "S", "E", "O"]}
        self.shared_sem_dict = self.manager.dict(initial_semas)
        
        # Shared Controller State (for GUI)
        self.shared_ctrl_state = self.manager.dict({
            "cycle": 0,
            "phase": 0
        })
        
        self.lock = self.manager.RLock() # RLock is safer
        self.running_event = self.manager.Event()
        self.running_event.set()
        
        # Barrier: 4 semaphores + 1 controller
        self.barrier = self.manager.Barrier(5)
        
        self.processes = []

    def start(self) -> None:
        self.running_event.set()
        
        # Start Semaphore Processes
        dirs = ["N", "S", "E", "O"]
        for i, d in enumerate(dirs):
            p = multiprocessing.Process(
                target=worker_semaforo,
                args=(d, self.shared_sem_dict, self.lock, self.running_event, self.barrier, i+1),
                name=f"Semaforo-{d}"
            )
            self.processes.append(p)
            p.start()
            
        # Start Controller Process
        p_ctrl = multiprocessing.Process(
            target=worker_controlador,
            args=(self.shared_sem_dict, self.shared_ctrl_state, self.lock, self.running_event, self.barrier, self.cycles_target),
            name="Controlador"
        )
        self.processes.append(p_ctrl)
        p_ctrl.start()

    def stop(self) -> None:
        self.running_event.clear()
        for p in self.processes:
            p.join()
        self.manager.shutdown()

    def get_snapshot(self) -> Dict[str, Any]:
        # The GUI calls this from the MainProcess
        # We access the shared managed dicts
        try:
            with self.lock:
                # We interpret the data
                semas_data = {}
                for d in ["N", "S", "E", "O"]:
                    s = self.shared_sem_dict[d] # copy
                    semas_data[d] = {
                        "estado": s.estado,
                        "cola": len(s.cola),
                        "cruzaron": s.cruzaron,
                        "espera_prom": round(s.espera_promedio(), 2),
                    }
                
                return {
                    "cycle": self.shared_ctrl_state["cycle"],
                    "phase": self.shared_ctrl_state["phase"],
                    "semaforos": semas_data
                }
        except Exception:
            # If manager is closed or error
            return {
                "cycle": 0, "phase": 0, 
                "semaforos": {d: {"estado": "OFF", "cola": 0, "cruzaron": 0, "espera_prom": 0} for d in "NSEO"}
            }
