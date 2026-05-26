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

    async def _mouth_animation_loop(self) -> None:
            """Enhanced speaking animation (mouth + more movement)."""
            await self.ensure_connected()
            if not self.connected or self.vts is None:
                return

            start_time = time.time()
            try:
                while self.speaking:
                    t = time.time() - start_time

                    # Mouth (stronger when speaking)
                    mouth_value = (math.sin(t * 9) + 1) / 2 * 0.95

                    # Extra movement while speaking (head bob + slight body)
                    head_y = math.sin(t * 1.8) * 4
                    head_x = math.sin(t * 1.2) * 2.5

                    request = self.vts.vts_request.BaseRequest(
                        "InjectParameterDataRequest",
                        {
                            "faceFound": True,
                            "mode": "set",
                            "parameterValues": [
                                {"id": "MouthOpen", "value": mouth_value},
                                {"id": "FaceAngleY", "value": head_y},
                                {"id": "FaceAngleX", "value": head_x},
                            ]
                        }
                    )
                    await self._send_request(request)
                    await asyncio.sleep(0.033)

            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[VtubeStudioHandler] Mouth animation error: {e}")
            finally:
                # Reset key parameters when speaking ends
                try:
                    reset = self.vts.vts_request.BaseRequest(
                        "InjectParameterDataRequest",
                        {
                            "faceFound": True,
                            "mode": "set",
                            "parameterValues": [
                                {"id": "MouthOpen", "value": 0.0},
                                {"id": "FaceAngleY", "value": 0.0},
                                {"id": "FaceAngleX", "value": 0.0},
                            ]
                        }
                    )
                    await self._send_request(reset)
                except Exception:
                    pass
                
    async def send(self, text: str):
        """Placeholder for future use (hotkeys, props, etc)."""
        pass

    async def idle_animation(self) -> None:
        """Runs subtle idle movements when not speaking"""
        await self.ensure_connected()
        if not self.connected or self.vts is None:
            return

        try:
            while not self.speaking:   # Only run when not speaking
                t = time.time()

                # Gentle breathing
                breath = (math.sin(t * 1.2) + 1) / 2 * 0.6 + 0.2   # 0.2 ~ 0.8

                # Very subtle head movement
                head_x = math.sin(t * 0.8) * 8
                head_y = math.sin(t * 0.5) * 5
                head_z = math.cos(t * 0.3) * 3

                # Tiny eye movement
                eye_x = math.sin(t * 2.5) * 3
                eye_y = math.sin(t * 1.7) * 2

                request = self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [
                            {"id": "FaceAngleX", "value": head_x},
                            {"id": "FaceAngleY", "value": head_y},
                            {"id": "FaceAngleZ", "value": head_z},
                            {"id": "EyeLeftX", "value": eye_x},
                            {"id": "EyeLeftY", "value": eye_y},
                            {"id": "EyeRightX", "value": eye_x},
                            {"id": "EyeRightY", "value": eye_y},
                        ]
                    }
                )

                await self._send_request(request)
                await asyncio.sleep(0.05)   # 20 FPS is enough for idle

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[VtubeStudioHandler] Idle animation error: {e}")
        finally:
            # Reset idle parameters when stopping
            await self._reset_idle_parameters()

    async def _reset_idle_parameters(self):
        try:
            reset_request = self.vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {
                    "faceFound": True,
                    "mode": "set",
                    "parameterValues": [
                        {"id": "FaceAngleX", "value": 0.0},
                        {"id": "FaceAngleY", "value": 0.0},
                        {"id": "FaceAngleZ", "value": 0.0},
                        {"id": "EyeLeftX", "value": 0.0},
                        {"id": "EyeLeftY", "value": 0.0},
                        {"id": "EyeRightX", "value": 0.0},
                        {"id": "EyeRightY", "value": 0.0},
                    ]
                }
            )
            await self._send_request(reset_request)
        except Exception:
            pass