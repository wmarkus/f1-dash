import os
import time
import threading
from events import F1Event, EventType


class ReachyReactions:
    def __init__(self, reachy):
        self.reachy = reachy
        self.disabled = os.getenv("REACHY_DISABLED", "0") == "1"
        # Mutex so movements don't overlap
        self._lock = threading.Lock()

    def react(self, event: F1Event):
        handler = getattr(self, f"_{event.type.value}", None)
        if not handler:
            return
        threading.Thread(target=self._run, args=(handler, event), daemon=True).start()

    def _run(self, handler, event: F1Event):
        with self._lock:
            if self.disabled:
                print(f"[reachy reaction] {event.type.value}")
                return
            try:
                handler(event)
            except Exception as e:
                print(f"[reachy error] {e}")

    # ── Movements ──────────────────────────────────────────────────────────────
    # head= dict accepts: yaw (left/right), pitch (up/down), roll (tilt)
    # interpolation: "minjerk" (smooth), "cartoon" (snappy), "linear"

    def _overtake(self, event: F1Event):
        # Excited snap left-right
        self.reachy.goto_target(head={"yaw": 20}, duration=0.3, interpolation="cartoon")
        time.sleep(0.25)
        self.reachy.goto_target(head={"yaw": -20}, duration=0.3, interpolation="cartoon")
        time.sleep(0.25)
        self.reachy.goto_target(head={"yaw": 0}, duration=0.4, interpolation="minjerk")

    def _crash(self, event: F1Event):
        # Dramatic drop + slow disbelieving shake
        self.reachy.goto_target(head={"pitch": -15}, duration=0.5, interpolation="minjerk")
        time.sleep(0.4)
        for _ in range(2):
            self.reachy.goto_target(head={"yaw": -15, "pitch": -15}, duration=0.5)
            time.sleep(0.4)
            self.reachy.goto_target(head={"yaw": 15, "pitch": -15}, duration=0.5)
            time.sleep(0.4)
        self.reachy.goto_target(head={"yaw": 0, "pitch": 0}, duration=0.6, interpolation="minjerk")

    def _retirement(self, event: F1Event):
        # Slow sad droop
        self.reachy.goto_target(head={"pitch": -20}, duration=1.2, interpolation="minjerk")
        time.sleep(1.5)
        self.reachy.goto_target(head={"pitch": 0}, duration=0.8, interpolation="minjerk")

    def _safety_car(self, event: F1Event):
        # Cautious slow scan
        self.reachy.goto_target(head={"yaw": -25}, duration=1.5, interpolation="minjerk")
        time.sleep(1.0)
        self.reachy.goto_target(head={"yaw": 25}, duration=2.0, interpolation="minjerk")
        time.sleep(1.0)
        self.reachy.goto_target(head={"yaw": 0}, duration=1.0, interpolation="minjerk")

    def _vsc(self, event: F1Event):
        # Calm nod
        self.reachy.goto_target(head={"pitch": 10}, duration=1.0, interpolation="minjerk")
        time.sleep(0.8)
        self.reachy.goto_target(head={"pitch": 0}, duration=0.8, interpolation="minjerk")

    def _red_flag(self, event: F1Event):
        # Alarmed rapid shake
        for _ in range(3):
            self.reachy.goto_target(head={"yaw": -25}, duration=0.2, interpolation="cartoon")
            time.sleep(0.15)
            self.reachy.goto_target(head={"yaw": 25}, duration=0.2, interpolation="cartoon")
            time.sleep(0.15)
        self.reachy.goto_target(head={"yaw": 0}, duration=0.5, interpolation="minjerk")

    def _green_flag(self, event: F1Event):
        # Energetic nod
        for _ in range(2):
            self.reachy.goto_target(head={"pitch": -10}, duration=0.3, interpolation="cartoon")
            time.sleep(0.2)
            self.reachy.goto_target(head={"pitch": 5}, duration=0.3, interpolation="cartoon")
            time.sleep(0.2)
        self.reachy.goto_target(head={"pitch": 0}, duration=0.4, interpolation="minjerk")

    def _fastest_lap(self, event: F1Event):
        # Celebration — look up then side-to-side
        self.reachy.goto_target(head={"pitch": 15}, duration=0.4, interpolation="cartoon")
        time.sleep(0.3)
        for _ in range(2):
            self.reachy.goto_target(head={"pitch": 5, "yaw": -15}, duration=0.3)
            time.sleep(0.2)
            self.reachy.goto_target(head={"pitch": 5, "yaw": 15}, duration=0.3)
            time.sleep(0.2)
        self.reachy.goto_target(head={"yaw": 0, "pitch": 0}, duration=0.5, interpolation="minjerk")

    def _pit_in(self, event: F1Event):
        # Glance toward pit wall
        self.reachy.goto_target(head={"yaw": 30}, duration=0.6, interpolation="minjerk")
        time.sleep(1.2)
        self.reachy.goto_target(head={"yaw": 0}, duration=0.5, interpolation="minjerk")

    def _pit_out(self, event: F1Event):
        # Quick look back at track
        self.reachy.goto_target(head={"yaw": -20}, duration=0.4, interpolation="cartoon")
        time.sleep(0.5)
        self.reachy.goto_target(head={"yaw": 0}, duration=0.4, interpolation="minjerk")
