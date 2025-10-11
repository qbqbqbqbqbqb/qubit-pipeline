import asyncio
from datetime import datetime
import re
from typing import Dict, List, Tuple

from scripts2.modules.response_generator_module import ResponseGeneratorModule
from scripts2.config.config import MAX_NEW_TOKENS_FOR_REFLECTION_GENERATION


class ReflectionGenerator:
    def __init__(self, chat_history_manager, response_generator: ResponseGeneratorModule, reflection_threshold: int = 20):
        self.chat_history_manager = chat_history_manager
        self.response_generator = response_generator
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

    async def _perform_reflection(self) -> List[Tuple[str, str]]:
        """Perform reflection on recent messages to generate Q&A memories."""
        recent_messages = self.chat_history_manager.get_recent_chat_history(limit=self.reflection_threshold)

        if len(recent_messages) < 10:
            return []

        formatted_messages = []
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            user_id = msg.get("user_id", "unknown")
            if role == "user":
                formatted_messages.append(f"User {user_id}: {content}")
            else:
                formatted_messages.append(f"Assistant: {content}")

        messages_text = "\n".join(formatted_messages)

        reflection_messages = [
            {"role": "system", "content": "You are an AI assistant that analyzes conversations and creates insightful question-answer pairs."},
            {"role": "user", "content": self.reflection_prompt.format(recent_messages=messages_text)}
        ]

        try:
            reflection_response = await self.response_generator._generate_response_with_retries(
                prompt=reflection_messages,
                use_system_prompt=False,
                max_new_tokens=MAX_NEW_TOKENS_FOR_REFLECTION_GENERATION,
            )

            qa_pairs = self._parse_qa_pairs(reflection_response)
            return qa_pairs

        except Exception as e:
            return []

    def _parse_qa_pairs(self, response: str) -> List[Tuple[str, str]]:
        """Parse Q&A pairs from LLM reflection response."""
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