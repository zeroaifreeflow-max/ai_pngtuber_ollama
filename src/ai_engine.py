import os
import google.generativeai as genai
from src.config import Config
from src.translation import translate_to_eng, translate_to_local
from src.memory import get_memory_context, update_memory

class AIEngine:
    def __init__(self):
        self.model = None
        self.chat_session = None
        self.base_lore = ""
        self._initialize()

    def _initialize(self):
        """Initialize Gemini API and load lore/memory."""
        if not Config.GEMINI_API_KEY or "YOUR_GEMINI_API_KEY" in Config.GEMINI_API_KEY:
            print("❌ Error: GEMINI_API_KEY is missing.")
            return

        # Load Lore
        if Config.LORE_PATH.exists():
            with open(Config.LORE_PATH, 'r', encoding='utf-8') as f:
                self.base_lore = f.read().strip()
        
        # Combine Lore + Memory
        memory_context = get_memory_context()
        system_instruction = f"{self.base_lore}\n\n{memory_context}"

        print(f"🧠 AI Initialized. Memory loaded.")

        # Configure API
        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            
            self.model = genai.GenerativeModel(
                model_name=Config.CHAT_MODEL,
                system_instruction=system_instruction,
                generation_config={
                    "temperature": 1.0,
                    "max_output_tokens": 1024,
                },
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                ]
            )
            self.chat_session = self.model.start_chat(history=[])
            
        except Exception as e:
            print(f"❌ Gemini Connection Failed: {e}")

    def generate_response(self, user_text: str) -> str:
        """Main function to process user input and return AI response."""
        if not self.chat_session:
            return "Error: AI not initialized."

        try:
            # 1. Translate Input
            translated_text = translate_to_eng(user_text)
            
            # 2. Check for Image Paths (Multimodal)
            content = [translated_text]
            for word in translated_text.split():
                if word.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and os.path.exists(word):
                    print(f"📸 Uploading image: {word}")
                    img_file = genai.upload_file(word)
                    content.append(img_file)

            # 3. Generate Response
            response = self.chat_session.send_message(content)
            ai_text_eng = response.text if response.text else "..."

            # 4. Background Memory Analysis
            self._analyze_memory(translated_text, ai_text_eng)

            # 5. Translate Output & Save Subs
            final_text = translate_to_local(ai_text_eng)
            self._save_subs(final_text)
            
            return final_text

        except Exception as e:
            print(f"⚠️ Generation Error: {e}")
            return "..."

    def _analyze_memory(self, user_input, ai_output):
        """Extract facts using a lightweight call."""
        try:
            analyzer = genai.GenerativeModel(model_name=Config.CHAT_MODEL)
            prompt = f"""
            Extract 1 important fact about the user from this chat. If none, return NO_DATA.
            User: {user_input}
            AI: {ai_output}
            Output format: Fact string only.
            """
            res = analyzer.generate_content(prompt)
            fact = res.text.strip()
            if fact and "NO_DATA" not in fact:
                print(f"📝 Memorized: {fact}")
                update_memory("facts", "", fact)
        except:
            pass

    def _save_subs(self, text):
        try:
            with open(Config.SUBS_PATH, 'w', encoding='utf-8') as f:
                f.write(text)
        except:
            pass
