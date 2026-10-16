"""
<summary>
VtubeStudioHandler — controls VTube Studio face and mouth animation via pyvts.
</summary>
<remarks>
Provides speaking and idle animation loops that inject face parameters directly
into VTube Studio. Both loops are managed as asyncio Tasks, cancelled and restarted
when the mode switches, so there is never more than one animation loop of each kind
running at a time.

Gracefully degrades if pyvts is not installed: all methods become no-ops.
</remarks>
"""

import asyncio
import math
import random
import time

try:
    import pyvts
except ImportError:
    pyvts = None


class VtubeStudioHandler:
    """
    <summary>
    Manages VTube Studio connection, authentication, speaking mouth animation,
    and idle head/eye animation via the pyvts library.
    </summary>
    """

    def __init__(
        self,
        plugin_name: str = "Qubit Pipeline",
        developer: str = "Khubie",
        port: int = 8001,
        token_path: str = "vtubeStudio_token.txt",
    ):
        """
        <summary>Initialise the handler with plugin identity and connection settings.</summary>
        <param name="plugin_name">Plugin name shown in VTube Studio's permissions UI.</param>
        <param name="developer">Developer name shown in VTube Studio's permissions UI.</param>
        <param name="port">VTube Studio API WebSocket port.</param>
        <param name="token_path">File path for storing the authentication token.</param>
        """
        self.plugin_name = plugin_name
        self.developer = developer
        self.port = port
        self.token_path = token_path
        print(f"[VtubeStudioHandler] Using VTube Studio port: {self.port}")

        self.vts = None
        self.connected = False
        self.speaking = False
        self._mouth_task: asyncio.Task | None = None
        self._idle_task: asyncio.Task | None = None

        if pyvts is None:
            print("[VtubeStudioHandler] pyvts not installed. Run: pip install pyvts")

    async def ensure_connected(self) -> bool:
        """
        <summary>Connect to VTube Studio if not already connected.</summary>
        <returns>True if connected, False if connection failed or pyvts is unavailable.</returns>
        """
        if self.connected:
            return True
        return await self.connect()

    async def start_speaking(self) -> None:
        """
        <summary>
        Switch to speaking mode: cancel the idle task and start the mouth animation loop.
        No-op if already speaking.
        </summary>
        """
        if self.speaking:
            return

        self.speaking = True

        if self._idle_task:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass
            self._idle_task = None

        if not self._mouth_task or self._mouth_task.done():
            self._mouth_task = asyncio.create_task(self._mouth_animation_loop())

    async def stop_speaking(self) -> None:
        """
        <summary>
        Switch back to idle mode: cancel the mouth animation task and restart the idle loop.
        No-op if not currently speaking.
        </summary>
        """
        if not self.speaking:
            return

        self.speaking = False

        if self._mouth_task:
            self._mouth_task.cancel()
            try:
                await self._mouth_task
            except asyncio.CancelledError:
                pass
            self._mouth_task = None

        await asyncio.sleep(0.1)

        if not self._idle_task or self._idle_task.done():
            self._idle_task = asyncio.create_task(self.idle_animation())

    async def start_idle(self) -> None:
        """
        <summary>Start the idle animation if not currently speaking.</summary>
        """
        if self.speaking:
            return

        if not self._idle_task or self._idle_task.done():
            self._idle_task = asyncio.create_task(self.idle_animation())

    async def connect(self) -> bool:
        """
        <summary>
        Open a new pyvts connection, request an auth token, and authenticate.
        Closes any existing connection before reconnecting.
        </summary>
        <returns>True if authentication succeeded, False on failure.</returns>
        """
        if pyvts is None:
            return False

        if self.vts:
            try:
                await self.vts.close()
            except Exception:
                pass
            self.vts = None

        try:
            plugin_info = {
                "plugin_name": self.plugin_name,
                "developer": self.developer,
                "authentication_token_path": self.token_path,
            }

            self.vts = pyvts.vts(plugin_info=plugin_info, port=self.port)

            print("[VtubeStudioHandler] Connecting to VTube Studio...")
            await self.vts.connect()

            print("[VtubeStudioHandler] Requesting fresh auth token...")
            await self.vts.request_authenticate_token()

            print("[VtubeStudioHandler] Authenticating...")
            await self.vts.request_authenticate()

            self.connected = True
            print("[VtubeStudioHandler] Connected and authenticated with VTube Studio")
            return True

        except Exception as e:
            print(f"[VtubeStudioHandler] Connection failed: {e}")
            print("[VtubeStudioHandler] Ensure VTube Studio is running and the plugin permission was accepted.")
            self.connected = False
            self.vts = None
            return False

    async def _send_request(self, request):
        """
        <summary>Send a pyvts request and return the response, or None on error.</summary>
        <param name="request">The pyvts request object to send.</param>
        <returns>The response dict, or None if unavailable or on error.</returns>
        """
        if not self.vts:
            return None
        try:
            response = await self.vts.request(request)
            if response and response.get("messageType") == "APIError":
                print(f"[VtubeStudioHandler] VTube API Error: {response['data'].get('message')}")
                return None
            return response
        except Exception as e:
            print(f"[VtubeStudioHandler] Request error: {e}")
            return None

    async def _blink(self, duration: float = 0.12) -> None:
        """
        <summary>Perform one blink by closing both eyes, waiting, then opening them.</summary>
        <param name="duration">Time in seconds to keep the eyes closed.</param>
        """
        if not self.connected or self.vts is None:
            return
        try:
            await self._send_request(
                self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [
                            {"id": "EyeOpenLeft", "value": 0.0},
                            {"id": "EyeOpenRight", "value": 0.0},
                        ],
                    },
                )
            )
            await asyncio.sleep(duration)

            await self._send_request(
                self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [
                            {"id": "EyeOpenLeft", "value": 1.0},
                            {"id": "EyeOpenRight", "value": 1.0},
                        ],
                    },
                )
            )
        except Exception:
            pass

    async def _mouth_animation_loop(self) -> None:
        """
        <summary>
        Drive jaw, mouth, smile, and head-angle parameters in a natural speech animation loop.
        Runs at ~30 fps until cancelled. Resets parameters on exit.
        </summary>
        """
        await self.ensure_connected()
        if not self.connected or self.vts is None:
            return

        start_time = time.time()
        last_blink = time.time()
        last_variation = 0.0

        var_smile = var_face_x = var_face_y = var_face_z = 0.0
        target_smile = 0.25
        target_face_x = target_face_y = target_face_z = 0.0

        try:
            while self.speaking:
                t = time.time() - start_time

                if t - last_variation > random.uniform(2.5, 6.0):
                    target_smile = random.uniform(0.20, 0.70)
                    target_face_x = random.uniform(-4.5, 4.5)
                    target_face_y = random.uniform(-4.0, 4.0)
                    target_face_z = random.uniform(-2.5, 2.5)
                    last_variation = t

                var_smile = var_smile * 0.94 + target_smile * 0.06
                var_face_x = var_face_x * 0.95 + target_face_x * 0.05
                var_face_y = var_face_y * 0.95 + target_face_y * 0.05
                var_face_z = var_face_z * 0.95 + target_face_z * 0.05

                jaw = (math.sin(t * 8.7) + 1) / 2 * 0.92
                mouth_open = jaw * 0.75 + (math.sin(t * 11.8) + 1) / 2 * 0.25
                smile = max(0.18, 0.42 + math.sin(t * 1.65) * 0.15 + var_smile)
                face_x = math.sin(t * 1.35) * 5.0 + var_face_x
                face_y = math.sin(t * 1.8) * 4.5 + var_face_y
                face_z = math.cos(t * 1.05) * 2.6 + var_face_z

                params = [
                    {"id": "JawOpen", "value": jaw},
                    {"id": "MouthOpen", "value": mouth_open},
                    {"id": "MouthSmile", "value": smile},
                    {"id": "FaceAngleX", "value": face_x},
                    {"id": "FaceAngleY", "value": face_y},
                    {"id": "FaceAngleZ", "value": face_z},
                ]

                await self._send_request(self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {"faceFound": True, "mode": "set", "parameterValues": params},
                ))

                if time.time() - last_blink > random.uniform(3.8, 6.2):
                    await self._blink(0.12)
                    last_blink = time.time()

                await asyncio.sleep(0.033)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[VtubeStudioHandler] Speaking error: {e}")
        finally:
            await self._reset_speaking_parameters()

    async def idle_animation(self) -> None:
        """
        <summary>
        Drive head, eye, and smile parameters in a natural idle animation loop.
        Runs at ~12 fps until cancelled or self.speaking becomes True. Resets parameters on exit.
        </summary>
        """
        await self.ensure_connected()
        if not self.connected or self.vts is None:
            return

        last_blink = time.time()

        try:
            while not self.speaking:
                t = time.time()

                face_x = math.sin(t * 0.25) * 3.8
                face_y = math.sin(t * 0.21) * 3.2 + math.cos(t * 0.15) * 1.5
                face_z = math.cos(t * 0.18) * 2.0
                eye_x = math.sin(t * 0.42) * 2.0
                eye_y = math.sin(t * 0.33) * 1.3

                request = self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [
                            {"id": "FaceAngleX", "value": face_x},
                            {"id": "FaceAngleY", "value": face_y},
                            {"id": "FaceAngleZ", "value": face_z},
                            {"id": "MouthSmile", "value": 0.48},
                            {"id": "EyeLeftX", "value": eye_x},
                            {"id": "EyeLeftY", "value": eye_y},
                            {"id": "EyeRightX", "value": eye_x},
                            {"id": "EyeRightY", "value": eye_y},
                        ],
                    },
                )

                await self._send_request(request)

                if time.time() - last_blink > random.uniform(4.0, 6.8):
                    await self._blink(0.13)
                    last_blink = time.time()

                await asyncio.sleep(0.085)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[VtubeStudioHandler] Idle error: {e}")
        finally:
            await self._reset_idle_parameters()

    async def _reset_speaking_parameters(self) -> None:
        """<summary>Reset all speaking-related VTS parameters to neutral values after the animation loop exits.</summary>"""
        if not self.connected or self.vts is None:
            return
        try:
            reset = self.vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {
                    "faceFound": True,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "JawOpen", "value": 0.0},
                        {"id": "MouthOpen", "value": 0.0},
                        {"id": "MouthSmile", "value": 0.25},
                        {"id": "MouthFunnel", "value": 0.0},
                        {"id": "CheekPuff", "value": 0.0},
                        {"id": "FaceAngleX", "value": 0.0},
                        {"id": "FaceAngleY", "value": 0.0},
                        {"id": "FaceAngleZ", "value": 0.0},
                        {"id": "Brows", "value": 0.0},
                    ],
                },
            )
            await self._send_request(reset)
        except Exception:
            pass

    async def _reset_idle_parameters(self) -> None:
        """<summary>Reset all idle-related VTS parameters to neutral values after the animation loop exits.</summary>"""
        if not self.connected or self.vts is None:
            return
        try:
            reset = self.vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {
                    "faceFound": True,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "FaceAngleX", "value": 0.0},
                        {"id": "FaceAngleY", "value": 0.0},
                        {"id": "FaceAngleZ", "value": 0.0},
                        {"id": "MouthSmile", "value": 0.45},
                        {"id": "EyeLeftX", "value": 0.0},
                        {"id": "EyeLeftY", "value": 0.0},
                        {"id": "EyeRightX", "value": 0.0},
                        {"id": "EyeRightY", "value": 0.0},
                    ],
                },
            )
            await self._send_request(reset)
        except Exception:
            pass
