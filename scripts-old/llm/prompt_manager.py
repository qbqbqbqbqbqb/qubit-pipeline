from typing import List, Tuple, Optional

class PromptManager:
    """
    Manages prompt construction and chat history for AI conversations.

    Builds structured prompts for the Llama model using conversation history,
    system instructions, and memory context. Handles chat history management
    with automatic trimming to prevent memory overflow.

    Supports customizable mood, tone, and interaction levels for dynamic
    personality adaptation.
    """

    def __init__(
        self,
        system_instructions: Optional[str] = None,
        max_history: int = 8,
        default_mood: str = "energetic",
        default_tone: str = "casual and humorous",
        default_interaction: str = "high",
    ):
        """
        Initialize the PromptManager with optional system instructions and default parameters.

        Args:
            system_instructions (Optional[str]): Template string with placeholders for mood, tone, and interaction instructions.
            max_history (int): Maximum number of chat history entries to retain.
            default_mood (str): Default mood descriptor for prompt generation.
            default_tone (str): Default tone/style descriptor for prompt generation.
            default_interaction (str): Default level of audience interaction ("low", "medium", or "high").
        """
        
        self.system_instructions = system_instructions
        self.max_history = max_history
        self.default_mood = default_mood
        self.default_tone = default_tone
        self.default_interaction = default_interaction
        
        self.chat_history: List[Tuple[str, str]] = []
    
    def add_user(self, content: str) -> None:
        """
        Add a user message to the chat history.
        """
        self.chat_history.append(("user", content))
        self._trim_history()
    
    def add_bot(self, content: str) -> None:
        """
        Add a bot message to the chat history.
        """
        self.chat_history.append(("assistant", content))
        self._trim_history()
    
    def build_prompt(self, base_prompt: str,
                    mood: str = "laid-back",
                    interaction_level: str = "high",
                    tone: str = "casual, funny, and edgy",
                    memory_context: str = "",
                    user_id: str = None
    ) -> List[dict]:
        """
        Builds a chat-style prompt using Llama-3-Instruct format for Sao10K model.
        Includes memory context for personalized responses.

        Args:
            base_prompt (str): The main idea to talk about.
            mood (str): Mood descriptor for the model's voice.
            interaction_level (str): Level of interaction with the audience.
            tone (str): Style or personality tone for the generation.
            memory_context (str): Additional context from memory system.
            user_id (str): User ID for personalized context.

        Returns:
            List[dict]: Chat messages in Llama-3-Instruct format.
        """

        chat_messages = []
        for role, content in self.chat_history[-self.max_history:]:
            chat_messages.append({"role": role, "content": content})

        interaction_instruction = {
            "low": "Focus mostly on monologue style, little audience interaction.",
            "medium": "Engage with the audience occasionally, reacting to chat.",
            "high": "Frequently interact with the audience, asking questions, "
                    "responding to chat, and making jokes about chat messages."
        }.get(interaction_level, "Frequently interact with the audience.")

        system_prompt = self.system_instructions.format(
            mood=mood,
            tone=tone,
            interaction_instruction=interaction_instruction
        )

        if memory_context:
            system_prompt += f"\n\nMemory Context:\n{memory_context}"

        chat_messages.insert(0, {"role": "system", "content": system_prompt})

        history_text = ""
        if self.chat_history:
            history_text = "\n".join(f"{role}: {content}" for role, content in self.chat_history[-3:])
            history_text = f"\nRecent chat history:\n{history_text}\n"

        current_prompt = f"{history_text}Now talk about: {base_prompt}"

        if user_id:
            current_prompt += f"\n\nResponding to user: {user_id}"

        chat_messages.append({"role": "user", "content": current_prompt})

        return chat_messages

    def _trim_history(self) -> None:
        """
        Trim the chat history to ensure it does not exceed max_history entries.
        """
        if len(self.chat_history) > self.max_history:
            excess = len(self.chat_history) - self.max_history
            self.chat_history = self.chat_history[excess:]