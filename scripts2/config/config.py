from twitchAPI.type import AuthScope
from scripts2.utils.file_utils import load_file, get_root, get_file_path, load_word_list

BOT_SCOPES = [
    AuthScope.CHAT_READ,
    AuthScope.CHAT_EDIT
]

STREAMER_SCOPES = [
    AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
    AuthScope.CHANNEL_MANAGE_RAIDS
]

MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION = 100
MAX_GENERATION_ATTEMPTS = 3

TTS_SPEAKER_NAME = "p236"
TTS_MODEL_NAME= "en_GB-vctk-medium.onnx"
TTS_DELAY = 1.5

ROOT = get_root()
INSTRUCTIONS_FILENAME = "instructions.txt"
INSTRUCTIONS_PATH = get_file_path(ROOT, INSTRUCTIONS_FILENAME)
INSTRUCTIONS_FILE = load_file(INSTRUCTIONS_PATH)

BANNED_WORDS_FILENAME = "banned_words.txt"
BANNED_WORDS_PATH = get_file_path(ROOT, BANNED_WORDS_FILENAME)
BANNED_WORDS_LIST = load_word_list(BANNED_WORDS_PATH)

ACRONYMS_LIST_FILENAME = "acronyms.txt"
ACRONYMS_LIST_PATH = get_file_path(ROOT, ACRONYMS_LIST_FILENAME)
ACRONYMS_LIST = load_word_list(ACRONYMS_LIST_PATH)