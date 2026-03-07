from src.qubit.prompting.injections import PromptInjection

def chat_memory_module(recent_history: list) -> PromptInjection:
    if not recent_history:
        return None

    history_str = "\n".join([f"{item['role']}: {item['content']}" for item in recent_history[-10:]])
    memory_text = f"Chat History:\n{history_str}" if history_str else ""
    return PromptInjection(
        content=memory_text,
        priority=70
    )