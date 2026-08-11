"""LLM provider abstraction — OpenAI, Groq, and Local support."""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Optional

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("rag.models")


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------
class BaseLLMProvider(ABC):
    """Abstract LLM provider with generate + stream support."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Generate a completion. Returns dict with text, model, tokens_used, latency_ms."""
        ...

    @abstractmethod
    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        """Yield tokens as they are generated."""
        ...


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------
class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI GPT-4o / GPT-4o-mini provider."""

    def __init__(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("OpenAI package not installed. Run: pip install openai")

        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when LLM_PROVIDER=openai. "
                "Add it to backend/.env"
            )

        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_llm_model
        logger.info(f"OpenAI LLM client ready. Model: {self.model}")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
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

        try:
            response = self.client.chat.completions.create(**kwargs)
            latency = int((time.time() - start) * 1000)
            text = response.choices[0].message.content or ""
            usage = response.usage

            return {
                "text": text,
                "model": self.model,
                "tokens_used": usage.total_tokens if usage else 0,
                "latency_ms": latency,
            }
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
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
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}")
            raise


# ---------------------------------------------------------------------------
# Groq Provider
# ---------------------------------------------------------------------------
class GroqLLMProvider(BaseLLMProvider):
    """Groq API provider (Llama, Mixtral, etc.)."""

    def __init__(self):
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Groq package not installed. Run: pip install groq")

        settings = get_settings()
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is required when LLM_PROVIDER=groq. "
                "Add it to backend/.env"
            )

        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        logger.info(f"Groq LLM client ready. Model: {self.model}")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
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

        try:
            response = self.client.chat.completions.create(**kwargs)
            latency = int((time.time() - start) * 1000)
            text = response.choices[0].message.content or ""
            usage = response.usage

            return {
                "text": text,
                "model": self.model,
                "tokens_used": usage.total_tokens if usage else 0,
                "latency_ms": latency,
            }
        except Exception as e:
            logger.error(f"Groq generation failed: {e}")
            raise

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
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
        except Exception as e:
            logger.error(f"Groq streaming failed: {e}")
            raise


# ---------------------------------------------------------------------------
# Local Provider (HuggingFace Transformers)
# ---------------------------------------------------------------------------
class LocalLLMProvider(BaseLLMProvider):
    """Local HuggingFace model provider (CPU/GPU)."""

    def __init__(self):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
        except ImportError:
            raise ImportError(
                "transformers not installed. Run: pip install transformers accelerate"
            )

        settings = get_settings()
        model_name = settings.local_llm_model
        logger.info(f"Loading local LLM: {model_name}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="auto",
        )
        self.pipeline = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
        )
        logger.info("Local LLM loaded successfully")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        start = time.time()
        prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"

        outputs = self.pipeline(
            prompt,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            return_full_text=False,
        )
        latency = int((time.time() - start) * 1000)
        text = outputs[0]["generated_text"].strip()

        # Rough token count
        tokens_used = len(self.tokenizer.encode(prompt + text))

        return {
            "text": text,
            "model": self.model.config.name_or_path,
            "tokens_used": tokens_used,
            "latency_ms": latency,
        }

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        # Local models typically don't stream easily with transformers pipeline
        # Fallback: generate full then yield word-by-word
        result = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        words = result["text"].split(" ")
        for word in words:
            yield word + " "


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_llm_instance: Optional[BaseLLMProvider] = None


def get_llm_provider() -> BaseLLMProvider:
    global _llm_instance
    if _llm_instance is None:
        settings = get_settings()
        provider = settings.llm_provider

        if provider == "openai":
            _llm_instance = OpenAILLMProvider()
        elif provider == "groq":
            _llm_instance = GroqLLMProvider()
        elif provider == "local":
            _llm_instance = LocalLLMProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    return _llm_instance