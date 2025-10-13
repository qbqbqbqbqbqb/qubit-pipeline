from typing import Optional, List, Dict
from scripts2.core.broker_event_handler import BrokerEventHandler
from datetime import datetime
from scripts2.rag.chat_history_manager import ChatHistoryManager
from scripts2.utils.filter_utils import contains_banned_words
from scripts2.config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST

"""Prompt Manager Module

This module provides the PromptManager class for managing system prompts and
building comprehensive prompts for AI responses in an AI Vtuber system. It handles
dynamic prompt creation based on mood, tone, interaction level, and integrates
memory context, chat history, and reflections to generate contextually appropriate
responses.
"""

class PromptManager:
    """Manages the creation of system prompts and building of full prompts for AI responses.

    The PromptManager handles dynamic prompt generation based on configured mood, tone,
    and interaction level. It integrates memory context, chat history, and reflections
    to provide comprehensive prompts that adapt to user interactions and system state.
    """

    def __init__(self, 
                 system_instructions: Optional[str] = None,
                 mood: str = "energetic",
                 tone: str = "casual and humorous",
                 interaction_level: str = "high",
                 chat_history_manager = None
                 ):

        """Initialize the PromptManager with configuration parameters.

        Args:
            system_instructions (Optional[str]): Custom system instructions. If None,
                uses default Qubit AI Vtuber instructions.
            mood (str): The mood of the AI (e.g., "energetic"). Defaults to "energetic".
            tone (str): The tone of responses (e.g., "casual and humorous").
                Defaults to "casual and humorous".
            interaction_level (str): Level of audience interaction ("low", "medium", "high").
                Defaults to "high".
        """

        self.cached_memories = {"chat_history": [], "reflections": []}
        self.mood = mood
        self.chat_history_manager = chat_history_manager
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
        """Create the system prompt based on current configuration.

        Returns:
            str: The formatted system prompt incorporating mood, tone, and interaction level.
        """
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

    def build_prompt(self, base_prompt: str, user_id: str = None, current_topic: str = None, original_type=None):
        prompt = []
        
        system_prompt = self.create_system_prompt()
        prompt.append({"role": "system", "content": system_prompt})

        if hasattr(self, 'memory_module') and self.memory_module:
            context = self.memory_module.get_memory_context(user_id, current_topic)
            if context:
                prompt.append({"role": "system", "content": context})

        recent_memories = self.chat_history_manager.get_recent_memories(limit_chat=15, limit_reflections=2)
        chat_history = recent_memories["chat_history"]
        reflections = recent_memories["reflections"]

        for message in chat_history:
            metadata = message["metadata"]
            if message["role"] == "user":
                user_id = message.get("user_id", "unknown")
                if not user_id or contains_banned_words(user_id, 
                                        blacklist=BLACKLISTED_WORDS_LIST, 
                                        whitelist=WHITELISTED_WORDS_LIST):
                    user_id = "Someone"
                content = f"{user_id} says {message['content']}"
            else:
                content = message["content"]

            print(content)
            print(message["role"])
            prompt.append({
                "role": message["role"],
                "content": content
            })

            """         
            for reflection in reflections:
            prompt.append({
                "role": "system",
                "content": f"Note to self: {reflection['content']}"
            }) """

        if original_type == "twitch_chat":
            if not user_id or contains_banned_words(user_id, 
                                     blacklist=BLACKLISTED_WORDS_LIST, 
                                     whitelist=WHITELISTED_WORDS_LIST):
                user_id == "Someone"
            prompt.append({"role": "user", "content": f"{user_id} says {base_prompt}"})
        else:
            prompt.append({"role": "user", "content": base_prompt})

        return prompt
    
    def handle_memory_update(self, memory_data: Dict):
        """Update the internal memory cache with new memory data.

        Args:
            memory_data (Dict): Dictionary containing 'chat_history' and 'reflections' lists.
        """
        self.cached_memories = memory_data