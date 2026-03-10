import asyncio
from datetime import datetime
import re
from typing import Dict, List, Tuple

from src.qubit.processing.prompt_dispatcher import PromptDispatcher
from config.config import MAX_NEW_TOKENS_FOR_REFLECTION_GENERATION
from src.utils.log_utils import get_logger

"""
Module for generating reflections from chat history.

This module provides functionality to analyze recent conversation messages and generate
insightful question-answer pairs that capture key aspects of the conversation. These Q&A
pairs are used to create memories for future interactions, improving the AI's contextual
understanding.

Classes:
    ReflectionGenerator: Handles the generation and parsing of reflection-based memories.
"""

class ReflectionGenerator:
    """
    A class to generate reflective question-answer pairs from recent chat history.

    This class interfaces with the chat history manager and response generator to create
    memories in the form of Q&A pairs that highlight important insights from conversations.
    """
    def __init__(self, dispatcher: PromptDispatcher = None, reflection_threshold: int = 20):
        """
        Initialize the ReflectionGenerator.
        """
        self.logger = get_logger("ReflectionGenerator")
        self.dispatcher = dispatcher
        self.reflection_threshold = reflection_threshold
        self.reflection_prompt = """
Given the following recent conversation messages, generate 3 high-level question-answer pairs that capture the most important and distinctive aspects of this conversation. Focus on insights, patterns, or key information that would be valuable to remember for future interactions.

Recent conversation:
{recent_messages}

Please format your response as exactly 3 question-answer pairs in this format:
Q1: [Question]
A1: [Answer]

Q2: [Question]
A2: [Answer]

Q3: [Question]
A3: [Answer]
"""

    async def perform_reflection(self, memory_manager) -> List[Tuple[str, str]]:
        """
        Perform reflection on recent messages to generate Q&A memories.

        Retrieves recent chat messages, formats them, and uses the response generator
        to create up to 3 insightful question-answer pairs that capture key aspects
        of the conversation.
        """
        self.logger.info("Starting reflection generation")
        recent_messages = memory_manager.get_recent_items("chat", limit=self.reflection_threshold)

        if len(recent_messages) < 10:
            self.logger.info("Not enough messages for reflection generation")   
            return []

        formatted_messages = []
        for msg in recent_messages:
            role = msg.get("role", "Unknown")
            content = msg.get("content", "")
            user_id = msg.get("user_id", "Unknown")
            if role == "User":
                formatted_messages.append(f"User {user_id}: {content}")
            else:
                formatted_messages.append(f"Qubit: {content}")

        messages_text = "\n".join(formatted_messages)

        reflection_messages = [
            {"role": "System", "content": "You are an AI assistant that analyzes conversations and creates insightful question-answer pairs."},
            {"role": "User", "content": self.reflection_prompt.format(recent_messages=messages_text)}
        ]

        self.logger.info("Generated reflection messages")
        try:
            if self.dispatcher is None:
                raise ValueError("Dispatcher not set for reflection generation")
            reflection_response = await self.dispatcher._generate_with_retries(
                prompt=reflection_messages
            )
            self.logger.info(f"Reflection response: {reflection_response}")

            qa_pairs = self._parse_qa_pairs(reflection_response)
            return qa_pairs

        except Exception as e:
            self.logger.error(f"Error during reflection generation: {e}")
            return []

    def _parse_qa_pairs(self, response: str) -> List[Tuple[str, str]]:
        """
        Parse question-answer pairs from the LLM's reflection response.

        Uses regex to extract Q&A pairs from the response string. If regex fails,
        falls back to line-by-line parsing. Ensures exactly 3 pairs are returned if possible.
        """
        qa_pairs = []

        qa_pattern = r'Q(\d+):\s*(.*?)\nA(\d+):\s*(.*?)(?=\nQ\d+:|$)'
        matches = re.findall(qa_pattern, response, re.DOTALL)

        for match in matches:
            q_num, question, a_num, answer = match
            if q_num == a_num:
                qa_pairs.append((question.strip(), answer.strip()))

        if not qa_pairs:
            lines = response.strip().split('\n')
            current_q = None
            current_a = None

            for line in lines:
                line = line.strip()
                if line.startswith('Q') and ':' in line:
                    if current_q and current_a:
                        qa_pairs.append((current_q, current_a))
                    current_q = line.split(':', 1)[1].strip()
                    current_a = None
                elif line.startswith('A') and ':' in line and current_q:
                    current_a = line.split(':', 1)[1].strip()

            if current_q and current_a:
                qa_pairs.append((current_q, current_a))

        return qa_pairs[:3]