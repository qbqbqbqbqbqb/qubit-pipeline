from datetime import datetime, timezone
from src.qubit.cognitive.behaviours.base import Behavior


class ChatResponseBehavior(Behavior):
    """
    Scored proposal behavior for responding to chat / STT input.

    Design goals (2026-05):
    - STT (live streamer voice) has absolute priority at EVERY activity level.
    - At low activity: high willingness to answer the few messages that exist.
    - At high activity: selective — only strong STT + high-quality/mentioned chat survive.
    - Cooldown is soft (score penalty) rather than hard gate.
    - Returns scored proposals so DecisionEngine can fairly compare against IdleMonologue etc.
    """

    def __init__(self):
        super().__init__("ChatResponse")
        self.base_cooldown = 15.0

    async def tick(self, context: dict) -> dict | None:
        queue = context["queue"]
        best = queue.get_best()
        if not best:
            return None

        features = context.get("features", {})
        monologue_enabled = features.get("monologue", True)
        stt_enabled = features.get("stt", True)

        has_live_stt = queue.has_source("user_input_stt") if stt_enabled else False
        pure_chat_mode = not monologue_enabled and not has_live_stt

        activity = float(context.get("activity_score", 0.0))
        time_since_response = context.get("time_since_last_user_response", 999.0)

        # === 1. Base willingness curve (inverted at low activity, selective at high) ===
        if pure_chat_mode or has_live_stt:
            willingness = 1.0
        else:
            # Low activity → more eager to talk to the sparse humans
            # High activity → only answer the very best stuff
            if activity < 2.0:
                willingness = 0.92
            elif activity < 4.0:
                willingness = 0.78
            elif activity < 9.0:
                willingness = 0.55
            else:
                # Very high activity: strong selectivity
                willingness = max(0.08, 0.95 - (activity - 9.0) * 0.12)

        # === 2. STT absolute priority boost (works at all activity levels) ===
        is_stt = best.get("source") == "user_input_stt"
        if is_stt:
            stt_boost = 2.8 if has_live_stt else 1.6   # streamer voice is sacred
            willingness = min(2.5, willingness * stt_boost)

        # === 3. Message quality multiplier (helps selectivity at high activity) ===
        quality = best.get("quality", 0.5)
        quality_mult = 0.6 + (quality * 1.1)   # 0.6–1.7 range

        # === 4. Soft cooldown penalty (never hard block) ===
        cooldown_penalty = 1.0
        if time_since_response < self.base_cooldown:
            # Linear penalty from 1.0 down to 0.25 over the cooldown window
            cooldown_penalty = max(0.25, 1.0 - (self.base_cooldown - time_since_response) / self.base_cooldown)

        # === 5. High-activity extra selectivity filter ===
        if activity > 9.5 and not is_stt:
            # Only let through high-quality mentions or questions when slammed
            if quality < 1.1:
                return None

        raw_score = willingness * quality_mult * cooldown_penalty

        # Final score normalization + small floor
        final_score = max(0.05, min(3.5, raw_score))

        return {
            "type": "response",
            "score": final_score,
            "reason": "chat_response",
            "best_message": best,
        }
