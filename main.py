import threading
import asyncio
import queue
import cv2
import sys
import time
from src.config import Config
from src.ai_engine import AIEngine
from src.audio import generate_voice, play_audio_and_animate

# --- Global State ---
input_queue = queue.Queue()
is_running = True

def input_listener():
    """Thread to handle console input."""
    global is_running
    print("\n Type your message (Ctrl+C to quit):")
    while is_running:
        try:
            text = input()
            if text.strip():
                input_queue.put(text.strip())
        except (EOFError, KeyboardInterrupt):
            is_running = False
            break

def main():
    """Main entry point - routes to standard or Live API mode."""
    if Config.USE_LIVE_API:
        main_live()
    else:
        main_standard()

def main_standard():
    """Original text-based AI with gTTS/ElevenLabs voice."""
    global is_running

    # 1. Setup Avatar Window
    if not Config.MUTE_IMG_PATH.exists() or not Config.TALK_IMG_PATH.exists():
        print(f"Error: Avatar images not found at {Config.MUTE_IMG_PATH}")
        return

    avatar_mute = cv2.imread(str(Config.MUTE_IMG_PATH))
    avatar_talk = cv2.imread(str(Config.TALK_IMG_PATH))

    cv2.namedWindow("Avatar", cv2.WINDOW_AUTOSIZE)

    # 2. Initialize AI
    print("Initializing AI Engine (Standard)...")
    ai = AIEngine()

    # 3. Start Input Thread
    t = threading.Thread(target=input_listener, daemon=True)
    t.start()

    print("System Ready! Talk to your PngTuber now.")

    # 4. Main Event Loop
    while is_running:
        try:
            if cv2.getWindowProperty("Avatar", cv2.WND_PROP_VISIBLE) < 1:
                is_running = False
                break

            if not input_queue.empty():
                user_msg = input_queue.get()

                print(f"User: {user_msg}")
                response = ai.generate_response(user_msg)
                print(f"AI: {response}")

                generate_voice(response)
                play_audio_and_animate(avatar_mute, avatar_talk, "Avatar")

                print("\n Type your message:")

            cv2.imshow("Avatar", avatar_mute)

            key = cv2.waitKey(20) & 0xFF
            if key == 27:
                is_running = False
                break

        except KeyboardInterrupt:
            is_running = False
            break

    cv2.destroyAllWindows()
    print("Exiting...")
    sys.exit()

def main_live():
    """Gemini Live API mode with real-time voice."""
    global is_running

    from src.gemini_live import GeminiLiveEngine
    import pygame

    # 1. Setup Avatar Window
    if not Config.MUTE_IMG_PATH.exists() or not Config.TALK_IMG_PATH.exists():
        print(f"Error: Avatar images not found at {Config.MUTE_IMG_PATH}")
        return

    avatar_mute = cv2.imread(str(Config.MUTE_IMG_PATH))
    avatar_talk = cv2.imread(str(Config.TALK_IMG_PATH))
    cv2.namedWindow("Avatar", cv2.WINDOW_AUTOSIZE)

    # 2. Initialize Live Engine
    print(f"Initializing Gemini Live API (mode: {Config.LIVE_MODE})...")
    live_engine = GeminiLiveEngine()

    # 3. Mic live mode - fully real-time
    if Config.LIVE_MODE == "mic_live":
        _run_mic_live(live_engine, avatar_mute, avatar_talk)
        return

    # 4. Text input modes (text_to_text or text_to_audio)
    t = threading.Thread(target=input_listener, daemon=True)
    t.start()

    print("System Ready! (Gemini Live API)")

    loop = asyncio.new_event_loop()

    while is_running:
        try:
            if cv2.getWindowProperty("Avatar", cv2.WND_PROP_VISIBLE) < 1:
                is_running = False
                break

            if not input_queue.empty():
                user_msg = input_queue.get()
                print(f"User: {user_msg}")

                if Config.LIVE_MODE == "text_to_text":
                    response = loop.run_until_complete(
                        live_engine.send_text_get_text(user_msg)
                    )
                    print(f"AI: {response}")
                    generate_voice(response)
                    play_audio_and_animate(avatar_mute, avatar_talk, "Avatar")

                elif Config.LIVE_MODE == "text_to_audio":
                    transcript, audio_path = loop.run_until_complete(
                        live_engine.send_text_get_audio(user_msg)
                    )
                    print(f"AI: {transcript}")

                    if audio_path:
                        _play_wav_and_animate(
                            audio_path, avatar_mute, avatar_talk, "Avatar"
                        )
                    else:
                        generate_voice(transcript)
                        play_audio_and_animate(avatar_mute, avatar_talk, "Avatar")

                print("\n Type your message:")

            cv2.imshow("Avatar", avatar_mute)
            key = cv2.waitKey(20) & 0xFF
            if key == 27:
                is_running = False
                break

        except KeyboardInterrupt:
            is_running = False
            break

    loop.close()
    cv2.destroyAllWindows()
    print("Exiting...")
    sys.exit()

def _play_wav_and_animate(wav_path, mute_img, talk_img, window_name="Avatar"):
    """Play a WAV file and animate the avatar."""
    import pygame

    try:
        pygame.mixer.init(frequency=24000, size=-16, channels=1)
        voice_channel = pygame.mixer.Channel(1)
        sound = pygame.mixer.Sound(wav_path)
        voice_channel.play(sound)

        while voice_channel.get_busy():
            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    sys.exit()
            except:
                break

            cv2.imshow(window_name, talk_img)
            cv2.waitKey(100)

        cv2.imshow(window_name, mute_img)
        cv2.waitKey(20)

    except Exception as e:
        print(f"[Audio Error] WAV playback failed: {e}")

def _run_mic_live(live_engine, avatar_mute, avatar_talk):
    """Run fully real-time mic-based live session."""
    global is_running

    is_talking = False

    def on_audio(data):
        nonlocal is_talking
        if not is_talking:
            is_talking = True

    def on_transcript(text):
        nonlocal is_talking
        is_talking = False

    # Run avatar animation in a thread
    def avatar_loop():
        while is_running:
            try:
                if cv2.getWindowProperty("Avatar", cv2.WND_PROP_VISIBLE) < 1:
                    break
                img = avatar_talk if is_talking else avatar_mute
                cv2.imshow("Avatar", img)
                key = cv2.waitKey(50) & 0xFF
                if key == 27:
                    break
            except:
                break

    avatar_thread = threading.Thread(target=avatar_loop, daemon=True)
    avatar_thread.start()

    try:
        asyncio.run(
            live_engine.live_mic_session(
                on_audio_response=on_audio,
                on_transcript=on_transcript,
            )
        )
    except KeyboardInterrupt:
        pass
    finally:
        is_running = False
        cv2.destroyAllWindows()
        print("Exiting...")

if __name__ == "__main__":
    main()
