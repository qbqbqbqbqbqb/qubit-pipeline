from typing import Optional


class MemoryContextProvider:
    def __init__(self, memory_storage, chat_history_manager, reflection_generator, user_profile_manager):
        self.memory_storage = memory_storage
        self.chat_history_manager = chat_history_manager
        self.reflection_generator = reflection_generator
        self.user_profile_manager = user_profile_manager

    def get_memory_context(self, user_id: Optional[str] = None, current_topic: Optional[str] = None) -> str:
        """Generate memory context for prompts."""
        context_parts = []

        if current_topic:
            try:
                reflection_results = self.chat_history_manager.collection.query(
                    query_texts=[current_topic],
                    n_results=2
                )
                if reflection_results["documents"]:
                    reflections = reflection_results["documents"][0]
                    key_insights = '; '.join(reflections)
                    context_parts.append(f"Key insights: {key_insights}")
            except Exception as e:
                print(f"Error querying ChromaDB reflections: {e}")

        if user_id:
            user_profile = self.user_profile_manager.get_user_profile(user_id)
            if user_profile:
                personality_traits = user_profile.get("personality_traits", {})
                relationship_score = user_profile.get("relationship_score", 0.0)
                traits = [k for k, v in personality_traits.items() if isinstance(v, (int, float)) and v > 0]
                if traits:
                    context_parts.append(f"User personality traits: {', '.join(traits)}")
                context_parts.append(f"User relationship score: {relationship_score}")

            user_memories = self.memory_storage.retrieve_memories(
                user_id=user_id,
                memory_type="semantic",
                limit=2
            )
            if user_memories:
                memory_texts = [m.content for m in user_memories]
                user_info = '; '.join(memory_texts)
                context_parts.append(f"About user {user_id}: {user_info}")

        if current_topic:
            topic_memories = self.memory_storage.retrieve_memories(
                query=current_topic,
                limit=1,
                min_relevance=0.1
            )
            if topic_memories:
                memory_texts = [m.content for m in topic_memories]
                related = '; '.join(memory_texts)
                context_parts.append(f"Related memories: {related}")

        recent_memories = self.memory_storage.retrieve_memories(
            memory_type="semantic",
            limit=1
        )
        if recent_memories:
            memory_texts = [m.content for m in recent_memories]
            recent = '; '.join(memory_texts)
            context_parts.append(f"Recent context: {recent}")

        return "\n".join(context_parts) if context_parts else ""