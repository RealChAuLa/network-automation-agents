"""
Gemini LLM Implementation

LLM implementation using Google's Gemini API via LangChain.
"""

import json
import time
import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.llm.base import BaseLLM, LLMResponse
from src.agents.config import config

logger = logging.getLogger(__name__)


class GeminiLLM(BaseLLM):
    """
    Gemini LLM implementation using LangChain.

    Example:
        llm = GeminiLLM(api_key="your-key", model="gemini-1.5-flash")
        response = await llm.generate("What is 2+2?")
        print(response.content)
    """

    def __init__(
            self,
            api_key: str,
            model: str = "gemini-1.5-flash",
            temperature: float = 0.1,
            max_tokens: int = 4096,
    ):
        """
        Initialize Gemini LLM.

        Args:
            api_key: Google API key
            model: Gemini model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
        """
        super().__init__(model, temperature, max_tokens)

        self.api_key = api_key
        self._client = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        logger.info(f"Initialized Gemini LLM with model: {model}")

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "gemini"

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Generate a response from Gemini.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt

        Returns:
            LLMResponse with the generated content
        """
        start_time = time.time()

        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            # Generate response
            response = await self._client.ainvoke(messages)

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract token usage if available
            usage_metadata = getattr(response, 'usage_metadata', None)
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None

            if usage_metadata:
                prompt_tokens = getattr(usage_metadata, 'input_tokens', None)
                completion_tokens = getattr(usage_metadata, 'output_tokens', None)
                total_tokens = getattr(usage_metadata, 'total_tokens', None)

            return LLMResponse(
                content=response.content,
                model=self.model,
                provider=self.provider_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise

    async def generate_structured(
            self,
            prompt: str,
            output_schema: dict,
            system_prompt: Optional[str] = None,
    ) -> dict:
        """
        Generate a structured response matching a schema.

        Args:
            prompt: The user prompt
            output_schema: JSON schema for expected output
            system_prompt: Optional system prompt

        Returns:
            Dictionary matching the output schema
        """
        # Build a prompt that encourages JSON output
        schema_str = json.dumps(output_schema, indent=2)

        structured_prompt = f"""{prompt}

Please respond with a valid JSON object that matches this schema:
```json
{schema_str}
Respond ONLY with the JSON object, no additional text or markdown formatting."""
        # Add JSON instruction to system prompt
        full_system_prompt = system_prompt or ""
        full_system_prompt += "\nYou are a helpful assistant that responds only in valid JSON format."

        response = await self.generate(structured_prompt, full_system_prompt)

        # Parse JSON from response
        try:
            # Try to extract JSON from the response
            content = response.content.strip()

            # Remove Markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            return json.loads(content.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            logger.debug(f"Raw response: {response.content}")

            # Return a default error structure
            return {
                "error": "Failed to parse JSON response",
                "raw_content": response.content,
            }

    def is_available(self) -> bool:
        """Check if Gemini is available."""
        return bool(self.api_key)