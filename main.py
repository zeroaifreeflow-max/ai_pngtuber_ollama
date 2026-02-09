import threading
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
    print("\n💬 Type your message (Ctrl+C to quit):")
    while is_running:
        try:
            text = input()
            if text.strip():
                input_queue.put(text.strip())
        except (EOFError, KeyboardInterrupt):
            is_running = False
            break

def main():
    global is_running
    
    # 1. Setup Avatar Window
    if not Config.MUTE_IMG_PATH.exists() or not Config.TALK_IMG_PATH.exists():
        print(f"❌ Error: Avatar images not found at {Config.MUTE_IMG_PATH}")
        return

    avatar_mute = cv2.imread(str(Config.MUTE_IMG_PATH))
    avatar_talk = cv2.imread(str(Config.TALK_IMG_PATH))
    
    cv2.namedWindow("Avatar", cv2.WINDOW_AUTOSIZE)
    
    # 2. Initialize AI
    print("🤖 Initializing AI Engine...")
    ai = AIEngine()
    
    # 3. Start Input Thread
    t = threading.Thread(target=input_listener, daemon=True)
    t.start()
    
    print("✅ System Ready! Talk to your PngTuber now.")

    # 4. Main Event Loop
    while is_running:
        try:
            # Check Window Status
            if cv2.getWindowProperty("Avatar", cv2.WND_PROP_VISIBLE) < 1:
                is_running = False
                break
            
            # Process Input
            if not input_queue.empty():
                user_msg = input_queue.get()
                
                # AI Logic
                print(f"User: {user_msg}")
                response = ai.generate_response(user_msg)
                print(f"AI: {response}")
                
                # Audio & Animation
                generate_voice(response)
                play_audio_and_animate(avatar_mute, avatar_talk, "Avatar")
                
                print("\n💬 Type your message:")

            # Render Idle State
            cv2.imshow("Avatar", avatar_mute)
            
            # 20ms delay for 50fps UI update
            key = cv2.waitKey(20) & 0xFF
            if key == 27: # ESC
                is_running = False
                break
                
        except KeyboardInterrupt:
            is_running = False
            break
            
    # Cleanup
    cv2.destroyAllWindows()
    print("👋 Exiting...")
    sys.exit()

if __name__ == "__main__":
    main()
