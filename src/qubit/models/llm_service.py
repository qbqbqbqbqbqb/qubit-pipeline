"""LLMService — central orchestrator for multiple LLM profiles.

This is the main interface most of the application should use for text generation.
It supports multiple named profiles (main chat, reflection, monologue, etc.),
each with its own model, prompt formatter, and generation defaults.
"""

import asyncio
from typing import Any, Dict, Optional, Union, List

from src.qubit.models.llm_profile import LLMProfile, GenerationOverrides
from src.qubit.models.hf_model_manager import HuggingFaceModelManager
from src.qubit.models.prompt_formatters import get_formatter
from src.qubit.models.model_config import GenerationConfig
from src.utils.log_utils import get_logger

logger = get_logger(__name__)


class LLMService:
    """High-level service for model-agnostic generation across multiple profiles.

    Usage:
        service = LLMService()
        service.load_profile("main")           # or load all known profiles
        response = await service.generate("main", prompt_text_or_messages, max_new_tokens=150)
    """

    def __init__(self):
        self._profiles: Dict[str, LLMProfile] = {}
        self._managers: Dict[str, HuggingFaceModelManager] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------ #
    # Profile management
    # ------------------------------------------------------------------ #

    def register_profile(self, profile: LLMProfile) -> None:
        """Register (but do not yet load) a profile definition."""
        self._profiles[profile.key] = profile
        if profile.key not in self._locks:
            self._locks[profile.key] = asyncio.Lock()

    def get_profile(self, key: str) -> LLMProfile:
        if key not in self._profiles:
            raise KeyError(f"Unknown LLM profile: {key}")
        return self._profiles[key]

    def list_profiles(self) -> List[str]:
        return list(self._profiles.keys())

    async def load_profile(self, key: str) -> HuggingFaceModelManager:
        """Load the underlying model for a profile (idempotent).

        If another profile with an identical underlying model (same model_name + lora_path + quant)
        is already loaded, the manager is shared to avoid loading the same weights twice.
        """
        if key not in self._profiles:
            raise KeyError(f"Cannot load unknown profile: {key}")

        async with self._locks[key]:
            if key in self._managers:
                return self._managers[key]

            profile = self._profiles[key]

            # Simple deduplication: reuse manager if the core model identity matches an already-loaded one
            for existing_key, existing_mgr in self._managers.items():
                existing_prof = self._profiles[existing_key]
                if self._same_model_identity(profile.config, existing_prof.config):
                    logger.info("[LLMService] Reusing already-loaded manager for profile '%s' (same model as '%s')", key, existing_key)
                    self._managers[key] = existing_mgr
                    return existing_mgr

            logger.info("[LLMService] Loading profile '%s' -> %s", key, profile.config.model_name)

            try:
                manager = HuggingFaceModelManager(profile.config)
            except Exception as e:
                logger.error("[LLMService] Failed to load profile '%s': %s", key, e)
                raise

            self._managers[key] = manager
            return manager

    def _same_model_identity(self, a, b) -> bool:
        """Return True if two ModelConfigs point to the exact same underlying model weights."""
        return (
            getattr(a, "model_name", None) == getattr(b, "model_name", None)
            and getattr(a, "lora_path", None) == getattr(b, "lora_path", None)
            and getattr(a, "load_in_4bit", False) == getattr(b, "load_in_4bit", False)
            and getattr(a, "load_in_8bit", False) == getattr(b, "load_in_8bit", False)
        )

    async def ensure_loaded(self, key: str) -> HuggingFaceModelManager:
        """Return the loaded manager, loading it if necessary."""
        if key in self._managers:
            return self._managers[key]
        return await self.load_profile(key)

    def unload_profile(self, key: str) -> None:
        if key in self._managers:
            self._managers[key].unload()
            del self._managers[key]
            logger.info("[LLMService] Unloaded profile '%s'", key)

    # ------------------------------------------------------------------ #
    # Generation (the main public API)
    # ------------------------------------------------------------------ #

    async def generate(
        self,
        profile: str,
        input: Union[str, List[Dict[str, str]]],
        max_new_tokens: Optional[int] = None,
        overrides: Optional[GenerationOverrides] = None,
    ) -> str:
        """Generate text using the specified profile.

        This is the primary method the rest of the application should call.
        """
        prof = self.get_profile(profile)
        manager = await self.ensure_loaded(profile)

        # 1. Prepare the prompt using the profile's formatter
        formatter = prof.formatter
        tokenizer = getattr(manager, "tokenizer", None)

        formatted_prompt: str
        if isinstance(input, list):
            formatted_prompt = formatter.format(
                messages=input,
                tokenizer=tokenizer,
                model_config=prof.config,
            )
        else:
            formatted_prompt = formatter.format(
                assembled_text=str(input),
                tokenizer=tokenizer,
                model_config=prof.config,
            )

        # 2. Merge generation parameters (profile defaults + call-time overrides)
        gen_cfg = prof.generation_defaults
        ov = overrides or GenerationOverrides()

        max_tokens = max_new_tokens or ov.max_new_tokens or 150

        # Build a temporary GenerationConfig for this specific call
        effective_gen = GenerationConfig(
            temperature=ov.temperature if ov.temperature is not None else gen_cfg.temperature,
            top_p=ov.top_p if ov.top_p is not None else gen_cfg.top_p,
            top_k=ov.top_k if ov.top_k is not None else gen_cfg.top_k,
            repetition_penalty=ov.repetition_penalty if ov.repetition_penalty is not None else gen_cfg.repetition_penalty,
            min_p=ov.min_p if ov.min_p is not None else gen_cfg.min_p,
            do_sample=ov.do_sample if ov.do_sample is not None else gen_cfg.do_sample,
        )

        # 3. Temporarily apply the effective generation config to the manager for this call only
        original_gen_cfg = manager.config.generation_config
        manager.config.generation_config = effective_gen

        # 4. Call the underlying manager (sync) from a thread to stay async-friendly
        loop = asyncio.get_running_loop()

        def _do_generate() -> str:
            # We call generate_dialogue directly. It will now see the effective_gen we just set.
            return manager.generate_dialogue(formatted_prompt, max_new_tokens=max_tokens)

        try:
            response = await loop.run_in_executor(None, _do_generate)
            return response.strip() if response else ""
        except Exception as e:
            logger.error("[LLMService] Generation failed for profile '%s': %s", profile, e)
            return "Sorry, I couldn't generate a response right now."
        finally:
            # Always restore the original config so other profiles/calls are unaffected
            manager.config.generation_config = original_gen_cfg

    # ------------------------------------------------------------------ #
    # Convenience / compatibility helpers
    # ------------------------------------------------------------------ #

    async def generate_with_retries(
        self,
        profile: str,
        input: Union[str, List[Dict[str, str]]],
        max_attempts: int = 3,
        max_new_tokens: Optional[int] = None,
        overrides: Optional[GenerationOverrides] = None,
    ) -> str:
        """Wrapper with simple retry logic (similar to old PromptDispatcher / GenerationCoordinator behavior)."""
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await self.generate(profile, input, max_new_tokens, overrides)
                if resp and resp.strip():
                    return resp
            except Exception as e:
                last_error = e
                logger.warning("[LLMService] Attempt %s failed for profile %s: %s", attempt, profile, e)
            await asyncio.sleep(0.5)
        logger.error("[LLMService] All %s attempts failed for profile %s", max_attempts, profile)
        return "Sorry, I couldn't generate a response right now."

    def get_manager(self, profile: str) -> Optional[HuggingFaceModelManager]:
        """Advanced escape hatch: direct access to the loaded HF manager."""
        return self._managers.get(profile)
