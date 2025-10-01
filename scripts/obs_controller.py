import base64
import hashlib
import json
import websocket

# === Setup colorlog logger ===
from log_utils import get_logger
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
    secret = base64.b64encode(
        hashlib.sha256((OBS_PASSWORD + salt).encode('utf-8')).digest()
    )
    auth = base64.b64encode(
        hashlib.sha256(secret + challenge.encode('utf-8')).digest()
    ).decode('utf-8')
    return auth

def connect_to_obs():
    """
    Establish a WebSocket connection to OBS and authenticate.
    Returns:
        websocket.WebSocket: The authenticated WebSocket connection.
    """
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
                    "inputSettings": {"text": new_text}
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

def set_text_scroll_speed(source_name, filter_name, text):
    """
    Set the scroll speed of a text source filter in OBS based on text length.
    Args:
        source_name (str): The name of the text source in OBS.
        filter_name (str): The name of the filter applied to the text source.
        text (str): The current text to determine scroll speed.
    """
    try:
        ws = connect_to_obs()

        base_speed = 50
        speed_per_char = 5
        max_speed = 1000

        speed = min(base_speed + len(text) * speed_per_char, max_speed)

        payload = {
            "op": 6,
            "d": {
                "requestId": "set_scroll_speed",
                "requestType": "SetSourceFilterSettings",
                "requestData": {
                    "sourceName": source_name,
                    "filterName": filter_name,
                    "filterSettings": {
                        "speed_x": speed,
                    }
                }
            }
        }

        ws.send(json.dumps(payload))
        response = ws.recv()
        logger.info(f"Scroll speed updated: {response}")

    except Exception as e:
        logger.error(f"Failed to set scroll speed: {e}")
    finally:
        try:
            ws.close()
        except:
            pass