import os
import queue
import threading
import anthropic
from events import F1Event, EventType

SYSTEM_PROMPT = (
    "You are a sharp, energetic F1 TV commentator. "
    "Write a single punchy commentary line (max 2 sentences) for the race event you're given. "
    "Be dramatic, use driver names and positions. No stage directions."
)

# Low-drama events get a canned line, high-drama events go to the LLM
CANNED = {
    EventType.PIT_IN: "{driver} ducks into the pits from P{position}.",
    EventType.PIT_OUT: "{driver} rejoins the track.",
}

LLM_PROMPTS = {
    EventType.OVERTAKE: "{driver} just moved from P{from_position} to P{to_position}!",
    EventType.RETIREMENT: "{driver} has retired from the race at P{position}.",
    EventType.CRASH: "Accident involving {driver}! {message}",
    EventType.SAFETY_CAR: "Safety car has been deployed!",
    EventType.VSC: "Virtual Safety Car! All drivers slow down.",
    EventType.RED_FLAG: "RED FLAG! The race has been stopped!",
    EventType.GREEN_FLAG: "Green flag — racing resumes!",
    EventType.FASTEST_LAP: "{driver} sets the fastest lap of the race — {time}!",
}


class CommentaryEngine:
    def __init__(self, reachy):
        self.reachy = reachy
        self.disabled = os.getenv("REACHY_DISABLED", "0") == "1"
        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self._queue: queue.Queue = queue.Queue(maxsize=4)  # drop stale events if backed up
        threading.Thread(target=self._worker, daemon=True).start()

    def handle(self, event: F1Event):
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            pass  # race is moving fast; stale commentary isn't worth queuing

    def _worker(self):
        while True:
            event = self._queue.get()
            try:
                text = self._generate(event)
                if text:
                    self._speak(text)
            except Exception as e:
                print(f"[commentary error] {e}")
            finally:
                self._queue.task_done()

    def _generate(self, event: F1Event) -> str:
        if event.type in CANNED:
            try:
                return CANNED[event.type].format(**event.data)
            except KeyError:
                return ""

        prompt_template = LLM_PROMPTS.get(event.type)
        if not prompt_template:
            return ""

        try:
            prompt = prompt_template.format(**event.data)
        except KeyError:
            prompt = f"Race event: {event.type.value}"

        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    def _speak(self, text: str):
        print(f"[commentary] {text}")
        if self.disabled:
            return
        try:
            self.reachy.say(text)
        except Exception as e:
            print(f"[tts error] {e}")
