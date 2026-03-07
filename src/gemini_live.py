"""
Gemini Live API — bidirectional audio streaming with avatar animation.

Architecture:
  4 concurrent async tasks running in a TaskGroup:
    1. listen_mic   — reads PCM from microphone → out_queue
    2. send_audio   — out_queue → session.send_realtime_input()
    3. receive_audio — session.receive() → audio_in_queue (+ subtitle text)
    4. play_audio   — audio_in_queue → speaker output

  Avatar state is driven by a shared `is_speaking` flag toggled by
  play_audio, and read by the OpenCV render loop in main.py.
"""

import asyncio
import sys
import traceback

import pyaudio
from google import genai

from src.config import Config
from src.memory import get_memory_context

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

# Audio constants
FORMAT = pyaudio.paInt16
CHANNELS = 1


class GeminiLiveSession:
    """Manages a bidirectional audio session with Gemini Live API."""

    def __init__(self):
        self.audio_in_queue: asyncio.Queue | None = None
        self.out_queue: asyncio.Queue | None = None
        self.session = None
        self.mic_stream = None
        self.pya = pyaudio.PyAudio()

        # Shared state for avatar animation (read from main thread)
        self.is_speaking = False

        # Subtitle callback — set by main.py to capture transcription text
        self.on_subtitle = None

        # Build system instruction from lore + memory
        self._system_instruction = self._load_system_instruction()

        # Gemini client
        self.client = genai.Client(
            api_key=Config.GEMINI_API_KEY,
            http_options={"api_version": Config.LIVE_API_VERSION},
        )

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_system_instruction() -> str:
        lore = ""
        if Config.LORE_PATH.exists():
            with open(Config.LORE_PATH, "r", encoding="utf-8") as f:
                lore = f.read().strip()
        memory_ctx = get_memory_context()
        return f"{lore}\n\n{memory_ctx}"

    def _build_config(self) -> dict:
        cfg = {
            "system_instruction": self._system_instruction,
            "response_modalities": ["AUDIO"],
        }
        if Config.ENABLE_PROACTIVE_AUDIO:
            cfg["proactivity"] = {"proactive_audio": True}
        return cfg

    # ------------------------------------------------------------------
    # Async tasks
    # ------------------------------------------------------------------

    async def _listen_mic(self):
        """Capture PCM audio from the default microphone."""
        mic_info = self.pya.get_default_input_device_info()
        self.mic_stream = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=Config.SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=Config.AUDIO_CHUNK_SIZE,
        )
        kwargs = {"exception_on_overflow": False} if __debug__ else {}
        while True:
            data = await asyncio.to_thread(
                self.mic_stream.read, Config.AUDIO_CHUNK_SIZE, **kwargs
            )
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def _send_audio(self):
        """Forward mic chunks to the Gemini Live session."""
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def _receive_audio(self):
        """Read responses from the session and route audio/text."""
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    # Capture transcript for subtitles
                    print(text, end="")
                    if self.on_subtitle:
                        self.on_subtitle(text)

            # On turn_complete (e.g. interruption) — flush queued audio
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()
            self.is_speaking = False

    async def _play_audio(self):
        """Play received PCM audio through the default speaker."""
        speaker = await asyncio.to_thread(
            self.pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=Config.RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            self.is_speaking = True
            await asyncio.to_thread(speaker.write, bytestream)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self):
        """Connect to Gemini Live and run all streaming tasks."""
        print(f"🎤 Connecting to Gemini Live ({Config.LIVE_MODEL})...")
        try:
            async with (
                self.client.aio.live.connect(
                    model=Config.LIVE_MODEL,
                    config=self._build_config(),
                ) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                print("✅ Connected! Start talking (use headphones to avoid echo).")

                tg.create_task(self._listen_mic())
                tg.create_task(self._send_audio())
                tg.create_task(self._receive_audio())
                tg.create_task(self._play_audio())

        except asyncio.CancelledError:
            pass
        except asyncio.ExceptionGroup as eg:
            traceback.print_exception(eg)
        finally:
            self._cleanup()

    def _cleanup(self):
        if self.mic_stream:
            self.mic_stream.close()
        self.pya.terminate()
