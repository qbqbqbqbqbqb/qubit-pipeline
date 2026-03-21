#cognitive_service.py will handle behaviour controls
# it will be the layer to decide when to trigger monologues, when to respond to chat, and when to stay silent
# cognitive layer will take in processed input events and use them to
# calculate an "activity score" that determines how active the chat is. 
# If the score is low for a certain period of time, 
# it will trigger a monologue generation event. 
# It will also decide when to respond to chat messages based on the curremt chat activity score
# once its decided to respond, it will decide which chat message to respond to based on a combination of recency and relevance, 
# as well as chat message quality metrics
# and then trigger a response generation event for that message
# it will value messages from certain input sources more highly than others, 
# for example, it will value STT input more highly than any chat messages
# would the input value work better w/ a priority score for each message based on quality, in combo with a priority for STT vs chat

import asyncio
import random
from datetime import datetime, timezone
from qubit.core.events import MonologueEvent
from src.qubit.core.service import Service

class CognitiveService(Service):
    SUBSCRIPTIONS = {
        "twitch_chat_processed": "_update_activity",
        "bot_started": "_on_bot_start",
    }

    def __init__(self, dispatcher, inactivity_timeout=120):
        super().__init__("CognitiveService")
        self.dispatcher = dispatcher
        self.inactivity_timeout = inactivity_timeout
        self.activity_score = 0
        self.last_activity = datetime.now(timezone.utc)
        self.last_autonomous_speech_time = datetime.now(timezone.utc)
        self.last_user_input_response_time = datetime.now(timezone.utc)

        self.pending_messages = []  # List to track pending messages for response prioritization

        self.source_priorities = {"user_input_stt": 0, "user_input_chat_message": 0,
                       "user_event_follow": 0, "user_event_subscription": 0,
                       "user_event_raid": 0, "other": 0
                       }

    async def start(self, app):
        await super().start(app)

    async def _run(self):
        await super()._run()
        while not self.app.state.shutdown:
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            await self._cognitive_decision_loop()
            await asyncio.sleep(1)

    async def _cognitive_decision_loop(self):
        now = datetime.now(timezone.utc)

        # if actiivty score is low
        # start monolgue

        # else choose to respond to chat
        # or monologue on low random chance

    async def _trigger_autonomous_speech(self, reason):
        # reason can be low_Activity or random dhance
        topic = await self._get_topic_for_autonomous_speech()
        prompt = f"Monologue about {topic}, in character as Qubit."

        event = MonologueEvent(
            type="monologue_prompt",
            user="system",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"user": "system", "topic": topic, "prompt": prompt},
            prompt=prompt
        )

        self.last_autonomous_speech_time = datetime.now(timezone.utc)
        await self._publish_event_to_broker(event)
        self.logger.info("[_trigger_autonomous_speech] Triggered monologue due to %s", reason)

    async def _calculate_best_message_to_respond_to(self):
        # Placeholder for message prioritization logic
        pass

    async def _get_topic_for_autonomous_speech(self):
        topics = [
                            "a funny story about AI",
                            "an interesting Twitch fact",
                            "a quirky joke",
                            "motivational advice",
                            "a short adventure tale"
                        ]
        return random.choice(topics)
    
    async def _publish_event_to_broker(self, event) -> None:
        if self.event_bus:
            await self.event_bus.publish(event)
            self.logger.info("[_publish_event_to_broker] Published event: %s", event)


    async def _update_activity_score(self, event, source):
        self.last_activity = datetime.now(timezone.utc)
        #TODO: do something to activity score here depending on source
        # activity score is only dependent on speed of chat/stt?

    async def _handle_chat_type_input(self, event):
        #TODO: update chat event to have source
        source = "user_input_chat_message"

        text = event.data.get("text", "").lower().strip()

        await self._process_input(event, source)

    async def _handle_stt_input(self, event):
        source = "user_input_stt"
        await self._handle_stt_input(event, source)

    async def _handle_user_event_type_input(self, event):
        pass

    async def _handle_event(self, event):
        if event.type == "twitch_chat_processed":
            await self._handle_chat_type_input(event)

        if event.type == "stt_processed":
            await self._handle_stt_input(event)

    async def _process_input(self, event, source):
        self._update_activity_score(source)
    