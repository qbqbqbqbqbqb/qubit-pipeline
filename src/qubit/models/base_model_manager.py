"""Abstract base class for model managers.

This module defines the BaseModelManager interface, which standardises
how different model backends (e.g. Hugging Face) are implemented and used
within the application.
"""

from typing import Any
from abc import ABC, abstractmethod

class BaseModelManager(ABC):
    """Abstract base class for managing language models.

    This class defines the required interface for all model manager
    implementations, including access to the model and tokenizer,
    text generation, and resource cleanup.
    """

    @property
    @abstractmethod
    def model(self: Any) -> Any:
        """Return the underlying model instance.

        Returns:
            Any: The loaded model object.
        """

    @property
    @abstractmethod
    def tokenizer(self: Any) -> Any:
        """Return the tokenizer associated with the model.

        Returns:
            Any: The tokenizer instance used for encoding/decoding text.
        """

    @abstractmethod
    def generate_dialogue(self: Any, prompt: str, max_new_tokens: int) -> str:
        """Generate a response from the model based on a prompt.

        Args:
            prompt (str): Input text prompt for the model.
            max_new_tokens (int): Maximum number of tokens to generate.

        Returns:
            str: Generated text response.
        """

    @abstractmethod
    def unload(self: Any) -> None:
        """Unload the model and free associated resources.

        This method should handle cleanup such as releasing GPU memory
        or deleting model references.
        """
