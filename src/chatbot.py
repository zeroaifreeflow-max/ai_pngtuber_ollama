import os
import traceback
import google.generativeai as genai
import pygame
from pathlib import Path
from dotenv import load_dotenv
from src.translator import translate_chatbot, translate_user

pygame.init()

dotenv_path_chatbot = Path(str(Path().resolve())+'/env/chatbot.env')
load_dotenv(dotenv_path=dotenv_path_chatbot)

PATH_LORE:str = str(Path(str(Path().resolve())+str(os.getenv('PATH_LORE'))))
PATH_SUBS:str = str(Path(str(Path().resolve())+str(os.getenv('PATH_SUBS'))))
GEMINI_API_KEY:str = os.getenv('GEMINI_API_KEY')
CHAT_MODEL:str = os.getenv('CHAT_MODEL')

lore:str = "" 
model = None

def initialize() -> None:
    """Function that initializes the project, the chatbot, and verifies the API connection."""
    global lore
    global model

    # 1. Load Lore
    try:
        if os.path.exists(PATH_LORE):
            with open(PATH_LORE, 'r', encoding='utf-8') as file:
                lore = file.read()
            # Clean up lore slightly but keep structure as Gemini handles it well
            lore = lore.strip()
        else:
            print(f"Warning: Lore file not found at {PATH_LORE}")
    except Exception:
        print("Error when reading lore.txt")
        print(traceback.format_exc())

    # 2. Configure Gemini API
    if not GEMINI_API_KEY or "YOUR_GEMINI_API_KEY" in GEMINI_API_KEY:
        print("\nCRITICAL ERROR: GEMINI_API_KEY is missing or invalid in env/chatbot.env")
        print("Please open env/chatbot.env and paste your Google AI Studio API Key.\n")
        return

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Initialize Model with System Instruction (Lore)
        # This is more powerful than sending it as a user message
        model = genai.GenerativeModel(
            model_name=CHAT_MODEL,
            system_instruction=lore
        )

        # 3. Test Connection
        print(f"Connecting to Google Gemini API ({CHAT_MODEL})...")
        # Generate a trivial token to test auth and connectivity
        model.count_tokens("System Check")
        print("✅ Connection to Gemini API established successfully!")

    except Exception as e:
        print("\n❌ Failed to connect to Gemini API.")
        print(f"Error details: {e}")
        print("Check your Internet connection and API Key.\n")

    pygame.mixer.init()
    pygame.mixer.set_num_channels(8)
        
def generationPrompt(user_message:str) -> str:
    """Function that generates a response using Gemini API.

    Args:
        user_message (str): The user message to discuss with the chatbot.

    Returns:
        str: The answer of the chatbot
    """
    global model

    if model is None:
        return "Error: AI Model is not initialized. Check your API Key."

    try:
        # 1. Translate User Input (if enabled)
        user_message_translate:str = translate_user(user_message)
        print(f"User (Translated): {user_message_translate}")
        
        print("\n[Gemini] Generating response...")
        
        # 2. Generate Content
        # We assume stateless interaction here as per original design (one-shot response)
        # If history is needed, we would use model.start_chat()
        response = model.generate_content(user_message_translate)
        
        print("[Gemini] Response received!")

        # 3. Extract Text
        # Handle cases where response might be blocked due to safety settings
        if response.parts:
            ai_text_response = response.text
        else:
            # Fallback if safety filters blocked the response
            print("Warning: Response was blocked by safety filters.")
            try: 
                 print(f"Safety Ratings: {response.prompt_feedback}")
            except:
                 pass
            return "..."

        # 4. Translate AI Output (if enabled)
        chatbot_message:str = translate_chatbot(ai_text_response)
        
        # 5. Write to Subtitles
        with open(PATH_SUBS, "w", encoding='utf-8') as subs:
            subs.write(chatbot_message)
            
        return chatbot_message

    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        print(error_msg)
        return "..."