"""
Configuration module for qubit

This module defines constants, authentication scopes, token limits, TTS settings,
and loads external configuration files such as instructions, word lists, and dictionaries.
"""

from twitchAPI.type import AuthScope
from scripts2.utils.file_utils import load_text_file, get_root, get_file_path, load_word_list, load_phrases, load_json_file

BOT_SCOPES = [
    AuthScope.CHAT_READ,
    AuthScope.CHAT_EDIT
]

STREAMER_SCOPES = [
    AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
    AuthScope.CHANNEL_MANAGE_RAIDS
]

MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION = 50
MAX_NEW_TOKENS_FOR_REFLECTION_GENERATION = 200
MAX_GENERATION_ATTEMPTS = 3

TTS_SPEAKER_NAME = "p236"
TTS_MODEL_NAME= "en_GB-vctk-medium.onnx"
TTS_DELAY = 1.5

ROOT = get_root()
INSTRUCTIONS_FILENAME = "instructions.txt"
INSTRUCTIONS_PATH = get_file_path(ROOT, INSTRUCTIONS_FILENAME)
INSTRUCTIONS_FILE = load_text_file(INSTRUCTIONS_PATH)

BLACKLISTED_WORDS_FILENAME = "blacklisted_words.txt"
BLACKLISTED_WORDS_PATH = get_file_path(ROOT, BLACKLISTED_WORDS_FILENAME)
BLACKLISTED_WORDS_LIST = load_word_list(BLACKLISTED_WORDS_PATH)

WHITELISTED_WORDS_FILENAME = "whitelisted_words.txt"
WHITELISTED_WORDS_PATH = get_file_path(ROOT, WHITELISTED_WORDS_FILENAME)
WHITELISTED_WORDS_LIST = load_word_list(WHITELISTED_WORDS_PATH)

ACRONYMS_LIST_FILENAME = "acronyms.txt"
ACRONYMS_LIST_PATH = get_file_path(ROOT, ACRONYMS_LIST_FILENAME)
ACRONYMS_LIST = load_word_list(ACRONYMS_LIST_PATH)

MONOLOGUE_PROMPTS_FILENAME = "monologue_prompts.txt"
MONOLOGUE_PROMPTS_PATH = get_file_path(ROOT, MONOLOGUE_PROMPTS_FILENAME)
MONOLOGUE_PROMPTS_FILE = load_phrases(MONOLOGUE_PROMPTS_PATH)

SPELLING_DICTIONARY_FILENAME = "am_to_br_english.json"
SPELLING_DICTIONARY_PATH = get_file_path(ROOT, SPELLING_DICTIONARY_FILENAME)
SPELLING_DICTIONARY_FILE = load_json_file(SPELLING_DICTIONARY_PATH)

EXCEPTIONS = {"analysis", "thesis", "crisis", "basis"}
IRREGULAR_PLURALS = {
    "analysis": "analyses",
    "thesis": "theses",
    "crisis": "crises",
    "basis": "bases",
}

TTS_SUBTITLE_NAME="TTS_Subtitles"

BOT_NAME = "Qubit"