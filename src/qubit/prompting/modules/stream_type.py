
from src.qubit.prompting.injections import PromptInjection

def stream_type_module(

):
    STREAM_TYPE = "Just Chatting"
    content = (
        f"You are doing a {STREAM_TYPE} stream."
    )

    return PromptInjection(
        content=content,
        priority=80
    )