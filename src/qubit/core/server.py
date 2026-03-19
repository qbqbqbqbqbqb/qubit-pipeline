"""
WebSocket server service.

This module provides a WebSocket-based service that allows external clients
(e.g., a frontend dashboard or control panel) to connect to the application
and interact with its runtime state.

The service exposes functionality to:

- Broadcast application state (feature toggles) to connected clients.
- Receive control commands from clients (toggle features, start, terminate).
- Forward application events to connected WebSocket clients.
- Maintain a list of active client connections.

The service integrates with the application's event bus and state system,
allowing remote interfaces to control and observe the bot in real time.
"""
import asyncio
from datetime import datetime, timezone
import json
import websockets
from src.qubit.core.events import Event
from src.qubit.core.service import Service

class WebSocketServerService(Service):
    """
    Service that exposes a WebSocket server for real-time communication
    between the application and external clients.

    Connected clients can receive state updates and send commands to
    control application behavior, such as toggling features, starting
    the bot, or initiating shutdown.

    Attributes
    ----------
    host : str
        Host address the WebSocket server binds to.
    port : int
        Port the WebSocket server listens on.
    connected_clients : set
        Set of active WebSocket client connections.
    server : websockets.server.Serve
        The underlying WebSocket server instance.
    app : Any
        Reference to the application instance.
    event_bus : Any
        Event bus used to publish internal events.
    """
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
    async def start(self, app) -> None:
        """
        Start the WebSocket server.

        Initializes references to the application and event bus,
        then starts the WebSocket server listening for incoming
        client connections.

        Parameters
        ----------
        app : Application
            The application instance providing shared state and
            the event bus.
        """
        self.app = app
        self.event_bus = app.event_bus
        self.server = await websockets.serve(self.websocket_handler, self.host, self.port)
        self.logger.info("[start] WebSocketServer started on %s:%s", self.host, self.port)

    # it might work for stop but not start/run? just trying to reduce redundancy
    async def stop(self) -> None:
        """
        Stop the WebSocket server.

        Closes the server and waits for all active connections
        to terminate before completing shutdown.
        """
        self.logger.info("[stop] Stopping WebSocketServer...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.logger.info("[stop] WebSocketServer stopped.")

    async def websocket_handler(self, websocket) -> None:
        """
        Handle a WebSocket client connection.

        Registers the client, sends the current application state,
        and listens for incoming messages. Supported client actions
        include:

        - ``toggle``: Enable or disable a feature flag.
        - ``terminate``: Signal application shutdown.
        - ``start``: Signal the bot start event.

        State updates are broadcast to all connected clients.

        Parameters
        ----------
        websocket : websockets.WebSocketServerProtocol
            The connected WebSocket client.
        """
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
                        self.logger.info("[webSocketHandler] Toggled %s %s", input_type, state)
                        await self.broadcast_states()
                    else:
                        self.logger.warning("[webSocketHandler] Unknown input type: %s", input_type)
                elif action == "terminate":
                    self.logger.info("[webSocketHandler] terminate")
                    self.app.state.shutdown.set()
                elif action == 'start':
                    self.logger.info("[webSocketHandler] Start command from frontend")
                    self.app.state.start.set()
                    await self.broadcast_states()
        except Exception as e:
            self.logger.error(e)
        finally:
            self.connected_clients.remove(websocket)

    async def send_states(self, websocket) -> None:
        """
        Send the current feature state to a specific client.

        Parameters
        ----------
        websocket : websockets.WebSocketServerProtocol
            The client that will receive the state message.
        """
        states_message = json.dumps({"type": "states", "data": self.app.state.features})
        await websocket.send(states_message)

    async def broadcast_states(self) -> None:
        """
        Broadcast the current feature states to all connected clients.

        If no clients are connected, the method exits without sending
        any messages.
        """
        if self.connected_clients:
            message = json.dumps({"type": "states", "data": self.app.state.features})
            await asyncio.gather(*(client.send(message) for client in self.connected_clients))

    async def forward_event(self, event_type, data) -> None:
        """
        Forward an application event to all connected WebSocket clients.

        Parameters
        ----------
        event_type : str
            The event type identifier.
        data : dict
            Event payload to send to clients.
        """
        if self.connected_clients:
            message = json.dumps({"type": event_type, "data": data})
            await asyncio.gather(*(client.send(message) for client in self.connected_clients))
