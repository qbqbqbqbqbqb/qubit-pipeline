# qubit-pipeline
this is my pipeline for running qubit. if you are wondering why i did something a certain way, it is because i do not respect python as a language. thank you.

TODO - by priority
1. add in twitch raid, follow, & sub events
2. add controller class to control speech start
3. add mood class for more advanced prompt control
4. add STT detection with speech and response generation priority for STT
5. ability to send events from elsewhere so she can reference whats on screen

MAYBE
- add singing via audio files
- hook to vtube studio for movement (if she has model)
- youtube chat API?

summary i did not bother writing below
---------------------------------
## Overview

Qubit is a sophisticated AI-powered Vtuber application designed to interact with Twitch chat in real-time. It combines conversational AI, memory management, and text-to-speech synthesis to create an engaging interactive experience. The system is built with a modular architecture using asynchronous event-driven programming.

## Architecture

The application is organized into several key components:

### Core Components

- **Central Event Broker**: Manages asynchronous event communication between all modules using asyncio queues
- **Signals**: Provides coordination events for startup, termination, and module readiness
- **Broker Event Handler**: Processes incoming events, filters messages, and coordinates responses

### Managers

- **Model Manager**: Handles AI model loading and inference (singleton pattern)
- **Prompt Manager**: Manages system prompts and cached memory context
- **TTS Manager**: Loads and manages Piper text-to-speech models
- **OBS Manager**: Interfaces with OBS Studio for live streaming integration

### Modules

- **Memory Module**: Implements RAG (Retrieval-Augmented Generation) with ChromaDB for long-term memory
- **Monologue Module**: Generates autonomous speech content when not responding to chat
- **Response Generator Module**: Creates AI responses using language models
- **TTS Speech Module**: Converts text responses to speech and manages audio output
- **Twitch Module**: Handles Twitch IRC chat integration and message processing

### RAG (Retrieval-Augmented Generation) System

The rag/ directory contains specialized components for memory and reflection:

- **Memory Storage**: JSON-based memory persistence with semantic indexing
- **Memory Context Provider**: Retrieves relevant memories for prompt context
- **Memory Lifecycle Manager**: Handles memory consolidation, decay, and cleanup
- **Chat History Manager**: Manages ChromaDB collections for conversations and reflections
- **Reflection Generator**: Creates Q&A pairs from conversations for long-term learning
- **Async Event Handler**: Processes memory events asynchronously
- **User Profile Manager**: Tracks user interaction history and personality traits
- **Statistics Reporter**: Provides analytics on memory system performance

### Utilities

- **Dialogue Generation Utils**: Text processing for British English conversion and response filtering
- **File Utils**: File I/O operations for loading configurations and word lists
- **Filter Utils**: Content filtering for banned words and inappropriate content
- **Log Utils**: Colored logging with file rotation
- **Message Tracker**: Prevents spam and repeated responses
- **Rate Limiters**: Token bucket algorithm for response throttling
- **TTS Utils**: Text normalization for speech synthesis

### Configuration

- **config.py**: Static configuration constants and loaded data files
- **env_config.py**: Environment variable management using Pydantic

## Data Flow

1. **Input**: Twitch chat messages are received by the TwitchModule
2. **Filtering**: Messages are filtered for banned words, rate limiting, and repetition
3. **Event Processing**: Valid messages generate response_prompt events via the BrokerEventHandler
4. **Response Generation**: ResponseGeneratorModule creates AI responses using model and memory context
5. **Memory Integration**: MemoryModule provides relevant context from stored memories
6. **Speech Synthesis**: TTS modules convert responses to audio output
7. **Memory Storage**: Conversations and reflections are stored for future use

## Key Features

- **Real-time Chat Interaction**: Responds to Twitch chat messages instantly
- **Long-term Memory**: Remembers conversations and user preferences across sessions
- **Personality Adaptation**: Learns user traits and adjusts communication style
- **Content Moderation**: Filters inappropriate content and prevents spam
- **British English Conversion**: Automatically converts American to British spelling
- **Reflective Learning**: Generates insights from conversations for improved responses
- **Modular Design**: Easily extensible with new modules and features
- **Asynchronous Processing**: High-performance event-driven architecture

## Startup Process

1. Load configuration and environment variables
2. Initialize managers (Model, TTS, Prompt, OBS)
3. Start TTS and Response Generator modules in threads
4. Initialize Memory, Twitch, and Monologue modules
5. Set up event handling and signal management
6. Begin main event loop for coordination

## Memory System

The RAG system uses multiple storage mechanisms:

- **Semantic Memory**: Long-term knowledge stored in JSON files with semantic search
- **Episodic Memory**: User interaction records with emotional valence tracking
- **Reflective Memory**: Q&A pairs generated from conversation analysis
- **Chat History**: Temporary ChromaDB collections for recent interactions

## Dependencies

- **AI/ML**: Transformers, ChromaDB, spaCy
- **TTS**: Piper voice synthesis
- **Twitch**: twitchAPI library
- **OBS**: OBS WebSocket integration
- **Async**: asyncio for event handling
- **Data**: Pydantic for configuration, numpy for calculations

This pipeline creates an intelligent, memory-aware AI Vtuber capable of engaging conversations, learning from interactions, and maintaining personality consistency across streaming sessions.