from datetime import datetime, timezone
from src.qubit.utils.log_utils import get_logger
from src.qubit.core.events import ResponsePromptEvent


logger = get_logger(__name__)
class LLMPromptHandler:

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

        self.builders = {
            "twitch_chat_processed": self._build_chat_prompt,
            "twitch_raid_processed": self._build_raid_prompt,
            "twitch_follow_processed": self._build_follow_prompt,
            "twitch_subscription_processed": self._build_subscription_prompt,
            "monologue_prompt": self._build_monologue_prompt
        }
        
    async def handle_event(self, event):
        builder = self.builders.get(event.type)
        if not builder:
            logger.warning(f"No builder found for event type: {event.type}")
            return

        prompt_event = builder(event)
        await self.dispatcher.enqueue(prompt_event)

    def _build_monologue_prompt(self, event):
        prompt = event.prompt
        return self._create_prompt_event(
            event,
            prompt,
            "monologue_response_prompt"
        )
    
    def _build_chat_prompt(self, event):
        prompt = f"{event.user}: {event.text}"
        return self._create_prompt_event(event, prompt, "twitch_chat_response_prompt")
    
    def _build_raid_prompt(self, event):
        prompt = f"{event.user} is raiding with {event.viewers} viewers!"
        return self._create_prompt_event(event, prompt, "twitch_raid_response_prompt")
    
    def _build_follow_prompt(self, event):
        prompt = f"{event.user} just followed the channel!"
        return self._create_prompt_event(event, prompt, "twitch_follow_response_prompt")
    
    def _build_subscription_prompt(self, event):
        messages = {
            "resub": f"{event.user} just resubscribed with {event.tier}!",
            "gift": f"{event.user} just gifted a {event.tier} subscription!",
            "prime": f"{event.user} just subscribed with Prime Gaming!"
        }

        base = messages.get(
            event.sub_type,
            f"{event.user} just subscribed with {event.tier}!"
        )

        extra = f" They said: {event.sub_message}" if event.sub_message else ""
        prompt = f"{base}{extra}"

        return self._create_prompt_event(event, prompt, "twitch_subscription_response_prompt")
    
    def _create_prompt_event(self, event, prompt, event_type):
        return ResponsePromptEvent(
            type=event_type,
            user=event.user,
            source=event.type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"user": event.user, "prompt": prompt},
            prompt=prompt
        )