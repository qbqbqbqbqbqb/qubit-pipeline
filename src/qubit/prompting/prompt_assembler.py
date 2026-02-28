

from src.qubit.prompting.injections import PromptInjection


"""
Assembles the final prompt to send to the LLM by combining multiple PromptInjections.
Injections can be added with different priorities to control their order in the final prompt.
"""
class PromptAssembler:

    def __init__(self):
        self.injections = []

    def add(self, injection: PromptInjection):
        self.injections.append(injection)

    def build(self) -> str:
        sorted_injections = sorted(
            self.injections,
            key=lambda x: x.priority,
            reverse=True
        )

        return "\n\n".join(inj.content for inj in sorted_injections)
    
