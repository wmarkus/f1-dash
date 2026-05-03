import copy
import json
import os
import sys
import threading
import time

import requests
import sseclient
from dotenv import load_dotenv

from events import State, detect_events
from commentary import CommentaryEngine
from reachy_reactions import ReachyReactions

load_dotenv()

REALTIME_URL = os.getenv("REALTIME_URL", "http://localhost:4000")
REACHY_DISABLED = os.getenv("REACHY_DISABLED", "0") == "1"


def deep_merge(base: dict, patch: dict) -> dict:
    """Mirrors the state merge logic used by the f1-dash realtime service."""
    result = copy.deepcopy(base)
    for key, value in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def connect(url: str):
    while True:
        try:
            print(f"Connecting to {url}/api/realtime ...")
            resp = requests.get(
                f"{url}/api/realtime",
                stream=True,
                timeout=None,
                headers={"Accept": "text/event-stream"},
            )
            resp.raise_for_status()
            yield from sseclient.SSEClient(resp).events()
        except Exception as e:
            print(f"SSE connection lost: {e}. Reconnecting in 5s...")
            time.sleep(5)


def main():
    if REACHY_DISABLED:
        reachy = None
        print("[dry-run] REACHY_DISABLED=1 — no robot connection")
    else:
        from reachy_mini import ReachyMini
        reachy = ReachyMini()
        print("Reachy Mini connected.")

    commentary = CommentaryEngine(reachy)
    reactions = ReachyReactions(reachy)

    state: State = {}

    for sse_event in connect(REALTIME_URL):
        if sse_event.event == "keep-alive-text" or not sse_event.data:
            continue

        try:
            data = json.loads(sse_event.data)
        except json.JSONDecodeError:
            continue

        if sse_event.event == "initial":
            state = data
            print("Initial state loaded — watching for events.")
            continue

        if sse_event.event == "update":
            prev_state = copy.deepcopy(state)
            state = deep_merge(state, data)

            for f1_event in detect_events(prev_state, state):
                print(f"  {f1_event}")
                # Fire both concurrently — speech and movement overlap naturally
                threading.Thread(target=commentary.handle, args=(f1_event,), daemon=True).start()
                reactions.react(f1_event)


if __name__ == "__main__":
    main()
