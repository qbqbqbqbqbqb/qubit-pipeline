from typing import Optional, List, Dict
from scripts2.modules.memory_module import MemoryModule

class PromptManager:
    def __init__(self, 
                 system_instructions: Optional[str] = None,
                 mood: str = "energetic",
                 tone: str = "casual and humorous",
                 interaction_level: str = "high",
                 memory_module: MemoryModule = None
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
                     base_prompt: str):

        prompt = []        
        system_prompt = self.create_system_prompt()
        prompt.insert(0, {"role": "system", "content": system_prompt})

        if self.memory_module:
            recent_memories = self.memory_module.get_recent_memories()
            chat_history = recent_memories.get("chat_history", [])
            reflections = recent_memories.get("reflections", [])

            prompt.append({"role": "system", "content": "Chat history:"})
            prompt.extend(chat_history)
            prompt.append({"role": "system", "content": "Reflections:"})
            prompt.extend(reflections)

        prompt.append({"role": "user", "content": base_prompt})

        return prompt
