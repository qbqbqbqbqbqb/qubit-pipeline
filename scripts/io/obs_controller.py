import base64
import hashlib
import json
import websocket

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("OBS_Websocket_Controller")

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

OBS_PASSWORD = os.getenv("OBS_PASSWORD")
OBS_HOST = os.getenv("OBS_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_PORT", 4455))

url = f"ws://{OBS_HOST}:{OBS_PORT}"

def _build_auth_string(salt, challenge):
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
            hashlib.sha256((OBS_PASSWORD + salt).encode('utf-8')).digest()
        )
        auth = base64.b64encode(
            hashlib.sha256(secret + challenge.encode('utf-8')).digest()
        ).decode('utf-8')
        return auth
    except Exception as e:
        logger.error(f"Error building auth string: {e}")
        raise

def connect_to_obs():
    """
    Establish a WebSocket connection to OBS and authenticate.
    Returns:
        websocket.WebSocket: The authenticated WebSocket connection.
    """
    try:
        ws = websocket.WebSocket()
        ws.connect(url)
        message = ws.recv()
        result = json.loads(message)

        if 'authentication' in result['d']:
            auth_payload = {
                "op": 1,
                "d": {
                    "rpcVersion": 1,
                    "authentication": _build_auth_string(
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
        logger.error(f"Error connecting to OBS: {e}")
        raise

def update_obs_text(source_name, new_text):
    """
    Update the text of a specified text source in OBS.
    Args:
        source_name (str): The name of the text source in OBS.
        new_text (str): The new text to set.
    """
    try:
        ws = connect_to_obs()

        payload = {
            "op": 6,
            "d": {
                "requestId": "change_text",
                "requestType": "SetInputSettings",
                "requestData": {
                    "inputName": source_name,
                    "inputSettings": {
                        "text": new_text,
                        "use_custom_extents": True,
                        "custom_width": 1920,
                        "custom_height": 540
                    }
                }
            }
        }

        ws.send(json.dumps(payload))
        response = ws.recv()
        logger.info(f"Text updated: {response}")

    except Exception as e:
        logger.error(f"Failed to update text: {e}")
    finally:
        try:
            ws.close()
        except:
            pass

def set_subtitle_position(source_name, scene_name, x=0, y=540):
    """
    Set the position of a text source in the given OBS scene.
    Args:
        source_name (str): Name of the text source.
        scene_name (str): Name of the OBS scene containing the text source.
        x (int): Horizontal position in pixels.
        y (int): Vertical position in pixels.
    """
    try:
        ws = connect_to_obs()
        payload = {
            "op": 6,
            "d": {
                "requestId": "set_position",
                "requestType": "SetSceneItemTransform",
                "requestData": {
                    "sceneName": scene_name,
                    "sceneItemName": source_name,
                    "sceneItemTransform": {
                        "position": {
                            "x": x,
                            "y": y
                        }
                    }
                }
            }
        }
        ws.send(json.dumps(payload))
        response = ws.recv()
        logger.info(f"Subtitle position updated: {response}")
    except Exception as e:
        logger.error(f"Failed to set subtitle position: {e}")
    finally:
        try:
            ws.close()
        except:
            pass

def update_subtitle_text_and_style(
    source_name, new_text, font_face="Arial", font_size=24,
    width=1920, height=540, valign="top", word_wrap=True
):
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
        ws = connect_to_obs()
        # OBS font flags: 1 = word_wrap enabled
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
        logger.info(f"Subtitle text and style updated: {response}")
    except Exception as e:
        logger.error(f"Failed to update subtitle text and style: {e}")
    finally:
        try:
            ws.close()
        except:
            pass
