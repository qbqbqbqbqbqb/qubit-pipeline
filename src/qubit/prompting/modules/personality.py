"""Prompt injection module for defining AI personality traits."""

from typing import Literal
from src.qubit.prompting.injections import PromptInjection

# TODO: can we use the interaction level passed into here to control priorities on the cognitive layer too?
# i forget where its passed from rn 
def personality_module(
    mood: str = "energetic",
    tone: str = "casual and humorous",
    interaction_level: Literal["low", "medium", "high"] = "high",
    ) -> PromptInjection:
    """
    Create a prompt injection that defines the AI's personality.

    This includes mood, tone, and how actively the AI should
    interact with the audience.

    Args:
        mood (str): The AI's emotional state (e.g., "energetic").
        tone (str): The communication style (e.g., "casual and humorous").
        interaction_level (str): Level of audience interaction.
            Expected values are "low", "medium", or "high".

    Returns:
        PromptInjection: A configured personality prompt injection.
    """
    
    interaction_instruction = {
        "low": "Focus mostly on monologue style, little audience interaction.",
        "medium": "Engage with the audience occasionally, reacting to chat.",
        "high": ("Frequently interact with the audience, asking questions, "
                 "responding to chat, and making jokes about chat messages.")
    }[interaction_level]
        
    return PromptInjection(
        content = (
        f"You are feeling {mood}, and talk in a {tone} tone.\n"
        f"{interaction_instruction}\n"
    ),
        priority=90
    )