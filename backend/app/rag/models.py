"""LLM provider wrappers: Groq primary, local fallback."""
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("rag.models")


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate a completion.

        Returns dict with: text, model, tokens_used, latency_ms
        """
        pass

    @abstractmethod
    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        """Generate a streaming completion. Yields text chunks."""
        pass


class GroqProvider(LLMProvider):
    """Groq API provider (primary)."""

    def __init__(self):
        try:
            from groq import Groq

            settings = get_settings()  # <-- FIX: settings lo pehle
            self.client = Groq(api_key=settings.groq_api_key)  # <-- FIX: os.environ ki jagah settings.groq_api_key
            self.model = settings.llm_model
            logger.info(f"Groq provider initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq: {e}")
            raise

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        start = time.time()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)

        latency = (time.time() - start) * 1000
        text = response.choices[0].message.content or ""

        return {
            "text": text,
            "model": self.model,
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "latency_ms": latency,
        }

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class LocalProvider(LLMProvider):
    """Local HuggingFace transformers provider (fallback)."""

    def __init__(self):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline  # <-- FIX: pipeline import add kiya

            settings = get_settings()
            logger.info(f"Loading local model: {settings.local_llm_model}")

            self.tokenizer = AutoTokenizer.from_pretrained(settings.local_llm_model)
            self.model = AutoModelForCausalLM.from_pretrained(
                settings.local_llm_model,
                device_map="auto",
                torch_dtype="auto",
            )
            self.pipe = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=True,
            )
            self.model_name = settings.local_llm_model
            logger.info("Local provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize local model: {e}")
            raise

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        start = time.time()

        # Format prompt for instruction-following models
        prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"

        result = self.pipe(prompt, max_new_tokens=max_tokens, temperature=temperature)
        text = result[0]["generated_text"].split("<|assistant|>")[-1].strip()

        latency = (time.time() - start) * 1000

        return {
            "text": text,
            "model": self.model_name,
            "tokens_used": len(self.tokenizer.encode(text)),
            "latency_ms": latency,
        }

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        # Local models don't stream efficiently; yield full response
        result = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        yield result["text"]


# Provider factory
_llm_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """Get LLM provider with fallback logic."""
    global _llm_provider
    if _llm_provider is None:
        settings = get_settings()

        # Try Groq first if configured
        if settings.llm_provider == "groq" and settings.groq_api_key:
            try:
                _llm_provider = GroqProvider()
                logger.info("Using Groq as primary LLM provider")
                return _llm_provider
            except Exception as e:
                logger.warning(f"Groq unavailable, falling back to local: {e}")

        # Fallback to local
        try:
            _llm_provider = LocalProvider()
            logger.info("Using local HuggingFace model as fallback")
        except Exception as e:
            logger.error(f"No LLM provider available: {e}")
            raise RuntimeError("No LLM provider available. Check GROQ_API_KEY or local model setup.")

    return _llm_provider