"""
VTube Studio handler.

Public interface (recommended usage):

    await handler.start_speaking()   # AI starts talking → mouth + enhanced movement
    await handler.stop_speaking()    # AI stops talking → switches back to idle animation

The handler automatically manages switching between speaking and idle animations.
You can also call start_idle() manually after connection if you want idle movement right away.
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
        """Try to connect early if not already connected. Safe to call multiple times."""
        if self.connected:
            return True
        return await self.connect()

    async def start_speaking(self):
        """Start speaking mode: cancel idle, start mouth animation."""
        if self.speaking:
            return

        self.speaking = True

        # Cancel any running idle animation
        if self._idle_task:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass
            self._idle_task = None

        # Start mouth animation
        if not self._mouth_task or self._mouth_task.done():
            self._mouth_task = asyncio.create_task(self._mouth_animation_loop())

    async def stop_speaking(self):
        """Stop speaking mode: cancel mouth, start idle animation."""
        if not self.speaking:
            return

        self.speaking = False

        # Cancel mouth animation
        if self._mouth_task:
            self._mouth_task.cancel()
            try:
                await self._mouth_task
            except asyncio.CancelledError:
                pass
            self._mouth_task = None

        # Small delay to let the last frame settle
        await asyncio.sleep(0.1)

        # Start idle animation
        if not self._idle_task or self._idle_task.done():
            self._idle_task = asyncio.create_task(self.idle_animation())

    async def start_idle(self):
        """Start idle animation (call this after connection if you want idle movement from the beginning)."""
        if self.speaking:
            return  # Don't start idle while speaking

        if not self._idle_task or self._idle_task.done():
            self._idle_task = asyncio.create_task(self.idle_animation())

    async def connect(self) -> bool:
        if pyvts is None:
            return False

        # Clean up any previous bad state
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
            print("[VtubeStudioHandler] ✅ Successfully connected and authenticated with VTube Studio")
            return True

        except Exception as e:
            print(f"[VtubeStudioHandler] Connection failed: {e}")
            print("[VtubeStudioHandler] ⚠️  Make sure VTube Studio is running and you accepted the plugin permission popup!")
            self.connected = False
            self.vts = None
            return False

    async def _send_request(self, request):
        """Neuro-style request helper with basic error handling."""
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

    async def _blink(self, duration: float = 0.12):
        """Natural blink using EyeOpen parameters."""
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
                        ]
                    }
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
                        ]
                    }
                )
            )
        except Exception:
            pass

    async def _mouth_animation_loop(self) -> None:
        """Smoother speaking with consistent smile"""
        await self.ensure_connected()
        if not self.connected or self.vts is None:
            return

        start_time = time.time()
        last_blink = time.time()
        last_variation = 0.0

        var_smile = 0.25
        var_face_x = var_face_y = var_face_z = 0.0

        target_smile = 0.25
        target_face_x = target_face_y = target_face_z = 0.0

        try:
            while self.speaking:
                t = time.time() - start_time

                # Even slower variation changes
                if t - last_variation > random.uniform(2.5, 6.0):
                    target_smile = random.uniform(0.20, 0.70)
                    target_face_x = random.uniform(-4.5, 4.5)
                    target_face_y = random.uniform(-4.0, 4.0)
                    target_face_z = random.uniform(-2.5, 2.5)
                    last_variation = t

                # Very strong smoothing to reduce jumping
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
                    {"faceFound": True, "mode": "set", "parameterValues": params}
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
        """Natural idle with proper smile for your model"""
        await self.ensure_connected()
        if not self.connected or self.vts is None:
            return

        last_blink = time.time()

        try:
            while not self.speaking:
                t = time.time()

                # Smooth and subtle movement
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
                            {"id": "MouthSmile", "value": 0.48},     # ← Increased for your model
                            {"id": "EyeLeftX", "value": eye_x},
                            {"id": "EyeLeftY", "value": eye_y},
                            {"id": "EyeRightX", "value": eye_x},
                            {"id": "EyeRightY", "value": eye_y},
                        ]
                    }
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

    async def _reset_speaking_parameters(self):
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
                        {"id": "MouthSmile", "value": 0.25},   # ← Leave a light smile after speaking
                        {"id": "MouthFunnel", "value": 0.0},
                        {"id": "CheekPuff", "value": 0.0},
                        {"id": "FaceAngleX", "value": 0.0},
                        {"id": "FaceAngleY", "value": 0.0},
                        {"id": "FaceAngleZ", "value": 0.0},
                        {"id": "Brows", "value": 0.0},
                    ]
                }
            )
            await self._send_request(reset)
        except Exception:
            pass

    async def _reset_idle_parameters(self):
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
                        {"id": "MouthSmile", "value": 0.45},   # ← Keep gentle smile even after idle stops
                        {"id": "EyeLeftX", "value": 0.0},
                        {"id": "EyeLeftY", "value": 0.0},
                        {"id": "EyeRightX", "value": 0.0},
                        {"id": "EyeRightY", "value": 0.0},
                    ]
                }
            )
            await self._send_request(reset)
        except Exception:
            pass
        
    async def send(self, text: str):
        """Placeholder for future use (hotkeys, props, etc)."""
        pass