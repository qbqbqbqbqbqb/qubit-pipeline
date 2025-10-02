from typing import List, Tuple, Optional

class PromptManager:
    def __init__(
        self,
        system_instructions: Optional[str] = None,
        max_history: int = 8,
        default_mood: str = "energetic",
        default_tone: str = "casual and humorous",
        default_interaction: str = "high",
    ):
        self.system_instructions = system_instructions
        self.max_history = max_history
        self.default_mood = default_mood
        self.default_tone = default_tone
        self.default_interaction = default_interaction
        
        self.chat_history: List[Tuple[str, str]] = []
    
    def add_user(self, content: str) -> None:
        self.chat_history.append(("user", content))
        self.trim_history()
    
    def add_bot(self, content: str) -> None:
        self.chat_history.append(("vtuber", content))
        self.trim_history()
    
    def trim_history(self) -> None:
        if len(self.chat_history) > self.max_history:
            excess = len(self.chat_history) - self.max_history
            self.chat_history = self.chat_history[excess:]
    
    def build_prompt(self, base_prompt: str,
                    mood: str = "energetic", 
                    interaction_level: str = "high", 
                    tone: str = "casual and humorous",
    ) -> List[dict]:
        """
        Builds a full prompt for generating streamer-style responses using a base prompt,
        a prompt template, and recent chat history.

        Args:
            base_prompt (str): The main idea to talk about.
            mood (str): Mood descriptor for the model's voice.
            interaction_level (str): Level of interaction with the audience.
            tone (str): Style or personality tone for the generation.
            
        Returns:
            str: A formatted prompt to send to the language model.
        """

        history_text = "".join(f"{role}: {content}\n" for role, content in self.chat_history)

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

        full_prompt = f"{system_prompt}\nChat History:\n{history_text}Now talk about: {base_prompt}"

        return [
            {"role": "user", "content": [{"type": "text", "text": full_prompt}]},
            {"role": "Vtuber", "content": []}
        ]
