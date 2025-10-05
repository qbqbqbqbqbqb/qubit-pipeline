# === Setup colorlog logger ===
import re
from scripts.utils.log_utils import get_logger
logger = get_logger("TextProcessor")

# === Setup sentence tokenisation ===
import nltk
from nltk.tokenize import sent_tokenize

class TextProcessor:
    @staticmethod
    def trim_to_last_sentence(text: str) -> str:
        """
        Returns text trimmed to the last full sentence according to the sentence tokeniser.
        """
        sentences = sent_tokenize(text)
        if not sentences:
            return ""
        if not text.endswith(('.', '!', '?')):
            sentences = sentences[:-1]
        return ' '.join(sentences).strip()

    @staticmethod
    def limit_sentences(text: str, max_sentences: int=3) -> str:
        """
        Limits text to a maximum number of sentences using the sentence tokeniser.
        """
        sentences = sent_tokenize(text)
        return ' '.join(sentences[:max_sentences]).strip()

    @staticmethod
    def limit_chars(text: str, max_chars: int=300) -> str:
        """
        Truncates the input text to a maximum character length without cutting off words abruptly.
        """
        if len(text) > max_chars:
            return text[:max_chars].rsplit(' ', 1)[0] + '...'
        return text

    @staticmethod
    def clean_and_limit_text(text: str, 
                             max_sentences: int=3, 
                             max_chars: int=300) -> str:
        """
        Cleans and limits the input text by trimming to full sentences, limiting sentence count, and truncating characters.
        """
        text = TextProcessor.trim_to_last_sentence(text)
        text = TextProcessor.limit_sentences(text, max_sentences)
        text = TextProcessor.limit_chars(text, max_chars)
        return text

    @staticmethod
    def contains_url(text: str) -> bool:
        """
        Checks if the input text contains a URL pattern.
        """
        url_pattern = re.compile(r'https?://\S+|www\.\S+|.com\S*', re.IGNORECASE)
        return bool(url_pattern.search(text))

    @staticmethod
    def clean_generated_text(text: str) -> str:
        """
        Cleans generated text by removing text consisting only of punctuation and stripping trailing punctuation,
        and removes sentences containing URLs.
        """
        if re.fullmatch(r"[:;,.!?\-]+", text.strip()):
            return ""
        text = text.strip().strip(":;,.!?-")
        sentences = text.split('. ')
        sentences = [s for s in sentences if not TextProcessor.contains_url(s)]
        return '. '.join(sentences).strip()
