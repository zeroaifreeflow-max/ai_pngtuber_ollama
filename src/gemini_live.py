import asyncio
import wave
import struct
import os
from google import genai
from google.genai import types
from src.config import Config
from src.memory import get_memory_context, update_memory

# Audio constants
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM

class GeminiLiveEngine:
    """Real-time voice conversation engine using Gemini Live API."""

    def __init__(self):
        self.client = None
        self.session = None
        self.base_lore = ""
        self.is_connected = False
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Gemini client and load lore."""
        if not Config.GEMINI_API_KEY:
            print("[Live API] Error: GEMINI_API_KEY is missing.")
            return

        # Load Lore
        if Config.LORE_PATH.exists():
            with open(Config.LORE_PATH, 'r', encoding='utf-8') as f:
                self.base_lore = f.read().strip()

        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        print("[Live API] Client initialized.")

    def _build_config(self):
        """Build LiveConnectConfig with voice and system instruction."""
        memory_context = get_memory_context()
        system_instruction = f"{self.base_lore}\n\n{memory_context}"

        config_dict = {
            "response_modalities": [Config.LIVE_RESPONSE_MODALITY],
            "system_instruction": system_instruction,
        }

        # Voice config for audio mode
        if Config.LIVE_RESPONSE_MODALITY == "AUDIO":
            config_dict["speech_config"] = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=Config.LIVE_VOICE_NAME
                    )
                )
            )

        return config_dict

    async def connect(self):
        """Establish a live session with Gemini."""
        if not self.client:
            print("[Live API] Client not initialized.")
            return False

        try:
            config = self._build_config()
            self.session = self.client.aio.live.connect(
                model=Config.LIVE_MODEL,
                config=config,
            )
            self.is_connected = True
            print(f"[Live API] Ready. Model: {Config.LIVE_MODEL}, Voice: {Config.LIVE_VOICE_NAME}")
            return True
        except Exception as e:
            print(f"[Live API] Connection failed: {e}")
            return False

    async def send_text_get_text(self, user_text: str) -> str:
        """Send text and receive text response (text-to-text mode)."""
        if not self.client:
            return "Error: Live API not initialized."

        try:
            config = self._build_config()
            config["response_modalities"] = ["TEXT"]

            async with self.client.aio.live.connect(
                model=Config.LIVE_MODEL, config=config
            ) as session:
                await session.send_client_content(
                    turns=types.Content(
                        role="user", parts=[types.Part(text=user_text)]
                    ),
                    turn_complete=True,
                )

                response_parts = []
                async for msg in session.receive():
                    if msg.text is not None:
                        response_parts.append(msg.text)
                    if msg.server_content and msg.server_content.turn_complete:
                        break

                ai_text = "".join(response_parts) or "..."

                # Memory analysis
                self._analyze_memory_sync(user_text, ai_text)

                # Save subtitles
                self._save_subs(ai_text)

                return ai_text

        except Exception as e:
            print(f"[Live API] Text error: {e}")
            return "..."

    async def send_text_get_audio(self, user_text: str) -> tuple:
        """Send text and receive audio response. Returns (text_response, audio_path)."""
        if not self.client:
            return "Error: Live API not initialized.", None

        try:
            config = self._build_config()
            config["response_modalities"] = ["AUDIO"]
            config["output_audio_transcription"] = {}

            async with self.client.aio.live.connect(
                model=Config.LIVE_MODEL, config=config
            ) as session:
                await session.send_client_content(
                    turns=types.Content(
                        role="user", parts=[types.Part(text=user_text)]
                    ),
                    turn_complete=True,
                )

                audio_chunks = []
                transcript_parts = []

                async for msg in session.receive():
                    # Collect audio data
                    if msg.data:
                        audio_chunks.append(msg.data)
                    # Collect transcript
                    if (msg.server_content
                            and msg.server_content.output_transcription
                            and msg.server_content.output_transcription.text):
                        transcript_parts.append(
                            msg.server_content.output_transcription.text
                        )
                    if msg.server_content and msg.server_content.turn_complete:
                        break

                # Save audio to WAV
                audio_path = None
                if audio_chunks:
                    audio_path = str(Config.LIVE_AUDIO_OUTPUT_PATH)
                    self._save_pcm_as_wav(
                        b"".join(audio_chunks), audio_path, RECEIVE_SAMPLE_RATE
                    )

                transcript = "".join(transcript_parts) or user_text
                self._save_subs(transcript)
                self._analyze_memory_sync(user_text, transcript)

                return transcript, audio_path

        except Exception as e:
            print(f"[Live API] Audio error: {e}")
            return "...", None

    async def send_audio_get_audio(self, audio_bytes: bytes) -> tuple:
        """Send audio input and receive audio response.
        Returns (transcript, audio_path).
        audio_bytes should be 16-bit PCM at 16kHz mono.
        """
        if not self.client:
            return "Error: Live API not initialized.", None

        try:
            config = self._build_config()
            config["response_modalities"] = ["AUDIO"]
            config["input_audio_transcription"] = {}
            config["output_audio_transcription"] = {}

            async with self.client.aio.live.connect(
                model=Config.LIVE_MODEL, config=config
            ) as session:
                # Send audio as realtime input
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=audio_bytes,
                        mime_type="audio/pcm;rate=16000",
                    )
                )

                audio_chunks = []
                input_transcript = []
                output_transcript = []

                async for msg in session.receive():
                    if msg.data:
                        audio_chunks.append(msg.data)
                    if msg.server_content:
                        if (msg.server_content.input_transcription
                                and msg.server_content.input_transcription.text):
                            input_transcript.append(
                                msg.server_content.input_transcription.text
                            )
                        if (msg.server_content.output_transcription
                                and msg.server_content.output_transcription.text):
                            output_transcript.append(
                                msg.server_content.output_transcription.text
                            )
                        if msg.server_content.turn_complete:
                            break

                # Save response audio
                audio_path = None
                if audio_chunks:
                    audio_path = str(Config.LIVE_AUDIO_OUTPUT_PATH)
                    self._save_pcm_as_wav(
                        b"".join(audio_chunks), audio_path, RECEIVE_SAMPLE_RATE
                    )

                user_text = "".join(input_transcript) or "(audio input)"
                ai_text = "".join(output_transcript) or "..."
                self._save_subs(ai_text)
                self._analyze_memory_sync(user_text, ai_text)

                return ai_text, audio_path

        except Exception as e:
            print(f"[Live API] Audio-to-audio error: {e}")
            return "...", None

    async def live_mic_session(self, on_audio_response=None, on_transcript=None):
        """Run a continuous microphone-based live session.
        Requires sounddevice. Calls on_audio_response(audio_bytes) and
        on_transcript(text) callbacks.
        """
        try:
            import sounddevice as sd
        except ImportError:
            print("[Live API] sounddevice not installed. Run: pip install sounddevice")
            return

        import numpy as np

        config = self._build_config()
        config["response_modalities"] = ["AUDIO"]
        config["input_audio_transcription"] = {}
        config["output_audio_transcription"] = {}

        print("[Live API] Starting live mic session... (Ctrl+C to stop)")

        audio_out_queue = asyncio.Queue()

        async with self.client.aio.live.connect(
            model=Config.LIVE_MODEL, config=config
        ) as session:

            # --- Mic capture task ---
            async def capture_mic():
                loop = asyncio.get_event_loop()
                mic_queue = asyncio.Queue()

                def mic_callback(indata, frames, time_info, status):
                    pcm_bytes = indata.tobytes()
                    loop.call_soon_threadsafe(mic_queue.put_nowait, pcm_bytes)

                stream = sd.InputStream(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=1024,
                    callback=mic_callback,
                )
                with stream:
                    while True:
                        chunk = await mic_queue.get()
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=chunk,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )

            # --- Receive task ---
            async def receive_responses():
                async for msg in session.receive():
                    if msg.data:
                        audio_out_queue.put_nowait(msg.data)
                        if on_audio_response:
                            on_audio_response(msg.data)
                    if msg.server_content:
                        if (msg.server_content.input_transcription
                                and msg.server_content.input_transcription.text):
                            text = msg.server_content.input_transcription.text
                            print(f"[You]: {text}")
                        if (msg.server_content.output_transcription
                                and msg.server_content.output_transcription.text):
                            text = msg.server_content.output_transcription.text
                            print(f"[AI]: {text}")
                            self._save_subs(text)
                            if on_transcript:
                                on_transcript(text)

            # --- Playback task ---
            async def play_audio():
                loop = asyncio.get_event_loop()

                play_stream = sd.OutputStream(
                    samplerate=RECEIVE_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=1024,
                )
                with play_stream:
                    while True:
                        chunk = await audio_out_queue.get()
                        samples = np.frombuffer(chunk, dtype="int16")
                        play_stream.write(samples.reshape(-1, 1))

            # Run all tasks concurrently
            await asyncio.gather(
                capture_mic(),
                receive_responses(),
                play_audio(),
            )

    def _save_pcm_as_wav(self, pcm_data: bytes, path: str, sample_rate: int):
        """Save raw PCM bytes as a WAV file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)

    def _analyze_memory_sync(self, user_input, ai_output):
        """Extract facts using a lightweight call."""
        try:
            response = self.client.models.generate_content(
                model=Config.CHAT_MODEL,
                contents=f"""
Extract 1 important fact about the user from this chat. If none, return NO_DATA.
User: {user_input}
AI: {ai_output}
Output format: Fact string only.
""",
            )
            fact = response.text.strip()
            if fact and "NO_DATA" not in fact:
                print(f"[Memory]: {fact}")
                update_memory("facts", "", fact)
        except Exception:
            pass

    def _save_subs(self, text):
        try:
            with open(Config.SUBS_PATH, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception:
            pass
