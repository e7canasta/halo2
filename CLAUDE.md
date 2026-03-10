# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
make install    # Install dependencies and package (uv sync && uv pip install -e .)
make server     # Start FastAPI server on port 8000
make chat       # Run CLI chat interface
make test       # Run tests (uv run python test/test_halo_qwen.py)
make clean      # Clean cache files
```

Run a single test: `uv run python test/<test_file>.py`

## Architecture

Halo is a local AI inference server optimized for edge computing (i7 CPU without GPU). It provides OpenAI-compatible APIs and a tool-based orchestration system for home automation using Qwen 3.5-0.8B model.

### Core Components

**Backend Layer** (`src/halo/backend/`)
- `base.py`: Abstract `Backend` class defining `initialize()` and `generate()` interface
- `qwen/backend.py`: `QwenBackend` with chat templates, real token counting, and message formatting
- `provider.py`: Singleton pattern to ensure only ONE model instance is loaded (critical for RAM)

**Tool Framework** (`src/halo/tools/`)
- `registry.py`: Tool definitions with JSON Schema (OpenAI function calling style)
- `executor.py`: Tool execution and result coordination
- `pipeline.py`: Complete execution pipeline with pre/post filters (quality-first)
- `handlers/`: Mock handlers for lights, climate, blinds, status (swap for real MQTT)
- `filters/`: Intercepting Filter Pattern for validation and formatting
  - `pre_execution/`: SchemaValidator, ContextEnricher, ParameterNormalizer
  - `post_execution/`: ResultValidator, ContextUpdater, NLGFormatter

**MQTT Integration** (`src/halo/mqtt/`)
- `client.py`: MQTT client wrapper (paho-mqtt)
- `topics.py`: Topic naming conventions (halo/command/*, halo/state/*, halo/response/*)
- `correlation.py`: Request/Response correlation with 3s timeout for edge

**API Layer** (`src/halo/api/`)
- `server.py`: FastAPI application with dependency injection
- `models.py`: Shared Pydantic models (CommandRequest, CommandResponse, ToolCall, etc.)
- Routes:
  - `openai_routes.py`: OpenAI-compatible endpoints with real token counting
  - `custom_routes.py`: Simple `/generate` endpoint
  - `command_routes.py`: Tool-based orchestration (NEW - primary endpoint)
  - `home_routes.py`: Legacy context-based endpoint

**Context Management** (`src/halo/context/`)
- `manager.py`: Token-aware conversation context (max 512 tokens for history = 25% of window)

**CLI Layer** (`src/halo/cli/__init__.py`)
- `HaloClient`: HTTP client for `/generate`
- `HomeAssistantClient`: Client for `/command` with context tracking
- `OpenAIClient`: Client for OpenAI-compatible endpoints

**Chat Interface** (`src/halo/chat.py`)
- Two modes: `chat` (conversational) and `command` (home assistant with tools)
- Uses `prompt_toolkit` for interactive prompts

### Request Flow (Quality-First Pipeline)

```
User Input → Intent Classification Chain
                ↓
        ExactMatch → Embedding → Keyword → LLM
                ↓
        Tool Call Identified
                ↓
        Pre-Execution Filters (ALL run)
                ├── SchemaValidator (validate params)
                ├── ParameterNormalizer (salon→sala)
                └── ContextEnricher (add missing params)
                ↓
        Tool Execution → MQTT Command
                ↓
        Post-Execution Filters (ALL run)
                ├── ResultValidator (check format)
                ├── NLGFormatter (JSON→natural language)
                └── ContextUpdater (update conversation state)
                ↓
        Response to User
```

### Key Design Patterns

1. **Singleton Backend**: Only ONE Qwen model instance via `get_backend()` dependency
2. **Chain of Responsibility**: Intent classification chain (ExactMatch → Embedding → Keyword → LLM)
3. **Intercepting Filter Pattern**: Pre/post execution filters for validation and formatting
   - Philosophy: **QUALITY > SPEED** - ALL filters execute for comprehensive validation
   - Pre-filters: Schema validation, parameter normalization, context enrichment
   - Post-filters: Result validation, NLG formatting, context updates
4. **Fire-and-forget MQTT**: 3s timeout, returns "pending" if no immediate response
5. **Token-efficient prompts**: Compact system prompts (~100 tokens vs 400)
6. **Mock handlers**: Swappable for real MQTT integration
7. **Correlation IDs**: Track async MQTT request/response pairs
8. **Learning Loop**: Successful classifications are cached for future reuse (deterministic)
9. **Deterministic Functions**: Same input → same output (cacheable, testable)
