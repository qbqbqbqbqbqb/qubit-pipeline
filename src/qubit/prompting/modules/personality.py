
from src.qubit.prompting.injections import PromptInjection

"""
    Args:
        mood: The AI's mood, e.g., "energetic".
        tone: The AI's tone, e.g., "casual and humorous".
        interaction_level: How much the AI interacts with chat ("low", "medium", "high").
        """


def personality_module(
    mood: str = "energetic",
    tone: str = "casual and humorous",
    interaction_level: str = "high"
):
    
    interaction_instruction = {
        "low": "Focus mostly on monologue style, little audience interaction.",
        "medium": "Engage with the audience occasionally, reacting to chat.",
        "high": "Frequently interact with the audience, asking questions, responding to chat, and making jokes about chat messages."
    }.get(interaction_level, "Frequently interact with the audience.")
        
    return PromptInjection(
        content = (
        f"You are feeling {mood}, and talk in a {tone} tone.\n"
        f"{interaction_instruction}\n"
    ),
        priority=80
    )