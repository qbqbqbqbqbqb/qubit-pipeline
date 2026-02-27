import asyncio
import pyvts
import numpy as np
from scripts2.utils.log_utils import get_logger

plugin_info = {
    "plugin_name": "Qubit Controller",
    "developer": "Kubi",
    "authentication_token_path": "./token.txt"
}
params = {
    1: "AiMouthOpen",
    2: "AiEyeBlink"
}

class VTubeStudioModule:
    """
    Async module for controlling VTube Studio model lip-sync.
    """

    def __init__(self, signals, model_enabled=True):
        self.logger = get_logger("VTubeStudioModule")
        self.model_enabled = model_enabled
        self.speaking = False
        self.vts = None 
        self.signals = signals

    async def init(self):
        if not self.model_enabled:
            self.logger.info("VTube Studio module is disabled. Not initializing.")
            return
        self.logger.info("Initializing VTube Studio connection...")
        await self.connect()
        await self.register_params()

    async def connect(self):
        self.vts = pyvts.vts(plugin_info=plugin_info)
        await self.vts.connect()
        await self.vts.request_authenticate_token()
        await self.vts.request_authenticate()

    async def register_params(self):
        for i in params:
            new_parameter_name = params[i]
            try:
                await self.vts.request(
                    self.vts.vts_request.requestCustomParameter(new_parameter_name)
                )
            except Exception as e:
                self.logger.error(f"Failed to register param {new_parameter_name}: {e}")

    async def mouthanimation(self):
        mouth_vals = np.linspace(0, 0.25, 10)
        animation_speed = 0.005
        param_name = "AiMouthOpen"

        try:
            while self.speaking:
                for val in mouth_vals:
                    if not self.speaking:
                        break
                    await self.vts.request(
                        self.vts.vts_request.requestSetParameterValue(param_name, val)
                    )
                    await asyncio.sleep(animation_speed)
                
                for val in reversed(mouth_vals):
                    if not self.speaking:
                        break
                    await self.vts.request(
                        self.vts.vts_request.requestSetParameterValue(param_name, val)
                    )
                    await asyncio.sleep(animation_speed)
            
            await self.vts.request(
                self.vts.vts_request.requestSetParameterValue(param_name, 0)
            )
        except Exception as e:
            self.logger.error(f"Mouth animation error: {e}")