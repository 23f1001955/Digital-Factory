import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


def generate_text(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    base_url = "https://opencode.ai/zen/v1"

    client = OpenAI(api_key=api_key, base_url=base_url)
    model = "mimo-v2.5-free"

    logger.info(f"Calling LLM {model} via {base_url}...")
    response = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}], max_tokens=16384
    )
    return response.choices[0].message.content.strip()
