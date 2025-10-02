from transformers import AutoTokenizer, AutoModelForCausalLM
import re
import torch

# === Setup sentence tokenisation ===
import nltk
from nltk.tokenize import sent_tokenize

nltk.download('punkt') 

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("GPT_Utils")

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "TheBloke/Llama-2-7b-chat-GPTQ")

# === Load LLAMA2 model ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"[Speech_Model_Utils] Using device: {device}")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto",
    trust_remote_code=False,
    dtype=torch.float16
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
tokenizer.pad_token = tokenizer.eos_token
logger.info(f"[Speech_Model_Utils] Loaded model: {MODEL_NAME}")

# === Prompt Formatting ===
def format_prompt(system_prompt: str, user_prompt: str) -> str:
    return f"""<s>[INST] <<SYS>>
{system_prompt}
<</SYS>>

{user_prompt} [/INST]
"""

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
def generate_response(user_prompt, max_new_tokens=100):
    """
    Generates a text response from a model given an input prompt, while filtering out URLs and limiting output length.

    The function:
    - Adds a system instruction to avoid generating URLs.
    - Tokenises and optionally truncates the input to fit model context limits.
    - Generates text with sampling parameters and constraints.
    - Decodes the generated tokens back to text.
    - Removes the original prompt from the generated output.
    - Cleans and limits the response by sentences and character length.
    - Logs key steps and handles exceptions gracefully.

    Args:
        prompt (str): The input text prompt to generate a response for.
        max_new_tokens (int, optional): The maximum number of new tokens to generate. Default is 200.

    Returns:
        str: The cleaned, limited generated text response, or an error message if generation fails.
    """
    try:
        logger.info(f"[generate_response] Received prompt: {user_prompt[:60]}...")

        system_instruction = "Please respond without including any links, URLs, or web addresses.\n\n"
        prompt = format_prompt(system_instruction, user_prompt)
        logger.debug(f"[generate_response] Created full prompt")

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        logger.debug(f"[generate_response] Tokenised input")

        max_context_len = 4096
        if inputs["input_ids"].size(1) > max_context_len - max_new_tokens:
                inputs["input_ids"] = inputs["input_ids"][:, -(max_context_len - max_new_tokens):]
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        logger.debug(f"[generate_response] Truncated input_ids to fit context length")
            
        bad_words = ["http", "www", "https", ".com"]
        bad_words_ids = [
            tokenizer.encode(word, add_special_tokens=False) 
            for word in bad_words
            if len(tokenizer.encode(word, add_special_tokens=False)) > 0
            ]
        logger.debug(f"[generate_response] bad_words_ids: {bad_words_ids}")

        #model.to(device)
        logger.debug(f"[generate_response] Calling model.generate()...")
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            top_k=50,
            top_p=0.95,
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.2,
            no_repeat_ngram_size=2,
            bad_words_ids=bad_words_ids,
        )
        logger.debug(f"[generate_response] Model generation completed")

        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        if "[/INST]" in generated_text:
            generated_text = generated_text.split("[/INST]", 1)[-1].strip()

        logger.debug(f"[generate_response] Raw generated text: {generated_text[:60]}...")

        final_response = clean_and_limit_text(generated_text, max_sentences=3, max_chars=300)

        if not final_response.strip():
            logger.warning("[generate_response] Generated empty response, returning fallback text.")
            final_response = "Sorry, I couldn't generate a response. Please try again."

        logger.info(f"[generate_response] Final response: {final_response}")
        return final_response

    except Exception as e:
        logger.exception("[generate_response] Exception occurred during response generation")
        return "Something went wrong!"