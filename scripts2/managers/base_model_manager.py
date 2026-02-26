from abc import ABC, abstractmethod

class BaseModelManager(ABC):
    @property
    @abstractmethod
    def _model(self):
        pass

    @property
    @abstractmethod
    def tokeniser(self):
        pass

    @abstractmethod
    def generate_dialogue(self, prompt: str, max_new_tokens: int = 512) -> str:
        pass