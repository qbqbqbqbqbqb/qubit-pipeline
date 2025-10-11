from typing import Optional, List, Dict
from scripts2.core.broker_event_handler import BrokerEventHandler

class PromptManager:
    def __init__(self, 
                 system_instructions: Optional[str] = None,
                 mood: str = "energetic",
                 tone: str = "casual and humorous",
                 interaction_level: str = "high",
                 ):

        self.cached_memories = {"chat_history": [], "reflections": []}
        self.mood = mood
        self.tone = tone
        self.interaction_level = interaction_level
        self.system_instructions = system_instructions or (
            "You are Qubit, an AI Vtuber talking to a chat. "
            "You are feeling {mood}, and talk in a {tone} tone. "
            "You will {interaction_instruction}. "
            "Adapt your response style and tone based on the user's personality traits and relationship score provided in the user context. "
            "Match the user's communication style - if they are sarcastic, respond sarcastically; if aggressive, be direct; etc. "
            "Adjust your friendliness: if relationship score is high (>0.5), be more casual and affectionate; if low (<0.2), be more formal and reserved."
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

    def build_prompt(self, base_prompt: str, user_id: str = None, current_topic: str = None):
        prompt = []
        system_prompt = self.create_system_prompt()
        prompt.append({"role": "system", "content": system_prompt})

        # Add memory context if available
        if hasattr(self, 'memory_module') and self.memory_module:
            context = self.memory_module.get_memory_context(user_id, current_topic)
            if context:
                prompt.append({"role": "system", "content": f"User context:\n{context}"})

        chat_history = self.cached_memories.get("chat_history", [])
        reflections = self.cached_memories.get("reflections", [])

        prompt.append({"role": "system", "content": "Chat history:"})
        prompt.extend(chat_history)
        prompt.append({"role": "system", "content": "Reflections:"})
        prompt.extend(reflections)

        prompt.append({"role": "user", "content": base_prompt})
        return prompt
    
    def handle_memory_update(self, memory_data: Dict):
        """Update internal memory cache when new memory data arrives."""
        self.cached_memories = memory_data
