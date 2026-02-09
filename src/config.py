import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load Environment Files
load_dotenv(BASE_DIR / 'env/chatbot.env')
load_dotenv(BASE_DIR / 'env/avatar.env')
load_dotenv(BASE_DIR / 'env/translator.env')
load_dotenv(BASE_DIR / 'env/voice.env')

class Config:
    # --- Paths ---
    BASE_DIR = BASE_DIR
    LORE_PATH = BASE_DIR / "res/content/lore.txt"
    SUBS_PATH = BASE_DIR / "res/content/subs.txt"
    MEMORY_PATH = BASE_DIR / "res/content/memory.json"
    AUDIO_OUTPUT_PATH = BASE_DIR / "res/sound/output.mp3"
    
    # --- Avatar Images ---
    MUTE_IMG_PATH = BASE_DIR / str(os.getenv('MUTE_IMG', '/res/img/avatar_mute.png')).strip('/')
    TALK_IMG_PATH = BASE_DIR / str(os.getenv('TALK_IMG', '/res/img/avatar_talk.png')).strip('/')

    # --- AI Settings ---
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    CHAT_MODEL = os.getenv('CHAT_MODEL', 'gemini-2.0-flash')

    # --- Translation Settings ---
    ENABLE_TRANSLATOR = int(os.getenv('TRANSLATOR', '0')) == 1
    USER_LANG = os.getenv('USER_LANG_TRANSLATE', 'en')
    BOT_LANG = os.getenv('CHATBOT_LANG', 'th')

    # --- Voice Settings ---
    USE_GTTS = int(os.getenv('TTS', '1')) == 1
    GTTS_LANG = os.getenv('GTTS_LANG', 'th')
    ELEVENLABS_URL = os.getenv('URL_ELEVENLAB', 'https://api.elevenlabs.io/v1/text-to-speech/')
    ELEVENLABS_KEY = os.getenv('API_KEY_ELEVENLAB', '')
    ELEVENLABS_VOICE_ID = os.getenv('VOICE_ID', '')
