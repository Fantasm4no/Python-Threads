import tkinter as tk
from tkinter import ttk
from typing import Any, Dict

class TrafficGUI:
    def __init__(self, simulation, system_info: Dict[str, Any]):
        self.sim = simulation
        self.system_info = system_info

        self.root = tk.Tk()
        self.root.title("Simulación de Tráfico - Intersección (N,S,E,O)")

        self._build_ui()
        self.sim.start()
        self._tick_ui()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        info_txt = (
            f"Python: {self.system_info['python_version']}\n"
            f"OS: {self.system_info['os']} | CPU cores: {self.system_info['cpu_count']}\n"
            f"Ejecutable: {self.system_info['executable']}"
        )
        ttk.Label(top, text=info_txt, justify="left").pack(anchor="w")

        self.canvas = tk.Canvas(self.root, width=600, height=420, bg="white")
        self.canvas.pack(padx=10, pady=10)

        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(fill="x")

        self.lbl_cycle = ttk.Label(bottom, text="Ciclo: 0")
        self.lbl_cycle.pack(anchor="w")

        self.lbl_stats = ttk.Label(bottom, text="", justify="left")
        self.lbl_stats.pack(anchor="w")

    def _draw_intersection(self, snap: Dict[str, Any]):
        c = self.canvas
        c.delete("all")

        # Dibujar vías
        c.create_rectangle(260, 0, 340, 420, fill="#f0f0f0", outline="")
        c.create_rectangle(0, 170, 600, 250, fill="#f0f0f0", outline="")

        sems = snap["semaforos"]

        # posiciones semáforos
        pos = {
            "N": (300, 130),
            "S": (300, 290),
            "E": (370, 210),
            "O": (230, 210),
        }

        def color(estado: str) -> str:
            return {"VERDE": "green", "AMARILLO": "yellow", "ROJO": "red"}.get(estado, "gray")

        for d, (x, y) in pos.items():
            estado = sems[d]["estado"]
            cola = sems[d]["cola"]

            # Semáforo
            c.create_oval(x-15, y-15, x+15, y+15, fill=color(estado), outline="black")
            c.create_text(x, y-28, text=f"{d}", font=("Arial", 12, "bold"))
            c.create_text(x, y+28, text=f"cola: {cola}")

            # Vehículos como rectángulos en fila
            for i in range(min(cola, 8)):
                if d == "N":
                    c.create_rectangle(x-6, y-35-(i*12), x+6, y-25-(i*12), fill="blue")
                elif d == "S":
                    c.create_rectangle(x-6, y+25+(i*12), x+6, y+35+(i*12), fill="blue")
                elif d == "E":
                    c.create_rectangle(x+25+(i*12), y-6, x+35+(i*12), y+6, fill="blue")
                elif d == "O":
                    c.create_rectangle(x-35-(i*12), y-6, x-25-(i*12), y+6, fill="blue")

        # Centro
        c.create_rectangle(260, 170, 340, 250, outline="black", width=2)

    def _tick_ui(self):
        snap = self.sim.get_snapshot()

        self.lbl_cycle.config(text=f"Ciclo: {snap['cycle']}  | Fase: {snap['phase']}")

        sems = snap["semaforos"]
        stats_lines = []
        for d in ["N","S","E","O"]:
            s = sems[d]
            stats_lines.append(
                f"{d}: estado={s['estado']} | cola={s['cola']} | cruzaron={s['cruzaron']} | espera_prom={s['espera_prom']}s"
            )
        self.lbl_stats.config(text="\n".join(stats_lines))

        self._draw_intersection(snap)

        # refresco
        self.root.after(150, self._tick_ui)

    def _on_close(self):
        self.sim.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
