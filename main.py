import argparse
import platform
import sys
import os

from src.config import DEFAULT_MODE
from src.ui.gui_tk import TrafficGUI
from src.concurrency.threads_impl import ThreadsSimulation
from src.concurrency.processes_impl import ProcessesSimulation

def system_info() -> dict:
    return {
        "python_version": sys.version.replace("\n", ""),
        "executable": sys.executable,
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
    }

def main():
    parser = argparse.ArgumentParser(description="Simulación de tráfico con hilos o procesos")
    parser.add_argument("--mode", choices=["threads", "processes"], default=DEFAULT_MODE,
                        help="Modo de concurrencia")
    parser.add_argument("--cycles", type=int, default=10, help="Número mínimo de ciclos")
    args = parser.parse_args()
    
    info = system_info()

    if args.mode == "threads":
        sim = ThreadsSimulation(cycles=args.cycles)
    else:
        sim = ProcessesSimulation(cycles=args.cycles)
    
    gui = TrafficGUI(simulation=sim, system_info=info)
    gui.run()


if __name__ == "__main__":
    main()