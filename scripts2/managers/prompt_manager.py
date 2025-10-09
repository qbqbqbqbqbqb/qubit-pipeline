from typing import Optional, List, Dict

class PromptManager:
    def __init__(self, 
                 system_instructions: Optional[str] = None,
                 mood: str = "energetic",
                 tone: str = "casual and humorous",
                 interaction_level: str = "high",
                 ):

        self.mood = mood
        self.tone = tone
        self.interaction_level = interaction_level
        self.system_instructions = system_instructions or (
            "You are Qubit, an AI Vtuber talking to a chat. "
            "You are feeling {mood}, and talk in a {tone} tone. "
            "You will {interaction_instruction}"
        )

    def create_system_prompt(self):
        interaction_instruction = {
            "low": "Focus mostly on monologue style, little audience interaction.",
            "medium": "Engage with the audience occasionally, reacting to chat.",
            "high": "Frequently interact with the audience, asking questions, "
                    "responding to chat, and making jokes about chat messages."
        }.get(self.interaction_level, "Frequently interact with the audience.")

        system_prompt = self.system_instructions.format(
            mood=self.mood,
            tone=self.tone,
            interaction_instruction=interaction_instruction
        )

        return system_prompt

    def build_prompt(self, 
                     base_prompt: str, 
                     chat_history: Optional[list] = None):

        prompt = []        
        system_prompt = self.create_system_prompt()
        prompt.insert(0, {"role": "system", "content": system_prompt})
        prompt.append({"role": "user", "content": base_prompt})

        return prompt
