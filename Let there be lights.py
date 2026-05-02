"""
Traffic Light Intersection Simulation
--------------------------------------
4 stop lights arranged at N, E, S, W positions.
Cars travel COUNTER-CLOCKWISE: N -> W -> S -> E -> N
Each light cycle: Green (60s) -> Yellow (15s) -> Red (60s+)
Cars can only move one at a time and cannot crash.
"""

import time
import random
from enum import Enum
from collections import deque


# ─────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────

class LightColor(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class Direction(Enum):
    NORTH = "NORTH"
    WEST = "WEST"
    SOUTH = "SOUTH"
    EAST = "EAST"

    def next_counter_clockwise(self):
        """Return the next direction going counter-clockwise: N -> W -> S -> E -> N"""
        order = [Direction.NORTH, Direction.WEST, Direction.SOUTH, Direction.EAST]
        idx = order.index(self)
        return order[(idx + 1) % len(order)]


# ─────────────────────────────────────────────
#  Car
# ─────────────────────────────────────────────

class Car:
    """Represents a single car waiting at or passing through a light."""

    def __init__(self, car_id: str, start_direction: Direction):
        self.car_id = car_id
        self.start_direction = start_direction
        self.current_position: Direction = start_direction
        self.passed_through: list[tuple[Direction, float]] = []  # (direction, timestamp)

    def move(self, sim_time: float):
        """Move the car counter-clockwise to the next intersection."""
        self.passed_through.append((self.current_position, sim_time))
        self.current_position = self.current_position.next_counter_clockwise()
        print(f"  🚗  Car {self.car_id} passed through {self.passed_through[-1][0].value}"
              f" at t={sim_time:.1f}s  →  now heading to {self.current_position.value}")

    def history_str(self) -> str:
        lines = [f"Car {self.car_id} (started at {self.start_direction.value}):"]
        for direction, t in self.passed_through:
            lines.append(f"    passed {direction.value} at t={t:.1f}s")
        return "\n".join(lines)


# ─────────────────────────────────────────────
#  StopLight
# ─────────────────────────────────────────────

class StopLight:
    """
    A single traffic light at one of the four directions.

    Timing (seconds):
        GREEN  : 60
        YELLOW : 15
        RED    : 60  (padded to complete the full 135-second cycle)
    """

    GREEN_DURATION = 60
    YELLOW_DURATION = 15
    RED_DURATION = 60

    CYCLE = GREEN_DURATION + YELLOW_DURATION + RED_DURATION  # 135 s total

    def __init__(self, direction: Direction, phase_offset: float = 0.0):
        self.direction = direction
        self.phase_offset = phase_offset  # seconds into cycle this light starts GREEN
        self.queue: deque[Car] = deque()  # cars waiting here

    # ------------------------------------------------------------------
    def color_at(self, sim_time: float) -> LightColor:
        """Return the light color at a given simulation time."""
        t = (sim_time - self.phase_offset) % self.CYCLE
        if t < 0:
            t += self.CYCLE
        if t < self.GREEN_DURATION:
            return LightColor.GREEN
        if t < self.GREEN_DURATION + self.YELLOW_DURATION:
            return LightColor.YELLOW
        return LightColor.RED

    def is_go(self, sim_time: float) -> bool:
        """Cars may proceed only on GREEN."""
        return self.color_at(sim_time) == LightColor.GREEN

    def add_car(self, car: Car):
        self.queue.append(car)
        print(f"  🚦  Car {car.car_id} joined queue at {self.direction.value} light"
              f"  (queue length: {len(self.queue)})")

    def pop_next_car(self) -> Car | None:
        """Remove and return the first car in the queue, if any."""
        return self.queue.popleft() if self.queue else None

    def status(self, sim_time: float) -> str:
        color = self.color_at(sim_time)
        emoji = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴"}[color.value]
        return (f"{emoji} {self.direction.value:5s} [{color.value:6s}]"
                f"  cars waiting: {len(self.queue)}")


# ─────────────────────────────────────────────
#  Intersection
# ─────────────────────────────────────────────

class Intersection:
    """
    Manages four stop lights and enforces the one-at-a-time rule to
    prevent crashes.  Lights are staggered so only one can be GREEN at
    a time (each offset by 135 / 4 ≈ 33.75 seconds).
    """

    def __init__(self):
        offset = StopLight.CYCLE / 4  # ≈ 33.75 s between each light turning green
        self.lights: dict[Direction, StopLight] = {
            Direction.NORTH: StopLight(Direction.NORTH, phase_offset=0.0),
            Direction.WEST: StopLight(Direction.WEST, phase_offset=offset * 1),
            Direction.SOUTH: StopLight(Direction.SOUTH, phase_offset=offset * 2),
            Direction.EAST: StopLight(Direction.EAST, phase_offset=offset * 3),
        }
        self.passage_log: list[str] = []  # full history of every car that passed
        self.active_car: Car | None = None  # the car currently in the intersection

    # ------------------------------------------------------------------
    def add_car(self, car: Car):
        self.lights[car.current_position].add_car(car)

    # ------------------------------------------------------------------
    def _intersection_clear(self) -> bool:
        """True when no car is currently moving through the intersection."""
        return self.active_car is None

    # ------------------------------------------------------------------
    def tick(self, sim_time: float):
        """
        One simulation tick.  For every GREEN light, if the intersection
        is clear, release the next queued car, move it, then re-queue it
        at the next light.
        """
        for direction in Direction:
            light = self.lights[direction]

            if not light.is_go(sim_time):
                continue
            if not self._intersection_clear():
                break  # only one car moves per tick
            if not light.queue:
                continue

            # --- release a car ---
            car = light.pop_next_car()
            self.active_car = car

            car.move(sim_time)

            # log the passage
            record = (f"t={sim_time:6.1f}s | Car {car.car_id:4s} | "
                      f"{direction.value:5s} → {car.current_position.value}")
            self.passage_log.append(record)

            # re-queue at the next light (the car now sits at the next intersection)
            next_light = self.lights[car.current_position]
            next_light.add_car(car)

            self.active_car = None  # car has cleared the intersection
            break  # one car per tick

    # ------------------------------------------------------------------
    def print_status(self, sim_time: float):
        print(f"\n── t = {sim_time:.1f}s ──────────────────────────────")
        for direction in Direction:
            print(" ", self.lights[direction].status(sim_time))

    # ------------------------------------------------------------------
    def print_full_log(self):
        print("\n" + "═" * 55)
        print("  PASSAGE LOG  (all cars, in order)")
        print("═" * 55)
        for entry in self.passage_log:
            print(" ", entry)
        print("═" * 55)

    # ------------------------------------------------------------------
    def print_car_histories(self, cars: list[Car]):
        print("\n" + "═" * 55)
        print("  PER-CAR HISTORY")
        print("═" * 55)
        for car in cars:
            print(car.history_str())
        print("═" * 55)


# ─────────────────────────────────────────────
#  Simulation Runner
# ─────────────────────────────────────────────

class Simulation:
    """
    Drives the intersection forward in discrete time steps.
    Each step represents one second of simulation time.
    """

    def __init__(self, duration: float = 540.0, tick_size: float = 1.0):
        self.duration = duration  # total seconds to simulate
        self.tick_size = tick_size  # seconds per tick
        self.intersection = Intersection()
        self.cars: list[Car] = []

    # ------------------------------------------------------------------
    def spawn_cars(self, cars_per_light: int = 3):
        """Create cars and distribute them across the four lights."""
        car_id_counter = 1
        for direction in Direction:
            for _ in range(cars_per_light):
                car = Car(f"C{car_id_counter:02d}", direction)
                self.cars.append(car)
                self.intersection.add_car(car)
                car_id_counter += 1

    # ------------------------------------------------------------------
    def run(self, status_every: float = 60.0):
        """Run the full simulation, printing status at regular intervals."""
        print("\n" + "═" * 55)
        print("  TRAFFIC INTERSECTION SIMULATION")
        print(f"  Duration: {self.duration}s  |  Tick: {self.tick_size}s")
        print("═" * 55)

        t = 0.0
        next_status = 0.0

        while t <= self.duration:
            if t >= next_status:
                self.intersection.print_status(t)
                next_status += status_every

            self.intersection.tick(t)
            t += self.tick_size

        # Final reports
        self.intersection.print_full_log()
        self.intersection.print_car_histories(self.cars)


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    random.seed(42)

    sim = Simulation(duration=540, tick_size=1.0)  # simulate 9 minutes
    sim.spawn_cars(cars_per_light=3)  # 3 cars at each of the 4 lights = 12 cars total
    sim.run(status_every=60.0)  # print intersection status every 60s