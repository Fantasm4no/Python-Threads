import tkinter as tk
from tkinter import ttk
from typing import Any, Dict
from pathlib import Path
import random

from ..concurrency.base import BaseSimulation
from ..concurrency.threads_impl import ThreadsSimulation
from ..concurrency.processes_impl import ProcessesSimulation

try:
    from PIL import Image, ImageTk  # type: ignore
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    Image = ImageTk = None  # type: ignore


CANVAS_W = 900
CANVAS_H = 630

CENTER_X = CANVAS_W // 2
CENTER_Y = CANVAS_H // 2
LANE_HALF = 40
SEM_DISTANCE = 110

DIRS = ["N", "S", "E", "O"]

# Colores bien visibles sobre mapa
CAR_COLORS = [
    "#ff1744", "#f50057", "#d500f9", "#651fff", "#2979ff",
    "#00b0ff", "#00e5ff", "#1de9b6", "#00e676", "#76ff03",
    "#ffea00", "#ffc400", "#ff9100", "#ff3d00",
]


def _darken(hex_color: str, factor: float = 0.55) -> str:
    """Oscurece #RRGGBB para representar carros esperando (rojo/amarillo)."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


class TrafficGUI:
    def __init__(self, mode: str, cycles: int, system_info: Dict[str, Any]):
        self.system_info = system_info
        self.mode = mode
        self.cycles_target = cycles
        self.sim: BaseSimulation | None = None
        self._resetting = False

        self.root = tk.Tk()
        self.root.title("Simulación de Tráfico - Intersección (N,S,E,O)")
        self.root.geometry(f"{CANVAS_W + 120}x{CANVAS_H + 260}")

        self._bg_photo = None
        self._bg_id = None

        self._lights: Dict[str, Dict[str, int]] = {}
        self._glow: Dict[str, Dict[str, int]] = {}
        self._dir_label: Dict[str, int] = {}

        # carros en cola (reutilizables)
        self._cars: Dict[str, list[int]] = {d: [] for d in DIRS}
        self._max_cars_draw = 12

        # memoria de “carros” por color para que el mismo carro cruce
        self._queue_colors: Dict[str, list[str]] = {d: [] for d in DIRS}
        self._prev_cola: Dict[str, int] = {d: 0 for d in DIRS}
        self._prev_cruzaron: Dict[str, int] = {d: 0 for d in DIRS}

        self._build_ui()
        self._init_scene()
        self._start_new_simulation(self.mode)
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

        self.canvas = tk.Canvas(
            self.root,
            width=CANVAS_W,
            height=CANVAS_H,
            bg="white",
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)

        self._load_background()

        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(fill="x")

        metrics_row = ttk.Frame(bottom)
        metrics_row.pack(fill="x")

        self.lbl_cycle = ttk.Label(metrics_row, text="Ciclo: 0 | Fase: 0")
        self.lbl_cycle.pack(anchor="w", side="left")

        self.lbl_mode = ttk.Label(metrics_row, text="", justify="right")
        self.lbl_mode.pack(anchor="e", side="right")

        self.lbl_stats = ttk.Label(bottom, text="", justify="left")
        self.lbl_stats.pack(anchor="w", pady=(6, 0))

        self.btn_reset = ttk.Button(bottom, text="Reiniciar / Cambiar modo", command=self._reset_simulation)
        self.btn_reset.pack(anchor="e", pady=(6, 0))

    # ---------- Gestión de simulación ----------

    def _create_simulation(self, mode: str) -> BaseSimulation:
        selected = (mode or "threads").lower()
        if selected == "processes":
            return ProcessesSimulation(cycles=self.cycles_target)
        return ThreadsSimulation(cycles=self.cycles_target)

    def _start_new_simulation(self, mode: str) -> None:
        self.mode = (mode or "threads").lower()

        if self.sim is not None:
            try:
                self.sim.stop()
            except Exception:
                pass

        self.sim = None
        self._clear_dynamic_state()

        self.sim = self._create_simulation(self.mode)
        self.sim.start()
        self.lbl_mode.config(text=f"Modo: {self.mode.upper()} | Ciclos objetivo: {self.cycles_target}")

    def _clear_dynamic_state(self) -> None:
        # Limpiar colas y animaciones
        self.canvas.delete("moving")
        for d in DIRS:
            self._queue_colors[d].clear()
            self._prev_cola[d] = 0
            self._prev_cruzaron[d] = 0
            for car_id in self._cars[d]:
                self.canvas.itemconfig(car_id, state="hidden")

        self.lbl_cycle.config(text="Ciclo: 0 | Fase: 0")
        self.lbl_stats.config(text="")

    def _reset_simulation(self) -> None:
        new_mode = self._ask_mode(initial=self.mode)
        if not new_mode:
            return

        self._resetting = True
        try:
            if self.sim is not None:
                try:
                    self.sim.stop()
                except Exception:
                    pass
            self.sim = None
            self._start_new_simulation(new_mode)
        finally:
            self._resetting = False

    def _ask_mode(self, initial: str) -> str | None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Seleccionar modo")
        dialog.transient(self.root)
        dialog.grab_set()

        w, h = 300, 150
        self.root.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        x = max(rx + (rw - w) // 2, 0)
        y = max(ry + (rh - h) // 2, 0)
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        selected = tk.StringVar(value="")

        current_txt = f" (Actual: {initial.upper()})" if initial else ""
        ttk.Label(dialog, text=f"Seleccione el modo de ejecución{current_txt}:", font=("Arial", 10)).pack(pady=15)

        def choose(mode_value: str) -> None:
            selected.set(mode_value)
            dialog.destroy()

        ttk.Button(dialog, text="1. Hilos (Threading)", command=lambda: choose("threads")).pack(fill="x", padx=20, pady=5)
        ttk.Button(dialog, text="2. Procesos (Multiprocessing)", command=lambda: choose("processes")).pack(fill="x", padx=20, pady=5)

        def on_close() -> None:
            selected.set("")
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)
        dialog.wait_window()

        result = selected.get().strip()
        return result or None

    # ---------- Escena estática ----------

    def _init_scene(self):
        c = self.canvas

        # Fondo
        if self._bg_photo is not None:
            self._bg_id = c.create_image(0, 0, image=self._bg_photo, anchor="nw", tags=("bg",))
        else:
            c.create_rectangle(0, 0, CANVAS_W, CANVAS_H, fill="white", outline="", tags=("bg",))

        # Overlay vías
        c.create_rectangle(
            CENTER_X - LANE_HALF, 0, CENTER_X + LANE_HALF, CANVAS_H,
            fill="#bbbbbb", outline="", stipple="gray25", tags=("static",)
        )
        c.create_rectangle(
            0, CENTER_Y - LANE_HALF, CANVAS_W, CENTER_Y + LANE_HALF,
            fill="#bbbbbb", outline="", stipple="gray25", tags=("static",)
        )

        # Centro cruce
        c.create_rectangle(
            CENTER_X - LANE_HALF, CENTER_Y - LANE_HALF,
            CENTER_X + LANE_HALF, CENTER_Y + LANE_HALF,
            outline="#222", width=2, tags=("static",)
        )

        # Líneas discontinuas
        for y in range(0, CANVAS_H, 26):
            c.create_line(CENTER_X, y, CENTER_X, min(y + 12, CANVAS_H), fill="white", width=2, tags=("static",))
        for x in range(0, CANVAS_W, 26):
            c.create_line(x, CENTER_Y, min(x + 12, CANVAS_W), CENTER_Y, fill="white", width=2, tags=("static",))

        self._draw_crosswalks()

        pos = {
            "N": (CENTER_X, CENTER_Y - SEM_DISTANCE),
            "S": (CENTER_X, CENTER_Y + SEM_DISTANCE),
            "E": (CENTER_X + SEM_DISTANCE, CENTER_Y),
            "O": (CENTER_X - SEM_DISTANCE, CENTER_Y),
        }

        # Semáforos + letra
        for d, (x, y) in pos.items():
            vertical = d in ["N", "S"]
            self._lights[d], self._glow[d] = self._create_traffic_light(x, y, vertical=vertical)
            self._dir_label[d] = self._text_with_plate(x, y - 54, d, font=("Arial", 12, "bold"))

        # Carros reutilizables (más visibles: borde blanco)
        for d in DIRS:
            for _ in range(self._max_cars_draw):
                car = c.create_rectangle(0, 0, 0, 0, fill="#2979ff", outline="white", width=2, tags=("cars",))
                c.itemconfig(car, state="hidden")
                self._cars[d].append(car)

        c.tag_raise("cars")

    def _draw_crosswalks(self):
        c = self.canvas
        for i in range(8):
            x0 = CENTER_X - LANE_HALF + 6 + i * 9
            c.create_rectangle(x0, CENTER_Y - LANE_HALF - 10, x0 + 6, CENTER_Y - LANE_HALF,
                               fill="white", outline="", tags=("static",))
        for i in range(8):
            x0 = CENTER_X - LANE_HALF + 6 + i * 9
            c.create_rectangle(x0, CENTER_Y + LANE_HALF, x0 + 6, CENTER_Y + LANE_HALF + 10,
                               fill="white", outline="", tags=("static",))
        for i in range(8):
            y0 = CENTER_Y - LANE_HALF + 6 + i * 9
            c.create_rectangle(CENTER_X - LANE_HALF - 10, y0, CENTER_X - LANE_HALF, y0 + 6,
                               fill="white", outline="", tags=("static",))
        for i in range(8):
            y0 = CENTER_Y - LANE_HALF + 6 + i * 9
            c.create_rectangle(CENTER_X + LANE_HALF, y0, CENTER_X + LANE_HALF + 10, y0 + 6,
                               fill="white", outline="", tags=("static",))

    # ---------- Semáforo ----------

    def _create_traffic_light(self, x: int, y: int, vertical: bool = True):
        c = self.canvas

        # poste
        if vertical:
            c.create_line(x, y + 28, x, y + 55, fill="#111", width=3, tags=("static",))
        else:
            c.create_line(x - 55, y, x - 28, y, fill="#111", width=3, tags=("static",))

        if vertical:
            c.create_rectangle(x - 14, y - 28, x + 14, y + 28,
                               fill="#1f1f1f", outline="#0f0f0f", width=2, tags=("static",))

            glow_r = c.create_oval(x - 10, y - 24, x + 10, y - 4, outline="", width=1, tags=("dynamic",))
            glow_y = c.create_oval(x - 10, y - 10, x + 10, y + 10, outline="", width=1, tags=("dynamic",))
            glow_g = c.create_oval(x - 10, y + 4,  x + 10, y + 24, outline="", width=1, tags=("dynamic",))

            r = c.create_oval(x - 8, y - 22, x + 8, y - 6, fill="#2b0000", outline="", tags=("dynamic",))
            yy = c.create_oval(x - 8, y - 8,  x + 8, y + 8,  fill="#2b2200", outline="", tags=("dynamic",))
            g = c.create_oval(x - 8, y + 6,  x + 8, y + 22, fill="#003300", outline="", tags=("dynamic",))
        else:
            c.create_rectangle(x - 28, y - 14, x + 28, y + 14,
                               fill="#1f1f1f", outline="#0f0f0f", width=2, tags=("static",))

            glow_r = c.create_oval(x - 24, y - 10, x - 4,  y + 10, outline="", width=1, tags=("dynamic",))
            glow_y = c.create_oval(x - 10, y - 10, x + 10, y + 10, outline="", width=1, tags=("dynamic",))
            glow_g = c.create_oval(x + 4,  y - 10, x + 24, y + 10, outline="", width=1, tags=("dynamic",))

            r = c.create_oval(x - 22, y - 8, x - 6, y + 8, fill="#2b0000", outline="", tags=("dynamic",))
            yy = c.create_oval(x - 8,  y - 8, x + 8, y + 8,  fill="#2b2200", outline="", tags=("dynamic",))
            g = c.create_oval(x + 6,  y - 8, x + 22, y + 8, fill="#003300", outline="", tags=("dynamic",))

        return {"R": r, "Y": yy, "G": g}, {"R": glow_r, "Y": glow_y, "G": glow_g}

    def _text_with_plate(self, x: int, y: int, text: str, font=("Arial", 10, "normal")) -> int:
        c = self.canvas
        c.create_rectangle(x - 38, y - 12, x + 38, y + 12,
                           fill="white", outline="#cccccc", stipple="gray25", tags=("hud",))
        label = c.create_text(x, y, text=text, font=font, fill="#111", tags=("hud",))
        return label

    # ---------- Update por tick ----------

    def _tick_ui(self):
        if self.sim is None or self._resetting:
            self.root.after(150, self._tick_ui)
            return

        try:
            snap = self.sim.get_snapshot()
        except Exception:
            self.root.after(150, self._tick_ui)
            return

        self.lbl_cycle.config(text=f"Ciclo: {snap['cycle']} | Fase: {snap['phase']}")

        sems = snap["semaforos"]
        stats_lines = []
        for d in DIRS:
            s = sems[d]
            stats_lines.append(
                f"{d}: estado={s['estado']} | cola={s['cola']} | cruzaron={s['cruzaron']} | espera_prom={s['espera_prom']}s"
            )
        self.lbl_stats.config(text="\n".join(stats_lines))

        self._update_scene(snap)
        self.root.after(150, self._tick_ui)

    def _update_scene(self, snap: Dict[str, Any]):
        sems = snap["semaforos"]

        pos = {
            "N": (CENTER_X, CENTER_Y - SEM_DISTANCE),
            "S": (CENTER_X, CENTER_Y + SEM_DISTANCE),
            "E": (CENTER_X + SEM_DISTANCE, CENTER_Y),
            "O": (CENTER_X - SEM_DISTANCE, CENTER_Y),
        }

        for d, (x, y) in pos.items():
            estado = str(sems[d]["estado"])
            cola = int(sems[d]["cola"])
            cruzaron = int(sems[d]["cruzaron"])

            # 1) Semáforo
            self._set_light(d, estado)

            # 2) Inferimos llegadas y salidas:
            prev_cola = self._prev_cola[d]
            prev_cruz = self._prev_cruzaron[d]

            departures = max(0, cruzaron - prev_cruz)  # cuantos cruzaron desde último tick
            # cola = prev_cola + arrivals - departures  => arrivals = cola - prev_cola + departures
            arrivals = max(0, (cola - prev_cola) + departures)

            # 3) Llegadas: agrega colores al final
            for _ in range(arrivals):
                self._queue_colors[d].append(random.choice(CAR_COLORS))

            # 4) Salidas: saca del frente y anima ESE MISMO color cruzando
            if departures > 0:
                for _ in range(min(departures, 3)):  # limita animaciones por tick
                    if self._queue_colors[d]:
                        color = self._queue_colors[d].pop(0)
                    else:
                        color = random.choice(CAR_COLORS)
                    self._spawn_crossing_car(d, color)

                # Si cruzaron muchos de golpe, igual “consumimos” colores para que la cola coincida
                for _ in range(departures - min(departures, 3)):
                    if self._queue_colors[d]:
                        self._queue_colors[d].pop(0)

            # 5) Reconciliar por seguridad (si hay desajustes raros)
            if len(self._queue_colors[d]) > cola:
                self._queue_colors[d] = self._queue_colors[d][:cola]
            while len(self._queue_colors[d]) < cola:
                self._queue_colors[d].append(random.choice(CAR_COLORS))

            # 6) Dibujar colas con colores
            self._draw_queue_cars(d, x, y, cola, estado)

            # guardar prev
            self._prev_cola[d] = cola
            self._prev_cruzaron[d] = cruzaron

        self.canvas.tag_raise("cars")
        self.canvas.tag_raise("moving")

    def _set_light(self, d: str, estado: str):
        c = self.canvas

        # apagado base (oscuro)
        c.itemconfig(self._lights[d]["R"], fill="#2b0000")
        c.itemconfig(self._lights[d]["Y"], fill="#2b2200")
        c.itemconfig(self._lights[d]["G"], fill="#003300")

        # apaga glows
        c.itemconfig(self._glow[d]["R"], outline="")
        c.itemconfig(self._glow[d]["Y"], outline="")
        c.itemconfig(self._glow[d]["G"], outline="")

        if estado == "ROJO":
            c.itemconfig(self._lights[d]["R"], fill="#ff2b2b")
            c.itemconfig(self._glow[d]["R"], outline="white")
        elif estado == "AMARILLO":
            c.itemconfig(self._lights[d]["Y"], fill="#ffd400")
            c.itemconfig(self._glow[d]["Y"], outline="white")
        elif estado == "VERDE":
            c.itemconfig(self._lights[d]["G"], fill="#00ff3b")
            c.itemconfig(self._glow[d]["G"], outline="white")

    def _draw_queue_cars(self, d: str, x: int, y: int, cola: int, estado: str):
        c = self.canvas
        cars = self._cars[d]
        colors = self._queue_colors[d]

        show = min(cola, self._max_cars_draw)
        dark = (estado != "VERDE")  # si no está verde, se ven “apagados”

        # más grandes para que se noten
        if d == "N":
            base_x = x - 26
            base_y = y - 82
            dx, dy = 0, -18
            w, h = 10, 16
        elif d == "S":
            base_x = x + 26
            base_y = y + 82
            dx, dy = 0, 18
            w, h = 10, 16
        elif d == "E":
            base_x = x + 82
            base_y = y - 26
            dx, dy = 18, 0
            w, h = 16, 10
        else:  # O
            base_x = x - 82
            base_y = y + 26
            dx, dy = -18, 0
            w, h = 16, 10

        for i in range(show):
            cx = base_x + i * dx
            cy = base_y + i * dy
            c.coords(cars[i], cx - w, cy - h, cx + w, cy + h)

            base = colors[i] if i < len(colors) else random.choice(CAR_COLORS)
            fill = _darken(base) if dark else base
            c.itemconfig(cars[i], state="normal", fill=fill, outline="white", width=2)

        for i in range(show, len(cars)):
            c.itemconfig(cars[i], state="hidden")

    # ---------- Animación de cruce (el mismo color que salió de la cola) ----------

    def _spawn_crossing_car(self, d: str, color: str):
        c = self.canvas

        if d == "N":
            x = CENTER_X - 26
            y0 = CENTER_Y - LANE_HALF - 75
            y1 = CENTER_Y + LANE_HALF + 75
            w, h = 10, 16
            car_id = c.create_rectangle(x - w, y0 - h, x + w, y0 + h,
                                        fill=color, outline="white", width=2, tags=("moving", "cars"))
            self._animate_move(car_id, dx=0, dy=(y1 - y0) / 25, steps=25, delay=18)

        elif d == "S":
            x = CENTER_X + 26
            y0 = CENTER_Y + LANE_HALF + 75
            y1 = CENTER_Y - LANE_HALF - 75
            w, h = 10, 16
            car_id = c.create_rectangle(x - w, y0 - h, x + w, y0 + h,
                                        fill=color, outline="white", width=2, tags=("moving", "cars"))
            self._animate_move(car_id, dx=0, dy=(y1 - y0) / 25, steps=25, delay=18)

        elif d == "E":
            y = CENTER_Y - 26
            x0 = CENTER_X + LANE_HALF + 75
            x1 = CENTER_X - LANE_HALF - 75
            w, h = 16, 10
            car_id = c.create_rectangle(x0 - w, y - h, x0 + w, y + h,
                                        fill=color, outline="white", width=2, tags=("moving", "cars"))
            self._animate_move(car_id, dx=(x1 - x0) / 25, dy=0, steps=25, delay=18)

        else:  # O
            y = CENTER_Y + 26
            x0 = CENTER_X - LANE_HALF - 75
            x1 = CENTER_X + LANE_HALF + 75
            w, h = 16, 10
            car_id = c.create_rectangle(x0 - w, y - h, x0 + w, y + h,
                                        fill=color, outline="white", width=2, tags=("moving", "cars"))
            self._animate_move(car_id, dx=(x1 - x0) / 25, dy=0, steps=25, delay=18)

    def _animate_move(self, item_id: int, dx: float, dy: float, steps: int, delay: int):
        c = self.canvas

        def step(k: int):
            if k <= 0:
                try:
                    c.delete(item_id)
                except Exception:
                    pass
                return
            try:
                c.move(item_id, dx, dy)
            except Exception:
                return
            self.root.after(delay, lambda: step(k - 1))

        step(steps)

    # ---------- Close ----------

    def _on_close(self):
        if self.sim is not None:
            try:
                self.sim.stop()
            except Exception:
                pass
            finally:
                self.sim = None
        self.root.destroy()

    def run(self):
        self.root.mainloop()

    def _load_background(self) -> None:
        if not _PIL_AVAILABLE:
            return

        base_path = Path(__file__).resolve().parents[2]
        for candidate in ("fondo2.jpeg", "fondo.jpeg"):
            img_path = base_path / candidate
            if not img_path.exists():
                continue
            try:
                with Image.open(img_path) as img:  # type: ignore[arg-type]
                    resampling = getattr(Image, "Resampling", Image)
                    resized = img.resize((CANVAS_W, CANVAS_H), resampling.LANCZOS)  # type: ignore[attr-defined]
                    self._bg_photo = ImageTk.PhotoImage(resized)  # type: ignore[arg-type]
                    return
            except Exception:
                self._bg_photo = None
                return
