"""Re-export shim — implementation has moved to app.services.model_discovery."""

from app.services.model_discovery import get_ollama_models

__all__ = ["get_ollama_models"]
