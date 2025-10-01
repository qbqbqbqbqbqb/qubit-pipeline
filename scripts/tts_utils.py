import re
import inflect
from TTS.api import TTS
import concurrent.futures
import os
import simpleaudio as sa

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("TTS_Utils")

# === Import TTS model ===
p = inflect.engine()
tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)
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
    text = remove_brackets_and_parentheses(text)
    text = convert_numbers_to_words(text, number_converter)
    text = strip_edge_punctuation(text)
    text = replace_ellipses(text)
    text = collapse_repeated_punctuation(text)
    text = ensure_spacing_after_punctuation(text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = remove_unsupported_chars(text)

    acronyms = ["PC", "CPU", "GPU", "RAM", "QB"]
    text = spell_out_acronyms(text, acronyms)

    return text

# === TTS Output ===
async def speak_from_prompt(text, output_audio="output.wav"):
    """
    Normalises text, converts it to speech, plays the audio, and deletes the file.

    Args:
        text (str): Text to be spoken.
        output_audio (str): Path to temporary audio file (default: "output.wav").
    """
    normalised_text = normalise_text(text, p.number_to_words)
    logger.info(f"\n[Normalised Text for TTS]\n{normalised_text}")
    
    tts.tts_to_file(text=normalised_text, file_path=output_audio, max_decoder_steps=500)

    logger.info(f"[Audio saved to]: {output_audio}")

    wave_obj = sa.WaveObject.from_wave_file(output_audio)
    play_obj = wave_obj.play()
    play_obj.wait_done() 

    try:
        os.remove(output_audio)
        logger.debug(f"[Deleted audio file]: {output_audio}")
    except Exception as e:
        logger.error(f"Error deleting audio file: {e}")
