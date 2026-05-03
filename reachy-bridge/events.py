from dataclasses import dataclass, field
from enum import Enum
from typing import Any

State = dict[str, Any]


class EventType(Enum):
    OVERTAKE = "overtake"
    RETIREMENT = "retirement"
    CRASH = "crash"
    SAFETY_CAR = "safety_car"
    VSC = "vsc"
    RED_FLAG = "red_flag"
    GREEN_FLAG = "green_flag"
    FASTEST_LAP = "fastest_lap"
    PIT_IN = "pit_in"
    PIT_OUT = "pit_out"


@dataclass
class F1Event:
    type: EventType
    data: dict = field(default_factory=dict)

    def __str__(self):
        return f"{self.type.value}: {self.data}"


def _driver_name(state: State, racing_number: str) -> str:
    driver = state.get("DriverList", {}).get(str(racing_number), {})
    return driver.get("FullName") or driver.get("Tla") or f"Car {racing_number}"


def _normalize_messages(messages_field) -> list:
    """F1 SSE sends RaceControlMessages.Messages as either a list or a
    numeric-keyed dict after incremental merges. Normalize to a list."""
    if isinstance(messages_field, list):
        return messages_field
    if isinstance(messages_field, dict):
        return [messages_field[k] for k in sorted(messages_field, key=lambda x: int(x))]
    return []


def detect_events(prev: State, curr: State) -> list["F1Event"]:
    events: list[F1Event] = []
    events.extend(_check_track_status(prev, curr))
    events.extend(_check_timing_data(prev, curr))
    events.extend(_check_race_control(prev, curr))
    events.extend(_check_fastest_lap(prev, curr))
    return events


def _check_track_status(prev: State, curr: State) -> list["F1Event"]:
    prev_status = prev.get("TrackStatus", {}).get("Status")
    curr_status = curr.get("TrackStatus", {}).get("Status")
    curr_msg = curr.get("TrackStatus", {}).get("Message", "")

    if prev_status == curr_status:
        return []

    mapping = {
        "3": (EventType.SAFETY_CAR, {"message": curr_msg}),
        "4": (EventType.VSC, {"message": curr_msg}),
        "5": (EventType.RED_FLAG, {"message": curr_msg}),
    }
    if curr_status in mapping:
        etype, edata = mapping[curr_status]
        return [F1Event(etype, edata)]

    # Green flag after interruption
    if curr_status == "1" and prev_status in ("3", "4", "5"):
        return [F1Event(EventType.GREEN_FLAG, {"message": "Track is green"})]

    return []


def _check_timing_data(prev: State, curr: State) -> list["F1Event"]:
    events: list[F1Event] = []
    prev_lines = prev.get("TimingData", {}).get("Lines", {})
    curr_lines = curr.get("TimingData", {}).get("Lines", {})

    for car_num, curr_driver in curr_lines.items():
        prev_driver = prev_lines.get(car_num, {})
        name = _driver_name(curr, car_num)

        # Retirement
        if not prev_driver.get("Retired") and curr_driver.get("Retired"):
            events.append(F1Event(EventType.RETIREMENT, {
                "driver": name,
                "racing_number": car_num,
                "position": curr_driver.get("Position"),
            }))

        # Overtake: position number decreased = moved forward
        prev_pos = prev_driver.get("Position")
        curr_pos = curr_driver.get("Position")
        if (prev_pos and curr_pos
                and isinstance(prev_pos, int) and isinstance(curr_pos, int)
                and curr_pos < prev_pos):
            events.append(F1Event(EventType.OVERTAKE, {
                "driver": name,
                "racing_number": car_num,
                "from_position": prev_pos,
                "to_position": curr_pos,
            }))

        # Pit in / pit out
        if not prev_driver.get("InPit") and curr_driver.get("InPit"):
            events.append(F1Event(EventType.PIT_IN, {
                "driver": name,
                "racing_number": car_num,
                "position": curr_driver.get("Position"),
            }))
        elif prev_driver.get("InPit") and not curr_driver.get("InPit"):
            events.append(F1Event(EventType.PIT_OUT, {
                "driver": name,
                "racing_number": car_num,
                "position": curr_driver.get("Position"),
            }))

    return events


def _check_race_control(prev: State, curr: State) -> list["F1Event"]:
    prev_msgs = _normalize_messages(
        prev.get("RaceControlMessages", {}).get("Messages", [])
    )
    curr_msgs = _normalize_messages(
        curr.get("RaceControlMessages", {}).get("Messages", [])
    )

    if len(curr_msgs) <= len(prev_msgs):
        return []

    events: list[F1Event] = []
    for msg in curr_msgs[len(prev_msgs):]:
        if msg.get("Category") == "Accident":
            racing_number = str(msg.get("RacingNumber", ""))
            name = _driver_name(curr, racing_number) if racing_number else "Unknown driver"
            events.append(F1Event(EventType.CRASH, {
                "driver": name,
                "racing_number": racing_number,
                "message": msg.get("Message", ""),
                "lap": msg.get("Lap"),
                "sector": msg.get("Sector"),
            }))
    return events


def _check_fastest_lap(prev: State, curr: State) -> list["F1Event"]:
    events: list[F1Event] = []
    prev_stats = prev.get("TimingStats", {}).get("Lines", {})
    curr_stats = curr.get("TimingStats", {}).get("Lines", {})

    for car_num, curr_stat in curr_stats.items():
        prev_fl = prev_stats.get(car_num, {}).get("FastestLap")
        curr_fl = curr_stat.get("FastestLap")
        if curr_fl and curr_fl != prev_fl:
            events.append(F1Event(EventType.FASTEST_LAP, {
                "driver": _driver_name(curr, car_num),
                "racing_number": car_num,
                "time": curr_fl,
            }))
    return events
