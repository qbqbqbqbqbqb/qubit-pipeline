import re
import inflect
from TTS.api import TTS
import concurrent.futures
import pyaudio
import asyncio
import numpy as np
from obs_controller import update_obs_text, set_subtitle_position, update_subtitle_text_and_style
import wave
from piper import PiperVoice, SynthesisConfig
from pathlib import Path
import io
import json

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

TTS_SUBTITLE_NAME = os.getenv("TTS_SUBTITLE_NAME", "TTS_Subtitles")
SCENE_NAME = os.getenv("SCENE_NAME")

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("TTS_Utils")

# === Import TTS model ===
p = inflect.engine()

this_file = Path(__file__).resolve()
project_root = this_file.parent.parent

MODEL_PATH = project_root / "en_GB-vctk-medium.onnx"
SPEAKER_NAME = "p236"

voice = PiperVoice.load(MODEL_PATH)

# === Normalise text for TTS ===
def remove_unsupported_chars(text: str) -> str:
    """
    Remove emojis and special unicode not in ASCII range (adjust as needed)
    """
    return re.sub(r'[^\x00-\x7F]+', '', text)

def remove_brackets_and_parentheses(text: str) -> str:
    """
    Removes content within square brackets and parentheses, including the brackets themselves.
    """
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    return text

def convert_numbers_to_words(text: str, converter) -> str:
    """
    Converts standalone digit sequences to their word equivalents using the provided converter function.
    
    Args:
        text (str): Input text containing numbers.
        converter (callable): Function to convert numbers to words (e.g., `p`).
    """
    def replace_numbers(match):
        return converter(match.group(0))
    return re.sub(r'\b\d+\b', replace_numbers, text)

def strip_edge_punctuation(text: str) -> str:
    """
    Removes orphan punctuation characters from the start and end of the text.
    """
    text = re.sub(r'^[!?.,;:\-–—]+', '', text)
    text = re.sub(r'[!?.,;:\-–—]+$', '', text)
    return text

def replace_ellipses(text: str) -> str:
    """
    Replaces ellipses (...) and Unicode ellipsis (…) with a verbal filler phrase.
    """
    text = text.replace('…', ' dot dot dot ')
    return re.sub(r'\.\.\.+', ' dot dot dot ', text)

def collapse_repeated_punctuation(text: str) -> str:
    """
    Collapses repeated punctuation marks into a single instance.
    """
    return re.sub(r'([!?.,]){2,}', r'\1', text)

def ensure_spacing_after_punctuation(text: str) -> str:
    """
    Ensures there is a space after punctuation marks where missing.
    """
    return re.sub(r'([!?.,])([^\s])', r'\1 \2', text)

def spell_out_acronyms(text: str, acronyms: list[str]) -> str:
    """
    Replaces known acronyms with their spelled-out versions for clearer TTS pronunciation.
    
    Args:
        acronyms (list[str]): List of acronyms to spell out.
    """
    for acronym in acronyms:
        text = re.sub(
            r'\b' + re.escape(acronym) + r'\b', 
            ' '.join(acronym), 
            text, 
            flags=re.IGNORECASE
        )
    return text

def remove_urls(text: str) -> str:
    """
    Removes URLs and domain-like patterns from the input text.
    """
    url_pattern = re.compile(
        r"""
        (https?://\S+)|
        (www\.\S+)| 
        (\b\S+\.(com|org|net|co|io|gov|edu)(\/\S*)?)  
        """,
        re.IGNORECASE | re.VERBOSE
    )
    return re.sub(url_pattern, '', text)

def remove_trailing_punctuation(text: str) -> str:
    """
        Removes trailing punctuation marks such as periods, exclamation points, and question marks from the end of the text.
    """
    return re.sub(r'[.!?]+$', '', text).strip()

def collapse_repeated_words(text: str) -> str:
    """
    Collapses consecutive repeated words into a single instance.
    """
    return re.sub(r'\b(\w+)( \1\b)+', r'\1', text)

def normalise_text(text: str, number_converter) -> str:
    """
    Prepares text for TTS by cleaning and normalising it:
    - Removes bracketed/parenthetical content
    - Converts numbers to words
    - Strips leading/trailing punctuation
    - Replaces ellipses with verbal filler
    - Collapses repeated punctuation
    - Ensures proper spacing after punctuation
    - Spells out acronyms for clarity
    
    Args:
        text (str): Raw input text.
        number_converter (callable): Function to convert numbers to words (e.g., `p`).
    
    Returns:
        str: Cleaned and normalised text ready for TTS.
    """
    text = remove_urls(text)
    text = remove_brackets_and_parentheses(text)
    text = convert_numbers_to_words(text, number_converter)
    text = strip_edge_punctuation(text)
    text = replace_ellipses(text)
    text = collapse_repeated_punctuation(text)
    text = ensure_spacing_after_punctuation(text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = remove_unsupported_chars(text)
    text = collapse_repeated_words(text)

    acronyms = ["PC", "CPU", "GPU", "RAM", "QB", "QBOT", "USB", "HTTP", "HTTPS", "API", "ID", "TV", "LOL", "BRB", "GTG", "AFK", 
                "IMHO", "FYI", "DIY", "ETA", "ASAP", "TTS", "AI", "VR", "AR", "IP", "LAN", "WAN", "SSID", "DM", "PM", "GMT", 
                "UTC", "FBI", "CIA", "NSA", "NASA", "HTML", "CSS", "JS", "JSON", "XML", "SQL", "HTTP", "HTTPS"]
    text = spell_out_acronyms(text, acronyms)

    if not text.endswith(('.', '!', '?')):
        text += '.'

    return text

# === TTS Output ===
def get_speaker_id(model_path: Path, speaker_name: str) -> int:
    """
    Retrieves the speaker ID for the given speaker name from the model's JSON configuration.
    """
    json_path = model_path.with_suffix(".onnx.json")
    with open(json_path, "r") as f:
        config = json.load(f)
    return config["speaker_id_map"][speaker_name]

def build_synthesis_config(speaker_id: int) -> SynthesisConfig:
    """
    Builds a SynthesisConfig object with specified parameters.
    """
    return SynthesisConfig(
        speaker_id=speaker_id,
        length_scale=1.0,
        noise_scale=0.667,
        noise_w_scale=0.8,
        volume=1.0,
        normalize_audio=True
    )

def generate_wav_bytes(text: str, syn_config: SynthesisConfig) -> bytes:
    """
    Generates WAV audio bytes from the given text using the specified synthesis configuration.
    """
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)
        return wav_io.getvalue()

def decode_wav_bytes(wav_data: bytes) -> tuple[int, np.ndarray]:
    """
    Decodes WAV byte data into a sample rate and NumPy array of audio samples."""
    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            audio_data = wav_file.readframes(wav_file.getnframes())
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
    return sample_rate, audio_np

def play_audio(sample_rate: int, audio_np: np.ndarray):
    """
    Plays the given audio NumPy array using PyAudio."""
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        output=True
    )
    stream.write(audio_np.tobytes())
    stream.stop_stream()
    stream.close()
    pa.terminate()

async def speak_from_prompt(text):
    """
    Normalises text, converts it to speech, plays the audio.

    Args:
        text (str): Text to be spoken.
    """
    normalised_text = normalise_text(text, p.number_to_words)

    if not normalised_text or re.fullmatch(r'[.!?]+', normalised_text.strip()):
        logger.warning("[TTS] No valid text to speak after normalisation.")
        return

    logger.info(f"\n[Normalised Text for TTS]\n{normalised_text}")

    update_subtitle_text_and_style(
    source_name=TTS_SUBTITLE_NAME,
    new_text=normalised_text,
    font_face="Arial",
    font_size=50,
    width=1920,
    height=400,
    valign="center",
    word_wrap=True
)


    speaker_id = get_speaker_id(MODEL_PATH, SPEAKER_NAME)
    syn_config = build_synthesis_config(speaker_id)
    wav_bytes = generate_wav_bytes(normalised_text, syn_config)
    sample_rate, audio_np = decode_wav_bytes(wav_bytes)

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, play_audio, sample_rate, audio_np)
