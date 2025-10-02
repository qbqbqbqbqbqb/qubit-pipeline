import re
import inflect
from TTS.api import TTS
import concurrent.futures
import pyaudio
import asyncio
import numpy as np
from obs_controller import update_obs_text, set_text_scroll_speed

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

TTS_SUBTITLE_NAME = os.getenv("TTS_SUBTITLE_NAME", "TTS_Subtitles")

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("TTS_Utils")

# === Import TTS model ===
p = inflect.engine()
tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)
tts.synthesizer.tts_model.decoder.max_decoder_steps = 2000
executor = concurrent.futures.ThreadPoolExecutor()

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
    
    set_text_scroll_speed(TTS_SUBTITLE_NAME, "Scroll", normalised_text)  
    update_obs_text(TTS_SUBTITLE_NAME, normalised_text)

    loop = asyncio.get_running_loop()
    wav = await loop.run_in_executor(None, lambda: tts.tts(normalised_text))

    if isinstance(wav, list):
        wav = np.array(wav)

    wav = np.array(wav)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    
    if len(wav) == 0:
        logger.warning("[TTS] Generated empty audio, skipping playback.")
        return
    
    max_val = np.max(np.abs(wav))
    if max_val > 0:
        wav = wav / max_val
    wav = np.clip(wav, -1.0, 1.0)

    logger.debug(f"[TTS] Audio waveform length: {len(wav)}, min: {wav.min()}, max: {wav.max()}")

    audio_data = (wav * 32767).astype(np.int16)

    def play_audio(audio_data: np.ndarray, sample_rate: int):
        pa = pyaudio.PyAudio()

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            output=True
        )
        stream.write(audio_data.tobytes())
        stream.stop_stream()
        stream.close()
        pa.terminate()

    await loop.run_in_executor(
        None, 
        play_audio, 
        audio_data, 
        tts.synthesizer.output_sample_rate)
