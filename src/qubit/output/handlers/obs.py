"""
<summary>
OBSHandler — manages OBS WebSocket connections and subtitle text source updates.
</summary>
<remarks>
Connects to OBS Studio via websocket-client, authenticates using the OBS WebSocket
protocol HMAC-SHA256 challenge response, and sends SetInputSettings requests to
update text sources for subtitles.
</remarks>
"""

import asyncio
import base64
import hashlib
import json
from typing import Any
import websocket

from config.config import TTS_SUBTITLE_NAME
from src.qubit.utils.log_utils import get_logger

logger = get_logger("OBS_Websocket_Controller")


class OBSHandler:
    """
    <summary>
    Leaf handler for OBS WebSocket connections and subtitle source updates.
    Stateless per-call: each subtitle update opens, sends, and closes its own connection.
    </summary>
    """

    def __init__(self: Any, settings: Any) -> None:
        """
        <summary>Initialise the handler with OBS connection settings.</summary>
        <param name="settings">Settings object providing obs_password, obs_host, and obs_port.</param>
        """
        self.settings = settings
        self.obs_password = self.settings.obs_password
        self.obs_host = self.settings.obs_host
        self.obs_port = self.settings.obs_port
        self.url = f"ws://{self.obs_host}:{self.obs_port}"

    def _build_auth_string(self: Any, salt: str, challenge: str) -> str:
        """
        <summary>Compute the HMAC-SHA256 authentication string for OBS WebSocket.</summary>
        <param name="salt">The salt from the OBS hello message.</param>
        <param name="challenge">The challenge from the OBS hello message.</param>
        <returns>The base64-encoded authentication string.</returns>
        """
        try:
            secret = base64.b64encode(
                hashlib.sha256((self.obs_password + salt).encode("utf-8")).digest()
            )
            auth = base64.b64encode(
                hashlib.sha256(secret + challenge.encode("utf-8")).digest()
            ).decode("utf-8")
            return auth
        except Exception as e:
            logger.error("Error building auth string: %s", e)
            raise

    def connect_to_obs(self: Any) -> websocket.WebSocket:
        """
        <summary>Open a WebSocket connection to OBS and complete authentication.</summary>
        <returns>The authenticated WebSocket connection.</returns>
        """
        try:
            ws = websocket.WebSocket()
            ws.connect(self.url)
            message = ws.recv()
            result = json.loads(message)

            if "authentication" in result["d"]:
                auth_payload = {
                    "op": 1,
                    "d": {
                        "rpcVersion": 1,
                        "authentication": self._build_auth_string(
                            result["d"]["authentication"]["salt"],
                            result["d"]["authentication"]["challenge"],
                        ),
                        "eventSubscriptions": 1000,
                    },
                }
                ws.send(json.dumps(auth_payload))
                auth_response = ws.recv()
                if not auth_response:
                    raise Exception("Empty response after auth payload")
            return ws
        except Exception as e:
            logger.error("Error connecting to OBS: %s", e)
            raise

    async def update_subtitle_text_and_style(
        self: Any,
        source_name: str = TTS_SUBTITLE_NAME,
        new_text: str = "Default",
        font_face: str = "Arial",
        font_size: int = 50,
        width: int = 1920,
        height: int = 400,
        valign: str = "center",
        word_wrap: bool = True,
    ) -> None:
        """
        <summary>
        Update a text source in OBS with the specified text, font, and layout settings.
        Opens and closes the WebSocket connection per call.
        </summary>
        <param name="source_name">Name of the text source in OBS.</param>
        <param name="new_text">Text content to display.</param>
        <param name="font_face">Font face name.</param>
        <param name="font_size">Font size in points.</param>
        <param name="width">Bounding box width in pixels.</param>
        <param name="height">Bounding box height in pixels.</param>
        <param name="valign">Vertical alignment: 'top', 'center', or 'bottom'.</param>
        <param name="word_wrap">Enable or disable word wrapping.</param>
        """
        try:
            ws = await asyncio.to_thread(self.connect_to_obs)

            font_flags = 1 if word_wrap else 0
            payload = {
                "op": 6,
                "d": {
                    "requestId": "update_subtitle_text_and_style",
                    "requestType": "SetInputSettings",
                    "requestData": {
                        "inputName": source_name,
                        "inputSettings": {
                            "text": new_text,
                            "font": {
                                "face": font_face,
                                "size": font_size,
                                "flags": font_flags,
                            },
                            "valign": valign,
                            "use_custom_extents": True,
                            "custom_width": width,
                            "custom_height": height,
                        },
                    },
                },
            }
            ws.send(json.dumps(payload))
            response = ws.recv()
            logger.info("Subtitle updated: %s", response)
        except Exception as e:
            logger.error("Failed to update subtitle text and style: %s", e)
        finally:
            try:
                ws.close()
            except Exception as e:
                logger.error("Error closing WebSocket connection: %s", e)
