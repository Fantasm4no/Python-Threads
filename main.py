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
    parser.add_argument("--mode", choices=["threads", "processes"], default=None,
                        help="Modo de concurrencia")
    parser.add_argument("--cycles", type=int, default=10, help="Número mínimo de ciclos")
    args = parser.parse_args()
    
    info = system_info()

    if args.mode is None:
        try:
            import tkinter as tk
            from tkinter import ttk
            
            def select_mode_gui():
                root = tk.Tk()
                root.title("Configurar Simulación")
                
                # Centrar ventana
                w, h = 300, 150
                ws = root.winfo_screenwidth()
                hs = root.winfo_screenheight()
                x = (ws/2) - (w/2)
                y = (hs/2) - (h/2)
                root.geometry('%dx%d+%d+%d' % (w, h, x, y))
                
                selected_mode = tk.StringVar(value=None)
                
                ttk.Label(root, text="Seleccione el modo de ejecución:", font=("Arial", 10)).pack(pady=15)
                
                def on_thread():
                    selected_mode.set("threads")
                    root.destroy()
                    
                def on_process():
                    selected_mode.set("processes")
                    root.destroy()
                
                ttk.Button(root, text="1. Hilos (Threading)", command=on_thread).pack(fill="x", padx=20, pady=5)
                ttk.Button(root, text="2. Procesos (Multiprocessing)", command=on_process).pack(fill="x", padx=20, pady=5)
                
                root.mainloop()
                return selected_mode.get()

            args.mode = select_mode_gui()
            if not args.mode or args.mode == "None":
                sys.exit(0)
                
        except ImportError:
            # Fallback a consola si no hay tk (raro en windows)
            print("Tkinter no disponible. Usando consola.")
            selection = input("Modo (1-Threads, 2-Processes): ")
            args.mode = "threads" if selection == "1" else "processes"

    print(f"\nIniciando simulación con modo: {args.mode.upper()}\n")

    if args.mode == "threads":
        sim = ThreadsSimulation(cycles=args.cycles)
    else:
        sim = ProcessesSimulation(cycles=args.cycles)
    
    gui = TrafficGUI(simulation=sim, system_info=info)
    gui.run()


if __name__ == "__main__":
    main()