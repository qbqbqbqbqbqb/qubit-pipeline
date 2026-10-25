"""
Vision model wrapper.

Supports two local multimodal models selectable via config/settings.py:

  moondream2  — vikhyatk/moondream2 (~1.8GB, fast, basic descriptions)
  llava       — llava-hf/llava-1.5-7b-hf (~4GB 4-bit, richer detail, slower)

The active model is loaded lazily on the first describe() call and held
in memory for the session. Switching models requires a restart.
"""

import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

_VISION_PROMPT = (
    "Describe what is happening on screen in 2-3 sentences. "
    "Focus on what is being played or shown — game state, UI elements, "
    "notable events. Be specific and concise."
)

_model = None
_tokenizer = None
_loaded_name: str | None = None


def load(model_name: str) -> None:
    """Load the named vision model into memory. Called once at startup."""
    global _model, _tokenizer, _loaded_name

    if _loaded_name == model_name:
        return

    logger.info("[vision/models] Loading vision model: %s", model_name)

    if model_name == "moondream2":
        _load_moondream()
    elif model_name == "llava":
        _load_llava()
    else:
        raise ValueError(f"Unknown vision model: {model_name!r}. Choose 'moondream2' or 'llava'.")

    _loaded_name = model_name
    logger.info("[vision/models] Vision model loaded: %s", model_name)


def describe(image: Image.Image) -> str:
    """
    Run the loaded vision model on a PIL Image and return a text description.
    Returns an empty string if no model is loaded or inference fails.
    """
    if _model is None:
        logger.warning("[vision/models] describe() called but no model is loaded")
        return ""

    try:
        if _loaded_name == "moondream2":
            return _describe_moondream(image)
        elif _loaded_name == "llava":
            return _describe_llava(image)
    except Exception as exc:
        logger.error("[vision/models] Inference failed: %s", exc)

    return ""


def _load_moondream() -> None:
    global _model, _tokenizer
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    _tokenizer = AutoTokenizer.from_pretrained(
        "vikhyatk/moondream2",
        revision="2025-01-09",
        trust_remote_code=True,
    )
    _model = AutoModelForCausalLM.from_pretrained(
        "vikhyatk/moondream2",
        revision="2025-01-09",
        trust_remote_code=True,
        torch_dtype=torch.float16,
        device_map="cuda",
    )
    _model.eval()


def _load_llava() -> None:
    global _model, _tokenizer
    from transformers import LlavaForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
    import torch

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    _tokenizer = AutoProcessor.from_pretrained("llava-hf/llava-1.5-7b-hf")
    _model = LlavaForConditionalGeneration.from_pretrained(
        "llava-hf/llava-1.5-7b-hf",
        quantization_config=quantization_config,
        device_map="cuda",
    )
    _model.eval()


def _describe_moondream(image: Image.Image) -> str:
    enc = _model.encode_image(image)
    return _model.answer_question(enc, _VISION_PROMPT, _tokenizer).strip()


def _describe_llava(image: Image.Image) -> str:
    import torch
    conversation = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": _VISION_PROMPT},
            ],
        }
    ]
    prompt = _tokenizer.apply_chat_template(conversation, add_generation_prompt=True)
    inputs = _tokenizer(images=image, text=prompt, return_tensors="pt").to("cuda")
    with torch.no_grad():
        output = _model.generate(
            **inputs,
            max_new_tokens=120,
            do_sample=False,
        )
    decoded = _tokenizer.decode(output[0], skip_special_tokens=True)
    # LLaVA echoes the prompt — strip everything up to and including "ASSISTANT:"
    if "ASSISTANT:" in decoded:
        return decoded.split("ASSISTANT:")[-1].strip()
    return decoded.strip()