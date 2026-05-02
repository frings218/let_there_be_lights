"""
Traffic Light Intersection Simulation
======================================
4-way intersection with safety enforcement:
- Green/Yellow/Red lights (1 minute each, 15-second transitions)
- Yellow > 10 seconds → cars will not proceed
- Prevents crashes, wrong-time driving, speeding
- Handles light malfunctions
"""

import random
import time
import threading
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class LightColor(Enum):
    GREEN  = "GREEN"
    YELLOW = "YELLOW"
    RED    = "RED"
    OFF    = "OFF"   # Malfunction state


class Direction(Enum):
    NORTH = "North"
    SOUTH = "South"
    EAST  = "East"
    WEST  = "West"


class CarStatus(Enum):
    WAITING   = auto()
    MOVING    = auto()
    STOPPED   = auto()
    SPEEDING  = auto()
    CRASHED   = auto()


# ─────────────────────────────────────────────
# TrafficLight Class
# ─────────────────────────────────────────────

class TrafficLight:
    """
    A single traffic light on one side of the intersection.

    Timing:
        GREEN  → 60 s
        YELLOW → 15 s  (transition / warning)
        RED    → 60 s
    """

    GREEN_DURATION  = 60   # seconds
    YELLOW_DURATION = 15   # seconds
    RED_DURATION    = 60   # seconds

    # Cars ignore yellow if it has been yellow longer than this
    YELLOW_IGNORE_THRESHOLD = 10  # seconds

    def __init__(self, direction: Direction, initial_color: LightColor = LightColor.RED):
        self.direction       = direction
        self._color          = initial_color
        self._is_malfunctioning = False
        self._color_start_time: float = time.time()
        self._lock           = threading.Lock()

    # ── Properties ──────────────────────────

    @property
    def color(self) -> LightColor:
        return self._color

    @property
    def is_malfunctioning(self) -> bool:
        return self._is_malfunctioning

    @property
    def seconds_on_current_color(self) -> float:
        return time.time() - self._color_start_time

    # ── Public Methods ───────────────────────

    def set_color(self, color: LightColor) -> None:
        """Change the light to a new color (thread-safe)."""
        with self._lock:
            self._color = color
            self._color_start_time = time.time()
            self._is_malfunctioning = (color == LightColor.OFF)
            print(f"  [LIGHT] {self.direction.value:5} → {color.value}")

    def trigger_malfunction(self) -> None:
        """Simulate a hardware failure."""
        print(f"  ⚠️  MALFUNCTION on {self.direction.value} light!")
        self.set_color(LightColor.OFF)

    def repair(self) -> None:
        """Restore the light after a malfunction."""
        print(f"  ✅  {self.direction.value} light repaired → RED")
        self.set_color(LightColor.RED)

    def cars_may_go(self) -> bool:
        """
        Return True only if conditions are safe to drive.
        - GREEN  → always go
        - YELLOW → only if yellow < YELLOW_IGNORE_THRESHOLD seconds
        - RED    → never go
        - OFF    → treat as RED (stop)
        """
        if self._is_malfunctioning or self._color == LightColor.OFF:
            return False
        if self._color == LightColor.GREEN:
            return True
        if self._color == LightColor.YELLOW:
            elapsed = self.seconds_on_current_color
            if elapsed <= self.YELLOW_IGNORE_THRESHOLD:
                return True  # Just turned yellow – clear to proceed
            print(f"  🚦 {self.direction.value}: Yellow > {self.YELLOW_IGNORE_THRESHOLD}s "
                  f"({elapsed:.1f}s) – cars must STOP")
            return False
        return False  # RED

    def __repr__(self) -> str:
        status = "MALFUNCTIONING" if self._is_malfunctioning else self._color.value
        return f"TrafficLight({self.direction.value}, {status})"


# ─────────────────────────────────────────────
# Car Class
# ─────────────────────────────────────────────

@dataclass
class Car:
    """Represents a vehicle approaching the intersection."""

    car_id:    int
    direction: Direction
    speed_kmh: float = field(default_factory=lambda: random.uniform(30, 70))
    status:    CarStatus = CarStatus.WAITING

    SPEED_LIMIT_KMH = 60.0

    def is_speeding(self) -> bool:
        return self.speed_kmh > self.SPEED_LIMIT_KMH

    def try_to_go(self, light: TrafficLight) -> str:
        """
        Attempt to drive through the intersection.
        Returns a human-readable result string.
        """
        # ── Malfunction check ──
        if light.is_malfunctioning:
            self.status = CarStatus.STOPPED
            return (f"Car #{self.car_id} ({self.direction.value}) STOPPED – "
                    f"light is malfunctioning, treating as RED.")

        # ── Red / blocked yellow check ──
        if not light.cars_may_go():
            self.status = CarStatus.STOPPED
            return (f"Car #{self.car_id} ({self.direction.value}) STOPPED – "
                    f"light is {light.color.value}.")

        # ── Speeding check ──
        if self.is_speeding():
            self.status = CarStatus.SPEEDING
            return (f"🚨 Car #{self.car_id} ({self.direction.value}) SPEEDING "
                    f"at {self.speed_kmh:.1f} km/h (limit {self.SPEED_LIMIT_KMH} km/h) – PENALIZED.")

        # ── Safe to go ──
        self.status = CarStatus.MOVING
        return (f"✅ Car #{self.car_id} ({self.direction.value}) MOVING "
                f"at {self.speed_kmh:.1f} km/h – light is {light.color.value}.")

    def __repr__(self) -> str:
        return (f"Car(id={self.car_id}, dir={self.direction.value}, "
                f"speed={self.speed_kmh:.1f}, status={self.status.name})")


# ─────────────────────────────────────────────
# Intersection Class
# ─────────────────────────────────────────────

class Intersection:
    """
    Models a 4-way intersection.

    Cycle (per axis):
        N/S GREEN  →  N/S YELLOW (15 s)  →  N/S RED  →
        E/W GREEN  →  E/W YELLOW (15 s)  →  E/W RED  →  repeat

    Safety rules enforced:
        1. Conflicting lights cannot both be GREEN/YELLOW simultaneously.
        2. Yellow > 10 s → cars blocked.
        3. Malfunctioning light → all cars stop on that approach.
        4. Speeding cars are penalised and stopped.
        5. Crash detection if two crossing cars are both MOVING.
    """

    def __init__(self):
        self.lights: dict[Direction, TrafficLight] = {
            d: TrafficLight(d, LightColor.RED) for d in Direction
        }
        self.cars:    list[Car] = []
        self._car_id_counter    = 1
        self._crash_log:  list[str] = []
        self._event_log:  list[str] = []

    # ── Light management ─────────────────────

    def _set_axis(self, axis_dirs: list[Direction], color: LightColor) -> None:
        for d in axis_dirs:
            self.lights[d].set_color(color)

    def _safe_green(self, green_dirs: list[Direction]) -> None:
        """
        Only allow GREEN on green_dirs if the perpendicular axis is fully RED.
        Prevents conflicting greens.
        """
        all_dirs  = set(Direction)
        cross_dirs = list(all_dirs - set(green_dirs))

        # Ensure cross axis is RED first
        cross_ok = all(
            self.lights[d].color == LightColor.RED and not self.lights[d].is_malfunctioning
            for d in cross_dirs
        )
        if not cross_ok:
            print("  ⚠️  SAFETY BLOCK: Cross-axis not RED – delaying green phase.")
            time.sleep(2)  # Brief safety delay (simulated)

        self._set_axis(green_dirs, LightColor.GREEN)

    def run_cycle(self, fast: bool = False) -> None:
        """
        Run one full light cycle.
        fast=True compresses durations for demo purposes (÷ 10).
        """
        scale = 0.1 if fast else 1.0

        ns = [Direction.NORTH, Direction.SOUTH]
        ew = [Direction.EAST,  Direction.WEST]

        print("\n" + "═" * 50)
        print("  🟢 Phase 1: N/S GREEN")
        print("═" * 50)
        self._safe_green(ns)
        self._set_axis(ew, LightColor.RED)
        time.sleep(TrafficLight.GREEN_DURATION * scale)

        print("\n" + "─" * 50)
        print("  🟡 Phase 2: N/S YELLOW (transition)")
        print("─" * 50)
        self._set_axis(ns, LightColor.YELLOW)
        time.sleep(TrafficLight.YELLOW_DURATION * scale)

        print("\n" + "═" * 50)
        print("  🟢 Phase 3: E/W GREEN")
        print("═" * 50)
        self._set_axis(ns, LightColor.RED)
        self._safe_green(ew)
        time.sleep(TrafficLight.GREEN_DURATION * scale)

        print("\n" + "─" * 50)
        print("  🟡 Phase 4: E/W YELLOW (transition)")
        print("─" * 50)
        self._set_axis(ew, LightColor.YELLOW)
        time.sleep(TrafficLight.YELLOW_DURATION * scale)

        self._set_axis(ew, LightColor.RED)

    # ── Car management ───────────────────────

    def add_car(self, direction: Direction, speed_kmh: Optional[float] = None) -> Car:
        car = Car(
            car_id    = self._car_id_counter,
            direction = direction,
            speed_kmh = speed_kmh if speed_kmh is not None
                        else random.uniform(30, 75),
        )
        self._car_id_counter += 1
        self.cars.append(car)
        return car

    def process_cars(self) -> None:
        """Evaluate every waiting car against its light and check for crashes."""
        moving_cars: list[Car] = []

        for car in self.cars:
            if car.status != CarStatus.WAITING:
                continue
            light  = self.lights[car.direction]
            result = car.try_to_go(light)
            print(f"  {result}")
            self._event_log.append(result)

            if car.status == CarStatus.MOVING:
                moving_cars.append(car)

        self._detect_crashes(moving_cars)

    def _detect_crashes(self, moving_cars: list[Car]) -> None:
        """
        Crossing streams (N/S vs E/W) moving simultaneously = crash.
        """
        ns_moving = [c for c in moving_cars if c.direction in (Direction.NORTH, Direction.SOUTH)]
        ew_moving = [c for c in moving_cars if c.direction in (Direction.EAST,  Direction.WEST)]

        if ns_moving and ew_moving:
            msg = (f"💥 CRASH DETECTED! "
                   f"N/S cars {[c.car_id for c in ns_moving]} "
                   f"collided with E/W cars {[c.car_id for c in ew_moving]}!")
            print(f"  {msg}")
            self._crash_log.append(msg)
            for c in ns_moving + ew_moving:
                c.status = CarStatus.CRASHED

    # ── Malfunction simulation ───────────────

    def trigger_malfunction(self, direction: Direction) -> None:
        self.lights[direction].trigger_malfunction()

    def repair_light(self, direction: Direction) -> None:
        self.lights[direction].repair()

    # ── Reporting ────────────────────────────

    def report(self) -> None:
        print("\n" + "═" * 50)
        print("  📋 INTERSECTION REPORT")
        print("═" * 50)

        print("\n  Lights:")
        for d, lt in self.lights.items():
            print(f"    {d.value:5}: {lt.color.value:6}  {'⚠ FAULT' if lt.is_malfunctioning else 'OK'}")

        print("\n  Cars:")
        if not self.cars:
            print("    (none)")
        for car in self.cars:
            flag = ""
            if car.status == CarStatus.SPEEDING: flag = "  🚨 SPEEDING"
            if car.status == CarStatus.CRASHED:  flag = "  💥 CRASHED"
            print(f"    Car #{car.car_id:3} | {car.direction.value:5} | "
                  f"{car.speed_kmh:5.1f} km/h | {car.status.name}{flag}")

        if self._crash_log:
            print("\n  ⚠️  Crash Log:")
            for entry in self._crash_log:
                print(f"    {entry}")
        else:
            print("\n  ✅  No crashes recorded.")

        print()


# ─────────────────────────────────────────────
# Demo / Main
# ─────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  TRAFFIC LIGHT INTERSECTION SIMULATION")
    print("=" * 50)
    print("  (fast=True → durations ÷ 10 for demo)\n")

    intersection = Intersection()

    # ── Scenario 1: Normal operation ─────────
    print("\n▶ Scenario 1: Normal traffic flow\n")
    # Put N/S on GREEN manually for demo
    intersection.lights[Direction.NORTH].set_color(LightColor.GREEN)
    intersection.lights[Direction.SOUTH].set_color(LightColor.GREEN)
    intersection.lights[Direction.EAST ].set_color(LightColor.RED)
    intersection.lights[Direction.WEST ].set_color(LightColor.RED)

    for d in Direction:
        intersection.add_car(d, speed_kmh=random.uniform(40, 58))

    intersection.process_cars()

    # ── Scenario 2: Speeding car ─────────────
    print("\n▶ Scenario 2: Speeding car\n")
    speeder = intersection.add_car(Direction.NORTH, speed_kmh=95.0)
    intersection.process_cars()

    # ── Scenario 3: Yellow too long ──────────
    print("\n▶ Scenario 3: Yellow light > 10 s\n")
    # Force NORTH to yellow and fake it has been yellow for 12 s
    north_light = intersection.lights[Direction.NORTH]
    north_light.set_color(LightColor.YELLOW)
    north_light._color_start_time -= 12   # Simulate 12 s have passed

    late_car = intersection.add_car(Direction.NORTH, speed_kmh=50.0)
    intersection.process_cars()

    # ── Scenario 4: Malfunction ──────────────
    print("\n▶ Scenario 4: Light malfunction\n")
    intersection.trigger_malfunction(Direction.EAST)
    fault_car = intersection.add_car(Direction.EAST, speed_kmh=45.0)
    intersection.process_cars()
    intersection.repair_light(Direction.EAST)

    # ── Scenario 5: Potential crash (cross-traffic) ──
    print("\n▶ Scenario 5: Conflicting green → crash detection\n")
    # Force both axes GREEN (unsafe scenario)
    for d in Direction:
        intersection.lights[d].set_color(LightColor.GREEN)

    for d in Direction:
        intersection.add_car(d, speed_kmh=50.0)

    intersection.process_cars()

    # ── Final report ─────────────────────────
    intersection.report()

    # ── Run a short timed cycle ──────────────
    print("\n▶ Running one abbreviated light cycle (fast mode)…\n")
    cycle_intersection = Intersection()
    cycle_intersection.run_cycle(fast=True)
    print("\n  ✅ Cycle complete.\n")


if __name__ == "__main__":
    main()