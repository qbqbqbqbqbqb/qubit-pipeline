from abc import ABC, abstractmethod


class BaseModelManager(ABC):

    @property
    @abstractmethod
    def model(self):
        pass

    @property
    @abstractmethod
    def tokenizer(self):
        pass

    @abstractmethod
    def generate_dialogue(self, prompt: str, max_new_tokens: int):
        pass

    @abstractmethod
    def unload(self):
        pass