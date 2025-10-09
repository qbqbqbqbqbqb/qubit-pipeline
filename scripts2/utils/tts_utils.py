import re
import inflect
p = inflect.engine()
from scripts2.config.config import ACRONYMS_LIST

def normalise_text_for_tts(text: str) -> str:
    text = remove_brackets_and_parentheses(text)
    text = remove_unsupported_chars(text)
    text = remove_quotes(text)
    text = convert_numbers_to_words(text, p.number_to_words)
    text = spell_out_acronyms(text, ACRONYMS_LIST)
    text = replace_ellipses(text)
    text = remove_consecutive_whitespace(text)

    return text

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

def replace_ellipses(text: str) -> str:
    """
    Replaces ellipses (...) and Unicode ellipsis (…) with a verbal filler phrase.
    """
    text = text.replace('…', ' dot dot dot ')
    return re.sub(r'\.\.\.+', ' dot dot dot ', text)

def remove_quotes(text: str) -> str:
    text = re.sub(r'[\"“”]', '', text)
    return text.strip()

def remove_consecutive_whitespace(text: str) -> str:
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def remove_unsupported_chars(text: str) -> str:
    """
    Remove emojis and special unicode not in ASCII range (adjust as needed)
    """
    return re.sub(r'[^\x00-\x7F]+', '', text).strip()

def remove_brackets_and_parentheses(text: str) -> str:
    """
    Removes content within square brackets and parentheses, including the brackets themselves.
    """
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    return text.strip()

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
