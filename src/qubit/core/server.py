import asyncio
from datetime import datetime, timezone
import json
import websockets
from src.qubit.core.events import Event
from src.qubit.core.service import Service

class WebSocketServerService(Service):
    def __init__(self, host="0.0.0.0", port=8765):
        super().__init__("websocket_server")
        self.host = host
        self.port = port
        self.connected_clients = set()
        self.server = None
        self.app = None
        self.event_bus = None

    #should i use super here?
    # pretty sure i dont as it needs to run first to trigger the other services
    # i probably shouldve written docs
    async def _start(self, app) -> None:
        self.app = app 
        self.event_bus = app.event_bus 
        self.server = await websockets.serve(self.webSocketHandler, self.host, self.port)
        self.logger.info(f"WebSocketServer started on {self.host}:{self.port}")

    # it might work for stop but not start/run? just trying to reduce redundancy
    async def _stop(self) -> None:
        self.logger.info("Stopping WebSocketServer...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.logger.info("WebSocketServer stopped.")

    async def webSocketHandler(self, websocket) -> None:
        self.connected_clients.add(websocket)
        try:
            await self.send_states(websocket)
            async for message in websocket:
                data = json.loads(message)
                action = data.get("action")
                if action == "toggle":
                    input_type = data.get("input")
                    state = data.get("state")
                    if input_type in self.app.state.features:
                        self.app.state.features[input_type] = (state == "on")
                        self.logger.info(f"Toggled {input_type} {state}")
                        await self.broadcast_states()
                    else:
                        self.logger.warning(f"Unknown input type: {input_type}")
                elif action == "terminate":
                    self.logger.info("terminate")
                    self.app.state.shutdown.set()
                elif action == 'start':
                    self.logger.info("Start command from frontend")
                    self.app.state.start.set()
                """                     self.signals.twitch_enabled.set()
                    self.signals.kick_enabled.set()
                    self.signals.youtube_enabled.set()
                    self.signals.stt_enabled.set() 
                    self.signals.chat_enabled.set()
                    self.signals.raid_enabled.set()
                    self.signals.follow_enabled.set()
                    self.signals.subs_enabled.set()
                    self.signals.monologue_enabled.set() """
                
                event = Event(
                        type="bot_started",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        data={"status": "active"},
                    )
                await self.event_bus.publish(event)
                await self.broadcast_states()
        except Exception as e:
            self.logger.error(e)
        finally:
            self.connected_clients.remove(websocket)

    async def send_states(self, websocket) -> None:
        states_message = json.dumps({"type": "states", "data": self.app.state.features})
        await websocket.send(states_message)

    async def broadcast_states(self) -> None:
        if self.connected_clients:
            message = json.dumps({"type": "states", "data": self.app.state.features})
            await asyncio.gather(*(client.send(message) for client in self.connected_clients))

    async def forward_event(self, event_type, data) -> None:
        if self.connected_clients:
            message = json.dumps({"type": event_type, "data": data})
            await asyncio.gather(*(client.send(message) for client in self.connected_clients))