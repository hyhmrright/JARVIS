# Specification: Ollama Support Integration

## Overview
This track aims to integrate Ollama as a local LLM provider for the JARVIS platform. Users will be able to use models hosted on their local Ollama instance for conversations, RAG-based knowledge retrieval, and tool-augmented workflows.

## Functional Requirements
- **Model Discovery**: The backend should automatically fetch the list of available models from the local Ollama API (`/api/tags`) and make them available in the JARVIS model selection UI.
- **Chat Integration**: Use LangChain's `ChatOllama` for core LLM interactions.
- **Streaming Support**: Implement Server-Sent Events (SSE) for real-time response streaming from Ollama models.
- **RAG Integration**: Ensure Ollama models can be used as the inference engine for the RAG knowledge base.
- **Tool Calling**: Support tool/plugin invocation for Ollama models that support it (e.g., Llama 3.1+, Mistral).

## Non-Functional Requirements
- **Latency**: Minimize overhead between JARVIS backend and local Ollama instance.
- **Reliability**: Gracefully handle cases where the local Ollama service is not running.

## Acceptance Criteria
- [ ] Available Ollama models are visible in the model selection menu.
- [ ] Users can start a conversation using an Ollama model.
- [ ] Responses stream in real-time.
- [ ] Ollama models can correctly answer questions based on uploaded RAG documents.
- [ ] Ollama models can trigger available JARVIS tools (if supported by the model).

## Out of Scope
- Downloading/Pulling models from within the JARVIS UI.
- Remote Ollama server configuration (fixed to localhost for now).