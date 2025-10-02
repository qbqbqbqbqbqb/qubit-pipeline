import re
import torch
from vllm import LLM, SamplingParams
from transformers import AutoProcessor

# === Setup sentence tokenisation ===
import nltk
from nltk.tokenize import sent_tokenize

nltk.download('punkt') 
nltk.download('punkt_tab')

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("Dialogue_Model_Utils")

MODEL_NAME = "RedHatAI/gemma-3-4b-it-quantized.w4a16"

# === Load LLAMA2 model ===
processor = AutoProcessor.from_pretrained(MODEL_NAME, trust_remote_code=False)
llm = LLM(model=MODEL_NAME, trust_remote_code=False)
logger.info(f"[Dialogue_Model_Utils] Loaded model: {MODEL_NAME}")

# === Utility Functions ===
def trim_to_last_sentence(text):
    """
    Returns text trimmed to the last full sentence according to the sentence tokeniser.
    """
    sentences = sent_tokenize(text)
    if not sentences:
        return ""
    if not text.endswith(('.', '!', '?')):
        sentences = sentences[:-1]
    return ' '.join(sentences).strip()

def limit_sentences(text, max_sentences=3):
    """
    Limits text to a maximum number of sentences using the sentence tokeniser.
    """
    sentences = sent_tokenize(text)
    return ' '.join(sentences[:max_sentences]).strip()

def limit_chars(text, max_chars=300):
    """
    Truncates the input text to a maximum character length without cutting off words abruptly.
    """
    if len(text) > max_chars:
        return text[:max_chars].rsplit(' ', 1)[0] + '...'
    return text

def clean_and_limit_text(text, max_sentences=3, max_chars=300):
    """
    Cleans and limits the input text by trimming to full sentences, limiting sentence count, and truncating characters.
    """
    text = trim_to_last_sentence(text)
    text = limit_sentences(text, max_sentences)
    text = limit_chars(text, max_chars)
    return text

def contains_url(text):
    """
    Checks if the input text contains a URL pattern.
    """
    url_pattern = re.compile(r'https?://\S+|www\.\S+|.com\S*', re.IGNORECASE)
    return bool(url_pattern.search(text))

def clean_generated_text(text):
    """
    Cleans generated text by removing text consisting only of punctuation and stripping trailing punctuation,
    and removes sentences containing URLs.
    """
    if re.fullmatch(r"[:;,.!?\-]+", text.strip()):
        return ""
    text = text.strip().strip(":;,.!?-")
    sentences = text.split('. ')
    sentences = [s for s in sentences if not contains_url(s)]
    return '. '.join(sentences).strip()

# === Core Function ===
def build_chat_prompt(user_prompt: str, system_instruction: str = None) -> str:
    """
    Constructs a prompt using a chat template, including optional system instructions.
    """
    if not system_instruction:
        system_instruction = "Please respond without including any links, URLs, or web addresses.\n\n"
    
    chat = [
        {"role": "user", "content": [{"type": "text", "text": system_instruction + user_prompt}]},
        {"role": "assistant", "content": []},
    ]
    return processor.apply_chat_template(chat, add_generation_prompt=True)

def get_sampling_params(max_tokens: int) -> SamplingParams:
    """
    Configures and returns sampling parameters for generation.
    """
    return SamplingParams(
        temperature=0.7,
        top_p=0.95,
        top_k=50,
        max_tokens=max_tokens,
        bad_words=["http", "https", "www", ".com", ".net", ".org", ".io", ".gov", ".edu"],
        repetition_penalty=1.2,
    )

def generate_text(prompt: str, max_tokens: int) -> str:
    """
    Performs the text generation call using the LLM.
    """
    logger.debug("[generate_text] Starting generation...")
    inputs = {"prompt": prompt, "multi_modal_data": {}}
    sampling_params = get_sampling_params(max_tokens)
    outputs = llm.generate(inputs, sampling_params)
    text = outputs[0].outputs[0].text.strip()
    logger.debug(f"[generate_text] Raw output: {text[:60]}...")
    return text

def safe_clean_response(text: str, fallback: str = "Sorry, I couldn't generate a response.") -> str:
    """
    Cleans, limits, and safely returns the final response.
    """
    cleaned = clean_and_limit_text(text, max_sentences=3, max_chars=300)
    return cleaned if cleaned.strip() else fallback

def generate_response(user_prompt: str, max_new_tokens: int = 100) -> str:
    """
    Orchestrates the generation of a cleaned and constrained model response.
    """
    try:
        logger.info(f"[generate_response] Prompt received: {user_prompt[:60]}...")
        full_prompt = build_chat_prompt(user_prompt)
        raw_output = generate_text(full_prompt, max_new_tokens)
        final_response = safe_clean_response(raw_output)
        logger.info(f"[generate_response] Final response: {final_response}")
        return final_response

    except Exception:
        logger.exception("[generate_response] Exception during generation")
        return "Something went wrong!"