"""
VTube Studio handler.

Public interface (recommended usage from OutputCoordinator or elsewhere):

    await handler.start_speaking()     # when AI begins talking
    await handler.stop_speaking()      # when AI finishes talking

The handler manages the animation task and mouth reset internally.
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

        if pyvts is None:
            print("[VtubeStudioHandler] pyvts not installed. Run: pip install pyvts")

    async def ensure_connected(self) -> bool:
        """Try to connect early if not already connected. Safe to call multiple times."""
        if self.connected:
            return True
        return await self.connect()

    async def start_speaking(self):
        """Call this when the AI starts speaking. Starts mouth animation."""
        if not self.speaking:
            self.speaking = True
            self._mouth_task = asyncio.create_task(self._mouth_animation_loop())

    async def stop_speaking(self):
        """Call this when the AI finishes speaking. Stops animation and resets mouth."""
        if self.speaking:
            self.speaking = False

            if self._mouth_task:
                self._mouth_task.cancel()
                try:
                    await self._mouth_task
                except asyncio.CancelledError:
                    pass
                self._mouth_task = None

            # Small delay to let the last animation frame settle
            await asyncio.sleep(0.1)

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
        await self.ensure_connected()
        if not self.connected or self.vts is None:
            return

        start_time = time.time()
        error_logged = False

        try:
            while self.speaking:                    # ← This flag must be set False externally
                elapsed = time.time() - start_time
                mouth_value = (math.sin(elapsed * 8.5) + 1) / 2 * 0.85

                request = self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [
                            {"id": "MouthOpen", "value": mouth_value}
                        ]
                    }
                )

                await self._send_request(request)
                await asyncio.sleep(0.033)

        except asyncio.CancelledError:
            print("[VtubeStudioHandler] Mouth animation cancelled")
        except Exception as e:
            if not error_logged:
                print(f"[VtubeStudioHandler] Mouth animation error: {e}")
                error_logged = True
        finally:
            # Always reset mouth when loop ends
            try:
                reset_request = self.vts.vts_request.BaseRequest(
                    "InjectParameterDataRequest",
                    {
                        "faceFound": True,
                        "mode": "set",
                        "parameterValues": [{"id": "MouthOpen", "value": 0.0}]
                    }
                )
                await self._send_request(reset_request)
            except Exception:
                pass
            
    async def send(self, text: str):
        """Placeholder for future use (hotkeys, props, etc)."""
        pass