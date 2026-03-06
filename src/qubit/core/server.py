import asyncio
import json
from src.qubit.utils.log_utils import get_logger
import websockets

logger = get_logger(__name__)

class WebSocketServer:
    def __init__(self, signals, host, port):
        self.signals = signals
        self.host = host
        self.port = port
        self.connected_clients = set()

        self.states = {
            'monologue': self.signals.monologue_enabled.is_set(),
            'twitch': self.signals.twitch_enabled.is_set(),
            'kick': self.signals.kick_enabled.is_set(),
            'youtube': self.signals.youtube_enabled.is_set(),
            'stt': self.signals.speech_to_text_enabled.is_set(),
            'chat_enabled': self.signals.chat_enabled.is_set(),
            'raid_enabled': self.signals.raid_enabled.is_set(),
            'follow_enabled': self.signals.follow_enabled.is_set(),
            'subs_enabled': self.signals.subs_enabled.is_set()
        }

    async def webSocketHandler(self, websocket, path):
        self.connected_clients.add(websocket)
        try:
            await self.send_states(websocket)
            async for message in websocket:
                data = json.loads(message)
                action = data.get('action'),
                if action == 'toggle':
                    input_type = data.get('input')
                    state = data.get('state')
                    if hasattr(self.signals, f"{input_type} enabled"):
                        enabled_event = getattr(self.signals, f"{input_type} enabled")
                        if state == 'on':
                            enabled_event.set()
                        else:
                            enabled_event.clear()
                        logger.info(f"{input_type} {state}")
                        await self.broadcast_states()
                    else:
                        logger.warning(f"aaaa{input_type}")
                elif action == 'terminate':
                    logger.info("terminate")
                    self.signals.terminate.set()
        except Exception as e:
            logger.error(e)
        finally:
            self.connected_clients.remove(websocket)

    async def send_states(self, websocket):
        await websocket.send({"type": "states", "data": self.states})

    async def broadcast_states(self):
        if self.connected_clients:
            states_message = json.dumps({"type": "states", "data": self.states})
            await asyncio.gather(*(client.send(states_message) for client in self.connected_clients))

    async def forward_event(self, event_type, data):
        if self.connected_clients:
            message = json.dumps({"type": event_type, "data": data})
            await asyncio.gather(*(client.send(message) for client in self.connected_clients))

    async def start(self):
        server = await websockets.serve(self.webSocketHandler, self.host, self.port)
        logger.info(f"Server started on {self.host}:{self.port}")
        #event_bus.subscribe("?????", self.forward_event)
        return server