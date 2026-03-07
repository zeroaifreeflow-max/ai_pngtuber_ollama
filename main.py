"""
AI PNGTuber — Gemini Live API (Voice-to-Voice)

Runs two concurrent loops:
  1. Async Gemini Live session (mic → Gemini → speaker)
  2. OpenCV avatar render loop (toggles mute/talk based on audio state)
"""

import asyncio
import threading
import cv2
import sys

from src.config import Config
from src.gemini_live import GeminiLiveSession


def run_avatar_loop(live_session: GeminiLiveSession):
    """OpenCV render loop — runs in a separate thread (blocking)."""
    if not Config.MUTE_IMG_PATH.exists() or not Config.TALK_IMG_PATH.exists():
        print(f"❌ Error: Avatar images not found at {Config.MUTE_IMG_PATH}")
        return

    avatar_mute = cv2.imread(str(Config.MUTE_IMG_PATH))
    avatar_talk = cv2.imread(str(Config.TALK_IMG_PATH))

    cv2.namedWindow("Avatar", cv2.WINDOW_AUTOSIZE)

    while True:
        try:
            if cv2.getWindowProperty("Avatar", cv2.WND_PROP_VISIBLE) < 1:
                break
        except cv2.error:
            break

        # Toggle avatar based on whether Gemini is sending audio
        if live_session.is_speaking:
            cv2.imshow("Avatar", avatar_talk)
        else:
            cv2.imshow("Avatar", avatar_mute)

        key = cv2.waitKey(50) & 0xFF
        if key == 27:  # ESC
            break

    cv2.destroyAllWindows()


def save_subtitle(text: str):
    """Write live transcript to subtitle file for OBS."""
    try:
        with open(Config.SUBS_PATH, "a", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass


async def main():
    live = GeminiLiveSession()
    live.on_subtitle = save_subtitle

    # Start avatar render loop in a background thread
    avatar_thread = threading.Thread(target=run_avatar_loop, args=(live,), daemon=True)
    avatar_thread.start()

    # Run the Gemini Live session (blocks until cancelled or error)
    await live.run()

    print("👋 Exiting...")
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
