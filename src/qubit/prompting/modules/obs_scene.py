"""Prompt injection module for current OBS scene context."""

from src.qubit.prompting.injections import PromptInjection


def obs_scene_module(scene_name: str | None) -> PromptInjection | None:
    """
    Returns a PromptInjection with the current OBS scene name, or None if
    no scene is known yet. Priority 75 — after stream type, before chat history.

    Keeps it minimal — just tells the model which scene is active so it can
    adapt tone (e.g. quieter during a BRB scene, engaged during gameplay).
    """
    if not scene_name:
        return None

    return PromptInjection(
        content=f"Current OBS scene: {scene_name}.",
        priority=75,
    )