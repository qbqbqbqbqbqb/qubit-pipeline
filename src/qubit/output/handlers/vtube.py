"""
VtubeStudioHandler — controls VTube Studio face and mouth animation via pyvts.

Speaking mouth values are driven by audio amplitude injected from TTSHandler
on each synthesis chunk, replacing the previous sine-wave approximation.
Head movement, smile, blinking, and eye movement are still animation-loop driven.
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

    def __init__(
        self,
        plugin_name: str = "Qubit Pipeline",
        developer: str = "Khubie",
        port: int = 8001,
        token_path: str = "vtubeStudio_token.txt",
    ):
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
        if self.connected:
            return True
        return await self.connect()

    async def start_speaking(self) -> None:
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
        if self.speaking:
            return
        if not self._idle_task or self._idle_task.done():
            self._idle_task = asyncio.create_task(self.idle_animation())

    async def inject_mouth(self, amplitude: float) -> None:
        """
        Called by TTSHandler once per audio chunk with the chunk's normalised RMS
        amplitude (0.0–1.0). Injects JawOpen and MouthOpen directly into VTS so
        mouth movement is driven by actual audio rather than a sine wave.

        Non-blocking — fire and forget. If VTS is not connected this is a no-op.
        """
        if not self.connected or self.vts is None:
            return

        jaw = min(amplitude * 1.4, 1.0)
        mouth_open = min(amplitude * 1.1, 1.0)

        try:
            await self._send_request(self.vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {
                    "faceFound": True,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "JawOpen",   "value": round(jaw, 3)},
                        {"id": "MouthOpen", "value": round(mouth_open, 3)},
                    ],
                },
            ))
        except Exception:
            pass

    async def connect(self) -> bool:
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
        if not self.connected or self.vts is None:
            return
        try:
            await self._send_request(self.vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {
                    "faceFound": True,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "EyeOpenLeft",  "value": 0.0},
                        {"id": "EyeOpenRight", "value": 0.0},
                    ],
                },
            ))
            await asyncio.sleep(duration)
            await self._send_request(self.vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {
                    "faceFound": True,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "EyeOpenLeft",  "value": 1.0},
                        {"id": "EyeOpenRight", "value": 1.0},
                    ],
                },
            ))
        except Exception:
            pass

    async def _mouth_animation_loop(self) -> None:
        """
        Drives head movement, smile, blink, and eye gaze during speech.
        JawOpen and MouthOpen are NOT set here — they come from inject_mouth()
        called by TTSHandler on each audio chunk.
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
                    target_smile  = random.uniform(0.20, 0.70)
                    target_face_x = random.uniform(-4.5, 4.5)
                    target_face_y = random.uniform(-4.0, 4.0)
                    target_face_z = random.uniform(-2.5, 2.5)
                    last_variation = t

                var_smile  = var_smile  * 0.94 + target_smile  * 0.06
                var_face_x = var_face_x * 0.95 + target_face_x * 0.05
                var_face_y = var_face_y * 0.95 + target_face_y * 0.05
                var_face_z = var_face_z * 0.95 + target_face_z * 0.05

                smile  = max(0.18, 0.42 + math.sin(t * 1.65) * 0.15 + var_smile)
                face_x = math.sin(t * 1.35) * 5.0 + var_face_x
                face_y = math.sin(t * 1.80) * 4.5 + var_face_y
                face_z = math.cos(t * 1.05) * 2.6 + var_face_z

                await self._send_request(self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [
                            {"id": "MouthSmile",  "value": round(smile,  3)},
                            {"id": "FaceAngleX",  "value": round(face_x, 3)},
                            {"id": "FaceAngleY",  "value": round(face_y, 3)},
                            {"id": "FaceAngleZ",  "value": round(face_z, 3)},
                        ],
                    },
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
                eye_x  = math.sin(t * 0.42) * 2.0
                eye_y  = math.sin(t * 0.33) * 1.3

                await self._send_request(self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [
                            {"id": "FaceAngleX",  "value": round(face_x, 3)},
                            {"id": "FaceAngleY",  "value": round(face_y, 3)},
                            {"id": "FaceAngleZ",  "value": round(face_z, 3)},
                            {"id": "MouthSmile",  "value": 0.48},
                            {"id": "EyeLeftX",    "value": round(eye_x, 3)},
                            {"id": "EyeLeftY",    "value": round(eye_y, 3)},
                            {"id": "EyeRightX",   "value": round(eye_x, 3)},
                            {"id": "EyeRightY",   "value": round(eye_y, 3)},
                        ],
                    },
                ))

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
        if not self.connected or self.vts is None:
            return
        try:
            await self._send_request(self.vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {
                    "faceFound": True,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "JawOpen",    "value": 0.0},
                        {"id": "MouthOpen",  "value": 0.0},
                        {"id": "MouthSmile", "value": 0.25},
                        {"id": "MouthFunnel","value": 0.0},
                        {"id": "CheekPuff",  "value": 0.0},
                        {"id": "FaceAngleX", "value": 0.0},
                        {"id": "FaceAngleY", "value": 0.0},
                        {"id": "FaceAngleZ", "value": 0.0},
                        {"id": "Brows",      "value": 0.0},
                    ],
                },
            ))
        except Exception:
            pass

    async def _reset_idle_parameters(self) -> None:
        if not self.connected or self.vts is None:
            return
        try:
            await self._send_request(self.vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {
                    "faceFound": True,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "FaceAngleX", "value": 0.0},
                        {"id": "FaceAngleY", "value": 0.0},
                        {"id": "FaceAngleZ", "value": 0.0},
                        {"id": "MouthSmile", "value": 0.45},
                        {"id": "EyeLeftX",   "value": 0.0},
                        {"id": "EyeLeftY",   "value": 0.0},
                        {"id": "EyeRightX",  "value": 0.0},
                        {"id": "EyeRightY",  "value": 0.0},
                    ],
                },
            ))
        except Exception:
            pass