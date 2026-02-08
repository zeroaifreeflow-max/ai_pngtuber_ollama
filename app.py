import threading
import queue
import cv2
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from src.chatbot import generationPrompt, initialize
from src.vtuberVoice import text_to_speech, talking

# Load Environment
dotenv_path_avatar = Path(str(Path().resolve())+'/env/avatar.env')
load_dotenv(dotenv_path=dotenv_path_avatar)

MUTE_IMG_PATH = str(Path(str(Path().resolve())+str(os.getenv('MUTE_IMG'))))
TALK_IMG_PATH = str(Path(str(Path().resolve())+str(os.getenv('TALK_IMG'))))

# Load Images
avatar_mute = cv2.imread(MUTE_IMG_PATH)
avatar_talk = cv2.imread(TALK_IMG_PATH)

if avatar_mute is None or avatar_talk is None:
    print("Error: Could not load avatar images. Check paths in env/avatar.env")
    sys.exit(1)

# Global Flags & Queue
input_queue = queue.Queue()
is_running = True
is_talking = False

def input_thread_func():
    """Thread function to handle user input without blocking the UI."""
    global is_running
    print("\nType your message and press Enter (Ctrl+C to quit):")
    while is_running:
        try:
            user_message = input()
            if user_message.strip():
                input_queue.put(user_message.strip())
        except (EOFError, KeyboardInterrupt):
            is_running = False
            break

def process_response(user_message):
    """Process AI generation and TTS."""
    global is_talking
    
    # 1. AI Generation
    response = generationPrompt(user_message)
    print(f"\nAI: {response}")
    
    # 2. TTS Generation
    text_to_speech(response)
    
    # 3. Talking Animation (Block Main Loop temporarily for sync)
    # We use a custom talking function here or modify the existing one.
    # To keep it simple with existing vtuberVoice logic, we call talking()
    # But talking() in vtuberVoice has its own loop which is fine.
    talking()

def main():
    global is_running
    
    # Initialize AI
    initialize()
    
    # Start Input Thread
    input_thread = threading.Thread(target=input_thread_func, daemon=True)
    input_thread.start()

    # Create Window explicitly
    cv2.namedWindow("Avatar", cv2.WINDOW_AUTOSIZE)
    print("System Ready. Avatar window is active.")

    while is_running:
        # Check if window is closed
        try:
            if cv2.getWindowProperty("Avatar", cv2.WND_PROP_VISIBLE) < 1:
                is_running = False
                break
        except Exception:
            is_running = False
            break

        # Check for new input
        if not input_queue.empty():
            msg = input_queue.get()
            process_response(msg)
            print("\nType your message and press Enter (Ctrl+C to quit):")
        
        # Default State: Show Mute Avatar
        # (Note: talking() function manages the talking animation loop internally)
        cv2.imshow("Avatar", avatar_mute)
        
        # Refresh UI (Important to prevent freezing)
        key = cv2.waitKey(20) & 0xFF
        if key == 27: # ESC to exit
            is_running = False
            break

    # Cleanup
    is_running = False
    cv2.destroyAllWindows()
    print("\nExiting...")
    sys.exit()

if __name__ == "__main__":
    main()