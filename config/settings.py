"""
config/settings.py

Non-sensitive application settings. Safe to commit to version control.

For secrets and machine-specific config (tokens, ports, device indices),
see .env loaded via config/env_config.py.

For the system prompt, edit src/data/system_prompt.txt directly.
"""

# === Bot identity ===
BOT_NAME = "Qubit"
STREAM_TYPE = "Just Chatting"

# === Personality defaults ===
# These are the starting values. The frontend can override them at runtime.
DEFAULT_MOOD = "energetic"
DEFAULT_TONE = "casual and humorous"
DEFAULT_INTERACTION_LEVEL = "high"  # "low" | "medium" | "high"

# === TTS ===
TTS_SPEAKER_NAME = "p236"
TTS_MODEL_NAME = "en_GB-vctk-medium.onnx"
TTS_DELAY = 1.5  # seconds between TTS playback and next action
TTS_SUBTITLE_NAME = "TTS_Subtitles"  # OBS source name for subtitle overlay

# === Memory ===
REFLECTIONS_THRESHOLD = 5  # number of unreflected entries before a reflection job runs

# === Vision ===
# Which vision model to use: "moondream2" (fast, ~1.8GB) or "llava" (better detail, ~4GB 4-bit)
VISION_MODEL = "moondream2"
# Seconds between screen captures when vision is on
VISION_INTERVAL_SECONDS = 45
# Default window title to capture — can be overridden at runtime from the frontend
VISION_WINDOW_TITLE = ""