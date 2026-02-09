import requests
import pygame
import cv2
import sys
from gtts import gTTS
from src.config import Config

# Initialize Pygame Mixer
try:
    pygame.mixer.init()
    pygame.mixer.set_num_channels(8)
except Exception:
    pass

def generate_voice(text: str) -> None:
    """Generate audio file from text using gTTS or ElevenLabs."""
    if not text.strip():
        return

    try:
        if Config.USE_GTTS:
            tts = gTTS(text=text, lang=Config.GTTS_LANG, slow=False)
            tts.save(str(Config.AUDIO_OUTPUT_PATH))
        else:
            # ElevenLabs Implementation
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": Config.ELEVENLABS_KEY
            }
            data = {
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {"stability": 0.43, "similarity_boost": 0.76}
            }
            url = f"{Config.ELEVENLABS_URL}{Config.ELEVENLABS_VOICE_ID}"
            response = requests.post(url, json=data, headers=headers)
            
            with open(Config.AUDIO_OUTPUT_PATH, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        print(f"[Audio Error] Generation failed: {e}")

def play_audio_and_animate(mute_img, talk_img, window_name="Avatar"):
    """Play the generated audio and animate the avatar lipsync."""
    if not Config.AUDIO_OUTPUT_PATH.exists():
        return

    try:
        voice_channel = pygame.mixer.Channel(1)
        sound = pygame.mixer.Sound(str(Config.AUDIO_OUTPUT_PATH))
        voice_channel.play(sound)

        # Animation Loop
        while voice_channel.get_busy():
            # Check if window is closed to avoid crash
            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    sys.exit()
            except: 
                break

            cv2.imshow(window_name, talk_img)
            cv2.waitKey(100) # Simple lip flap delay
            
        # Return to mute state
        cv2.imshow(window_name, mute_img)
        cv2.waitKey(20)
        
    except Exception as e:
        print(f"[Audio Error] Playback failed: {e}")
