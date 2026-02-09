from deep_translator import GoogleTranslator
from src.config import Config

def translate_to_eng(text: str) -> str:
    """Translate user input to English (if enabled)."""
    if Config.ENABLE_TRANSLATOR and text.strip():
        try:
            return GoogleTranslator(source='auto', target=Config.USER_LANG).translate(text)
        except Exception as e:
            print(f"[Translation Error] User Input: {e}")
            return text
    return text

def translate_to_local(text: str) -> str:
    """Translate AI response to local language (if enabled)."""
    if Config.ENABLE_TRANSLATOR and text.strip():
        try:
            return GoogleTranslator(source='auto', target=Config.BOT_LANG).translate(text)
        except Exception as e:
            print(f"[Translation Error] AI Output: {e}")
            return text
    return text
