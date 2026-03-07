from src.qubit.prompting.injections import PromptInjection

def reflection_memory_module(recent_reflections: list) -> PromptInjection:
    if not recent_reflections:
        return None

    reflections_str = "\n".join([item['content'] for item in recent_reflections])
    
    memory_text = f"Recent reflections:\n{reflections_str}" if reflections_str else ""

    return PromptInjection(
        content=memory_text,
        priority=60
    )