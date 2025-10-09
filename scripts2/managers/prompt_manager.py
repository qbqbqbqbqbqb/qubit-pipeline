from typing import Optional, List, Dict

class PromptManager:
    def __init__(self, system_instructions: Optional[str] = None):
        self.system_instructions = system_instructions

    def build_prompt(self, base_prompt: str, chat_history: Optional[list] = None):
        prompt = [
            {"role": "system", "content": self.system_instructions}
        ]

        if chat_history:
            prompt.extend(chat_history)

        prompt.append({"role": "user", "content": base_prompt})

        return prompt
