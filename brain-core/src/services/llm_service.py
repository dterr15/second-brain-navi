"""LLM abstraction service for auto-process feature.

Supports anthropic (default), google, and openai providers.
Provider is selected via SB_LLM_PROVIDER env variable.
"""
from src.settings import settings


class LLMConfigError(Exception):
    """Raised when the LLM provider is misconfigured (missing API key, unknown provider)."""


class LLMCallError(Exception):
    """Raised when the LLM API call fails."""


async def call_llm(prompt: str) -> str:
    """Call the configured LLM and return the raw text response.

    Args:
        prompt: The full prompt string to send.

    Returns:
        The raw text response from the LLM.

    Raises:
        LLMConfigError: If provider is unknown or API key is missing.
        LLMCallError: If the API call fails.
    """
    provider = settings.llm_provider.lower()
    api_key = settings.llm_api_key
    model = settings.llm_model

    if not api_key:
        raise LLMConfigError(
            f"SB_LLM_API_KEY is not set. Configure it to use auto-process with provider '{provider}'."
        )

    if provider == "anthropic":
        return await _call_anthropic(prompt, api_key, model)
    elif provider == "google":
        return await _call_google(prompt, api_key, model)
    elif provider == "openai":
        return await _call_openai(prompt, api_key, model)
    else:
        raise LLMConfigError(
            f"Unknown LLM provider '{provider}'. Supported values: anthropic, google, openai."
        )


async def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise LLMConfigError(
            "anthropic SDK is not installed. Add 'anthropic>=0.25.0' to dependencies."
        )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        raise LLMCallError(f"Anthropic API error: {e}") from e


async def _call_google(prompt: str, api_key: str, model: str) -> str:
    try:
        import google.generativeai as genai
    except ImportError:
        raise LLMConfigError(
            "google-generativeai SDK is not installed. Add 'google-generativeai>=0.5.0' to dependencies."
        )

    try:
        genai.configure(api_key=api_key)
        genai_model = genai.GenerativeModel(model)
        response = genai_model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise LLMCallError(f"Google Generative AI error: {e}") from e


async def _call_openai(prompt: str, api_key: str, model: str) -> str:
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise LLMConfigError(
            "openai SDK is not installed. Add 'openai>=1.30.0' to dependencies."
        )

    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise LLMCallError(f"OpenAI API error: {e}") from e
