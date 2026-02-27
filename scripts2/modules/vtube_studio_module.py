import asyncio
import json
import wave
import io
import websockets
import numpy as np
from scripts2.utils.log_utils import get_logger
from scripts2.modules.base_module import BaseModule

class VTubeStudioModule(BaseModule):
    """
    Async module for controlling VTube Studio model lip-sync from TTS audio.
    Handles WebSocket connection, authentication, and queued audio processing.
    """

    def __init__(self, signals, name="VTubeStudioModule", mouth_parameter="CustomLipSync", model_enabled=True, ws_url="ws://localhost:8001"):
        super().__init__(name)
        self.signals = signals
        self.ws = None
        self.ws_url = ws_url
        self.mouth_parameter = mouth_parameter
        self.model_enabled = model_enabled
        self.queue = asyncio.Queue()
        self._authenticated = False
        self.available_params = []
        self._speaking = False

    async def enqueue_audio(self, wav_bytes: bytes, sample_rate: int):
        """
        Add TTS audio to the lip-sync queue.
        Only queues data — does not touch WebSocket or loops.
        """
        await self.queue.put((wav_bytes, sample_rate))
        self.logger.info("TTS audio queued for VTube Studio")

    async def start(self):
        if not self.model_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        self.loop = asyncio.get_running_loop()
        await super().start()
        self.signals.vtube_studio_module_ready.set()

    async def run(self):
        """
        Connect to VTube Studio, authenticate once, and process queued audio continuously.
        """
        self.logger.info("[run] VTube Studio module starting")

        await self.connect_ws()
        if not await self.ensure_authenticated():
            self.logger.error("Failed to authenticate with VTube Studio; module will not run.")
            return

        self.logger.info("[run] VTube Studio module running")

        while self._running:
            try:
                wav_bytes, sample_rate = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                self._speaking = True
                await self._process_audio_lipsync(wav_bytes, sample_rate)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"[run] Lip-sync processing error: {e}")

        self.logger.info("[run] VTube Studio module stopped")

    async def connect_ws(self):
        if self.ws:
            self.logger.info("Already connected to WebSocket.")
            return True
        try:
            self.ws = await websockets.connect(self.ws_url)
            self.logger.info(f"Connected to VTube Studio at {self.ws_url}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to VTube Studio WS: {e}")
            self.ws = None
            return False

    async def request_auth_token(self):
        request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "auth-token",
            "messageType": "AuthenticationTokenRequest",
            "data": {
                "pluginName": "QubitPipeline",
                "pluginDeveloper": "Kubi"
            }
        }
        await self.ws.send(json.dumps(request))
        response = await self.ws.recv()
        return json.loads(response)

    async def authenticate(self, token: str):
        request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "auth",
            "messageType": "AuthenticationRequest",
            "data": {
                "pluginName": "QubitPipeline",
                "pluginDeveloper": "Kubi",
                "authenticationToken": token
            }
        }
        await self.ws.send(json.dumps(request))
        response = await self.ws.recv()
        return json.loads(response)

    async def ensure_authenticated(self):
        """
        Authenticate once at startup.
        """
        if not self.ws:
            self.logger.error("No WS connection for authentication")
            return False

        token_response = await self.request_auth_token()
        if token_response.get("messageType") != "AuthenticationTokenResponse":
            self.logger.error(f"Unexpected token response: {token_response}")
            return False

        token = token_response["data"]["authenticationToken"]
        auth_response = await self.authenticate(token)
        if auth_response.get("data", {}).get("authenticated", False):
            self._authenticated = True
            self.logger.info("Successfully authenticated with VTube Studio")
            await self.get_input_parameters()
            await self.create_custom_parameter(param_name=self.mouth_parameter)
            return True

        self.logger.error("Authentication failed")
        return False

    async def get_input_parameters(self):
        if not self.ws or not self._authenticated:
            self.logger.warning("Cannot get parameters: WS not authenticated")
            return

        msg = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": str(asyncio.get_running_loop().time()),
            "messageType": "InputParameterListRequest"
        }
        try:
            await self.ws.send(json.dumps(msg))
            response = await self.ws.recv()
            resp_json = json.loads(response)
            if resp_json.get("messageType") == "InputParameterListResponse":
                self.available_params = [p["name"] for p in resp_json["data"]["customParameters"] + resp_json["data"]["defaultParameters"]]
                self.logger.info(f"Available injectable parameters: {self.available_params}")
            else:
                self.logger.error(f"Unexpected response for parameter list: {resp_json}")
        except Exception as e:
            self.logger.error(f"Failed to get parameters: {e}")

    async def create_custom_parameter(self, param_name: str, min_val: float = 0.0, max_val: float = 1.0, default_val: float = 0.0):
        if not self.ws or not self._authenticated:
            self.logger.warning("Cannot create parameter: WS not authenticated")
            return

        if param_name in self.available_params:
            self.logger.info(f"Custom parameter {param_name} already exists.")
            return

        msg = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": str(asyncio.get_running_loop().time()),
            "messageType": "ParameterCreationRequest",
            "data": {
                "parameterName": param_name,
                "explanation": "Custom TTS lip sync parameter",
                "min": min_val,
                "max": max_val,
                "defaultValue": default_val
            }
        }
        try:
            await self.ws.send(json.dumps(msg))
            response = await self.ws.recv()
            resp_json = json.loads(response)
            if resp_json.get("messageType") == "ParameterCreationResponse" and resp_json["data"].get("parameterName") == param_name:
                self.logger.info(f"Created custom parameter: {param_name}")
                self.available_params.append(param_name)
            else:
                self.logger.error(f"Failed to create custom parameter: {resp_json}")
        except Exception as e:
            self.logger.error(f"Error creating custom parameter: {e}")

    async def _process_audio_lipsync(self, wav_bytes: bytes, sample_rate: int):
        """
        Simplified dummy oscillation for lip-sync, ignoring audio amplitude.
        """
        if not self.ws or not self._authenticated:
            self.logger.warning("Cannot process lipsync: WS not authenticated")
            return

        mouth_vals = np.linspace(0, 0.25, 10)
        animation_speed = 0.005

        while self._speaking:
            for val in mouth_vals:
                if not self._speaking:
                    break
                await self.set_parameter(self.mouth_parameter, val)
                await asyncio.sleep(animation_speed)
            
            for val in reversed(mouth_vals):
                if not self._speaking:
                    break
                await self.set_parameter(self.mouth_parameter, val)
                await asyncio.sleep(animation_speed)
        
        await self.set_parameter(self.mouth_parameter, 0.0)
        self._speaking = False

    async def set_parameter(self, parameter: str, value: float):
        if not self.ws:
            self.logger.warning("WS not connected; cannot send parameter")
            return

        msg = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": str(asyncio.get_running_loop().time()),
            "messageType": "InjectParameterDataRequest",
            "data": {
                "mode": "set",
                "parameterValues": [
                    {
                        "id": parameter,
                        "value": value
                    }
                ]
            }
        }
        try:
            await self.ws.send(json.dumps(msg))
            response = await self.ws.recv()
            self.logger.debug(f"Parameter set response: {response}")
        except Exception as e:
            self.logger.error(f"Failed to set parameter: {e}")