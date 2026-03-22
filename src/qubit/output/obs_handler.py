"""
Module for managing OBS WebSocket connections and subtitle operations.

This module provides the OBSManager class to handle authentication and communication
with OBS Studio via WebSocket, including updating subtitle text sources.
"""

import asyncio
import base64
import hashlib
import json
from typing import Any
import websocket

from config.config import TTS_SUBTITLE_NAME

from src.utils.log_utils import get_logger
logger = get_logger("OBS_Websocket_Controller")


class OBSHandler:
    """
    Manages OBS WebSocket connections and subtitle updates.

    This class handles establishing authenticated WebSocket connections to OBS Studio
    and provides methods to update text sources for subtitles.
    """

    def __init__(self: Any, settings: Any) -> None:
        """
        Initialize the OBSManager with settings.

        Args:
            settings: An object containing OBS configuration attributes such as
                      obs_password, obs_host, obs_port.
        """

        self.settings = settings
        self.obs_password = self.settings.obs_password
        self.obs_host = self.settings.obs_host
        self.obs_port = self.settings.obs_port
        self.url = f"ws://{self.obs_host}:{self.obs_port}"

    def _build_auth_string(self: Any, salt: str, challenge: str) -> str:
        """
        Build the authentication string for OBS WebSocket.
        Args:
            salt (str): The salt provided by OBS.
            challenge (str): The challenge provided by OBS.
        Returns:
            str: The computed authentication string.
        """
        try:
            secret = base64.b64encode(
                hashlib.sha256((self.obs_password + salt).encode('utf-8')).digest()
            )
            auth = base64.b64encode(
                hashlib.sha256(secret + challenge.encode('utf-8')).digest()
            ).decode('utf-8')
            return auth
        except Exception as e:
            logger.error("Error building auth string: %s", e)
            raise

    def connect_to_obs(self: Any) -> websocket.WebSocket:
        """
        Establish a WebSocket connection to OBS and authenticate.
        Returns:
            websocket.WebSocket: The authenticated WebSocket connection.
        """
        try:
            ws = websocket.WebSocket()
            ws.connect(self.url)
            message = ws.recv()
            result = json.loads(message)

            if 'authentication' in result['d']:
                auth_payload = {
                    "op": 1,
                    "d": {
                        "rpcVersion": 1,
                        "authentication": self._build_auth_string(
                            result['d']['authentication']['salt'],
                            result['d']['authentication']['challenge']
                        ),
                        "eventSubscriptions": 1000
                    }
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
        source_name:str=TTS_SUBTITLE_NAME, new_text: str = "Default", font_face:str="Arial", font_size:int=50,
        width:int=1920, height:int=400, valign:str="center", word_wrap:bool=True
    ) -> None:
        """
        Update subtitle text source in OBS with wrapping, font size, vertical alignment, and custom extents.
        
        Args:
            source_name (str): Name of the text source in OBS.
            new_text (str): Text content to display.
            font_face (str): Font face name.
            font_size (int): Font size.
            width (int): Width of bounding box in pixels.
            height (int): Height of bounding box in pixels.
            valign (str): Vertical alignment, "top", "center", or "bottom".
            word_wrap (bool): Enable or disable word wrapping.
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
                                "flags": font_flags
                            },
                            "valign": valign,
                            "use_custom_extents": True,
                            "custom_width": width,
                            "custom_height": height
                        }
                    }
                }
            }
            ws.send(json.dumps(payload))
            response = ws.recv()
            logger.info("Subtitle text and style updated: %s", response)
        except Exception as e:
            logger.error("Failed to update subtitle text and style: %s", e)
        finally:
            try:
                ws.close()
            except Exception as e:
                logger.error("Error closing WebSocket connection: %s", e)
