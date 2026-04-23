#!/usr/bin/env uv run
####################################################################
# Sample TUI app with a push to talk interface to the Realtime API #
# If you have `uv` installed and the `OPENAI_API_KEY`              #
# environment variable set, you can run this example with just     #
#                                                                  #
# `./push_to_talk_app.py`                                          #
#                                                                  #
# On Mac, you'll also need `brew install portaudio ffmpeg`          #
####################################################################
#
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "textual",
#     "numpy",
#     "pyaudio",
#     "pydub",
#     "sounddevice",
#     "openai[realtime]",
# ]
# ///
from __future__ import annotations

import base64
import asyncio
import json
import os
from typing import Any, cast
from typing_extensions import override

from textual import events
from audio_util import CHANNELS, SAMPLE_RATE, AudioPlayerAsync
from textual.app import App, ComposeResult
from textual.widgets import Button, Static, RichLog
from textual.reactive import reactive
from textual.containers import Container

from openai import AsyncOpenAI
from openai.types.beta.realtime.session import Session
from openai.resources.realtime.realtime import AsyncRealtimeConnection

import datetime


def get_current_time():
    now = datetime.datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')}."


def load_context() -> str:
    """Load previous conversation context from context.json if it exists."""
    base_instructions = (
        "You are a personal AI assistant with memory of past conversations. "
        "You HAVE been told about the user before. You MUST use this information naturally "
        "in conversation — reference past topics, remember their name, preferences, and anything "
        "they've told you. Do not say you don't have memory or can't remember things. "
        "You are NOT a generic assistant — you know this specific user.\n\n"
    )

    if os.path.exists("context.json"):
        with open("context.json", "r") as f:
            data = json.load(f)
        summary = data.get("summary", "")
        key_facts = data.get("key_facts", "")
        last_topic = data.get("last_topic", "")
        memory = (
            f"WHAT YOU KNOW ABOUT THIS USER:\n"
            f"Summary: {summary}\n"
            f"Key facts: {key_facts}\n"
            f"Last topic discussed: {last_topic}\n\n"
            f"Use this information proactively. For example, greet them by name if you know it, "
            f"or reference the last topic you discussed."
        )
        return base_instructions + memory

    # First time — no context file yet
    return (
        "You are a personal AI assistant with memory that builds over time. "
        "This is your FIRST conversation with this user — you know nothing about them yet. "
        "Your goal in this conversation is to get to know them naturally — learn their name, "
        "interests, and anything relevant about them through conversation. "
        "Do not make it feel like an interview, just be friendly and curious. "
        "This information will be remembered for all future conversations."
    )


def _get_turn_detection(session) -> object | None:
    """
    Make the sample compatible with both the old (2.6.1) and newer SDK shapes.
    - Newer SDKs: session.turn_detection
    - 2.6.1:      session.audio.input.turn_detection
    """
    td = getattr(session, "turn_detection", None)
    if td is not None:
        return td

    audio = getattr(session, "audio", None)
    if not audio:
        return None
    _in = getattr(audio, "input", None)
    if not _in:
        return None
    return getattr(_in, "turn_detection", None)


class SessionDisplay(Static):
    """A widget that shows the current session ID."""

    session_id = reactive("")

    @override
    def render(self) -> str:
        return f"Session ID: {self.session_id}" if self.session_id else "Connecting..."


class AudioStatusIndicator(Static):
    """A widget that shows the current audio recording status."""

    is_recording = reactive(False)

    @override
    def render(self) -> str:
        status = (
            "🔴 Recording... (Press K to stop)" if self.is_recording else "⚪ Press K to start recording (Q to quit)"
        )
        return status


class RealtimeApp(App[None]):
    CSS = """
        Screen {
            background: #1a1b26;
        }

        Container {
            border: double rgb(91, 164, 91);
        }

        Horizontal {
            width: 100%;
        }

        #input-container {
            height: 5;
            margin: 1 1;
            padding: 1 2;
        }

        Input {
            width: 80%;
            height: 3;
        }

        Button {
            width: 20%;
            height: 3;
        }

        #bottom-pane {
            width: 100%;
            height: 82%;
            border: round rgb(205, 133, 63);
            content-align: center middle;
        }

        #status-indicator {
            height: 3;
            content-align: center middle;
            background: #2a2b36;
            border: solid rgb(91, 164, 91);
            margin: 1 1;
        }

        #session-display {
            height: 3;
            content-align: center middle;
            background: #2a2b36;
            border: solid rgb(91, 164, 91);
            margin: 1 1;
        }

        Static {
            color: white;
        }
    """

    client: AsyncOpenAI
    should_send_audio: asyncio.Event
    audio_player: AudioPlayerAsync
    last_audio_item_id: str | None
    connection: AsyncRealtimeConnection | None
    session: Session | None
    connected: asyncio.Event

    def __init__(self) -> None:
        super().__init__()
        self.connection = None
        self.session = None
        self.client = AsyncOpenAI()
        self.audio_player = AudioPlayerAsync()
        self.last_audio_item_id = None
        self.should_send_audio = asyncio.Event()
        self.connected = asyncio.Event()
        self.acc_items: dict[str, Any] = {}  # tracks transcript across full session

    @override
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Container():
            yield SessionDisplay(id="session-display")
            yield AudioStatusIndicator(id="status-indicator")
            yield RichLog(id="bottom-pane", wrap=True, highlight=True, markup=True)

    async def on_mount(self) -> None:
        self.run_worker(self.handle_realtime_connection())
        self.run_worker(self.send_mic_audio())

    async def handle_realtime_connection(self) -> None:
        async with self.client.realtime.connect(model="gpt-4o-realtime-preview-2024-12-17") as conn:
            self.connection = conn
            self.connected.set()

            context = load_context()
            print("=== INSTRUCTIONS BEING SENT ===")
            print(context)
            print("===============================")

            await conn.session.update(
                session={
                    "instructions": context,
                    "voice": "coral",
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.8,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 800,
                    },
                    "model": "gpt-4o-realtime-preview-2024-12-17",
                }
            )

            # Inject memory directly into conversation history for reliability
            await conn.send({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"[SYSTEM: Remember, you have the following memory about me: {context}. Act on this from the very start of our conversation.]"
                        }
                    ]
                }
            })

            async for event in conn:

                if event.type == "session.created":
                    self.session = event.session
                    session_display = self.query_one(SessionDisplay)
                    assert event.session.id is not None
                    session_display.session_id = event.session.id
                    continue

                if event.type == "session.updated":
                    self.session = event.session
                    continue

                # Flush old audio immediately when response is cancelled
                if event.type == "response.cancelled":
                    self.audio_player.stop()
                    continue

                if event.type == "response.output_audio.delta":
                    if event.item_id != self.last_audio_item_id:
                        self.audio_player.stop()  # flush old audio on new response
                        self.audio_player.reset_frame_count()
                        self.last_audio_item_id = event.item_id

                    bytes_data = base64.b64decode(event.delta)
                    self.audio_player.add_data(bytes_data)
                    continue

                if event.type == "response.output_audio_transcript.delta":
                    try:
                        text = self.acc_items[event.item_id]
                    except KeyError:
                        self.acc_items[event.item_id] = event.delta
                    else:
                        self.acc_items[event.item_id] = text + event.delta
                    transcript = self.acc_items[event.item_id].lower()

                    bottom_pane = self.query_one("#bottom-pane", RichLog)
                    bottom_pane.clear()
                    bottom_pane.write(self.acc_items[event.item_id])

                    if "time" in transcript:
                        await conn.send({"type": "response.cancel"})
                        local_response = get_current_time()
                        await conn.send({
                            "type": "response.create",
                            "response": {
                                "instructions": local_response
                            }
                        })
                        continue

                    continue

    async def _get_connection(self) -> AsyncRealtimeConnection:
        await self.connected.wait()
        assert self.connection is not None
        return self.connection

    async def send_mic_audio(self) -> None:
        import sounddevice as sd  # type: ignore

        sent_audio = False

        device_info = sd.query_devices()
        print(device_info)

        read_size = int(SAMPLE_RATE * 0.02)

        stream = sd.InputStream(
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            dtype="int16",
        )
        stream.start()

        status_indicator = self.query_one(AudioStatusIndicator)

        try:
            while True:
                if stream.read_available < read_size:
                    await asyncio.sleep(0)
                    continue

                await self.should_send_audio.wait()
                status_indicator.is_recording = True

                data, _ = stream.read(read_size)

                connection = await self._get_connection()
                if not sent_audio:
                    asyncio.create_task(connection.send({"type": "response.cancel"}))
                    sent_audio = True

                await connection.input_audio_buffer.append(audio=base64.b64encode(cast(Any, data)).decode("utf-8"))

                await asyncio.sleep(0)
        except KeyboardInterrupt:
            pass
        finally:
            stream.stop()
            stream.close()

    async def save_context_and_exit(self) -> None:
        """Summarize the conversation and merge it into context.json before exiting."""
        bottom_pane = self.query_one("#bottom-pane", RichLog)
        bottom_pane.write("\n[yellow]Saving context...[/yellow]")

        transcript = "\n".join(self.acc_items.values())

        if transcript.strip():
            try:
                # Load existing context to merge with
                previous_context = ""
                if os.path.exists("context.json"):
                    with open("context.json", "r") as f:
                        previous_context = f.read()

                response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You maintain a running memory profile for an AI assistant. "
                                "You will be given the previous memory profile and a new conversation transcript. "
                                "Merge them into an updated JSON object with these keys: "
                                "'summary' (2-3 sentences about the user overall), "
                                "'key_facts' (all important things learned about the user, as a bullet list), "
                                "'last_topic' (what was just discussed). "
                                "Do not lose any information from the previous profile. "
                                "Respond with raw JSON only, no markdown or code fences."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"PREVIOUS MEMORY:\n{previous_context}\n\nNEW CONVERSATION:\n{transcript}"
                        }
                    ]
                )

                raw = response.choices[0].message.content or ""
                clean = raw.replace("```json", "").replace("```", "").strip()

                with open("context.json", "w") as f:
                    f.write(clean)

                bottom_pane.write("[green]Context saved![/green]")

            except Exception as e:
                bottom_pane.write(f"[red]Failed to save context: {e}[/red]")

        self.exit()

    async def on_key(self, event: events.Key) -> None:
        """Handle key press events."""
        if event.key == "enter":
            self.query_one(Button).press()
            return

        if event.key == "q":
            await self.save_context_and_exit()
            return

        if event.key == "k":
            status_indicator = self.query_one(AudioStatusIndicator)
            if status_indicator.is_recording:
                self.should_send_audio.clear()
                status_indicator.is_recording = False

                if self.session and _get_turn_detection(self.session) is None:
                    conn = await self._get_connection()
                    await conn.input_audio_buffer.commit()
                    await conn.response.create()
            else:
                self.should_send_audio.set()
                status_indicator.is_recording = True


if __name__ == "__main__":
    app = RealtimeApp()
    app.run()
