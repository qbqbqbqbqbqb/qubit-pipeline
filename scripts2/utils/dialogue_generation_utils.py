import re
from scripts2.utils.log_utils import get_logger
from scripts2.config.config import BOT_NAME, EXCEPTIONS, IRREGULAR_PLURALS
from scripts2.utils.filter_utils import filter_banned_words
from typing import Dict
import spacy

nlp = spacy.load("en_core_web_sm")
logger = get_logger("Dialogue_Generation_Utils")

def is_valid_response(response: str, blacklist, whitelist: list[str] = None) -> tuple[bool, str]:
    """
    Check whether the generated response is valid and filter banned words.

    Returns (is_valid, filtered_response)
    """
    if not response.strip():
        logger.warning("[_is_valid_response] Empty response")
        return False, response
    
    filtered = filter_banned_words(text=response, blacklist=blacklist, whitelist=whitelist)
    if filtered != response:
        logger.warning(f"[_is_valid_response] Filtered banned words: {response} -> {filtered}")
    return True, filtered

def normalise_response(response: str):
    """Remove trailing text after the last piece of punctuation"""
    match = re.search(r'[.!?](?!.*[.!?])', response)
    if match:
        return response[:match.end()].strip()
    else:
        return response.strip()
    
def remove_bot_name(response: str):
    """Remove 'Bot:' from speech if it adds it"""
    bot_name_lower = BOT_NAME.lower()
    if response.lower().startswith(f"{bot_name_lower}:"):
        response = response[len(f"{bot_name_lower}:"):].lstrip()
    return response

def apply_spelling_rules(word: str) -> str:
    lower_word = word.lower()

    if lower_word in EXCEPTIONS:
        return word

    rules = [
        (r'(.*[^aeiou])ies$', lambda base: base + 'ies'),  # plural y (already plural)
        (r'([a-z]+)ize$', lambda base: base + 'ise'),
        (r'([a-z]+)izing$', lambda base: base + 'ising'),
        (r'([a-z]+)ized$', lambda base: base + 'ised'),
        (r'([a-z]+)or$', lambda base: base + 'our'),
        (r'([a-z]+)er$', lambda base: base + 're'),
    ]

    for pattern, repl in rules:
        match = re.fullmatch(pattern, lower_word)
        if match:
            base = match.group(1)
            converted = repl(base)
            if word.isupper():
                return converted.upper()
            elif word.istitle():
                return converted.capitalize()
            else:
                return converted

    return word

def convert_token(token, spelling_dict: Dict[str, str]) -> str:
    text = token.text
    lemma = token.lemma_.lower()

    if token.ent_type_ or token.pos_ in {"PROPN", "PUNCT", "NUM"}:
        return text

    if lemma in IRREGULAR_PLURALS:
        if token.tag_ in {"NNS", "NNPS"}:
            replacement = IRREGULAR_PLURALS[lemma]
        else:
            return text
    elif lemma in spelling_dict:
        replacement = spelling_dict[lemma]
    else:
        return apply_spelling_rules(text)

    if token.tag_ in {"NNS", "NNPS"}:
        if replacement.endswith('y'):
            replacement = replacement[:-1] + 'ies' 
        else:
            replacement += 's'
    elif token.tag_ == "VBG":
        replacement += 'ing'
    elif token.tag_ == "VBD":
        if re.match(r'.*[aeiou][^aeiou]$', replacement):
            replacement += 'led'
        else:
            replacement += 'ed'
    elif token.tag_ == "VBZ": 
        replacement += 's'

    if text.isupper():
        replacement = replacement.upper()
    elif text.istitle():
        replacement = replacement.capitalize()

    if replacement != text:
        logger.debug(f"{text} → {replacement}")

    return replacement


def convert_to_british_english(text: str, spelling_dict: Dict[str, str]) -> str:
    doc = nlp(text)
    converted = [convert_token(token, spelling_dict) for token in doc]
    return "".join(converted[i] + doc[i].whitespace_ for i in range(len(doc)))
