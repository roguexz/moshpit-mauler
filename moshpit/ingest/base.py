from abc import ABC, abstractmethod
from typing import List, Optional
import requests
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from moshpit.config import settings
from moshpit.exceptions import MoshpitException
from moshpit.ingest.normalizer import extract_json_block
from moshpit.ingest.sanitation import clean_artist_name


class ArtistSchema(BaseModel):
    """Schema to enforce the structure of extracted artist lists."""

    artists: List[str] = Field(..., min_length=1)


class BaseIngester(ABC):
    """
    Base class for ingestion pipelines that parse unstructured documents
    and extract a validated list of artist names.
    """

    def __init__(self, config=settings):
        self.config = config

    @abstractmethod
    def extract_artists(self, input_path: str) -> List[str]:
        """Extracts artist names from the given source path."""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def query_ollama(self, prompt: str, image_b64: Optional[str] = None) -> str:
        """
        Sends a query request to the local Ollama API.
        Uses tenacity for exponential backoff retries on request failure.
        """
        url = f"{self.config.ollama_base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.config.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        if image_b64:
            payload["images"] = [image_b64]

        try:
            response = requests.post(
                url, json=payload, timeout=self.config.ollama_timeout
            )
            response.raise_for_status()
            response_json = response.json()
            llm_response = response_json.get("response", "")
            if not llm_response:
                raise MoshpitException("Ollama returned an empty response string.")
            return llm_response
        except requests.RequestException as e:
            raise MoshpitException(f"Failed to query Ollama API: {e}")

    def parse_and_validate_artists(self, raw_llm_output: str) -> List[str]:
        """
        Extracts, cleans, and validates the artist list from the raw LLM output.
        """
        # 1. Extract the JSON block
        json_str = extract_json_block(raw_llm_output)

        # 2. Parse using Pydantic
        try:
            validated = ArtistSchema.model_validate_json(json_str)
        except Exception as e:
            raise MoshpitException(
                f"Failed to validate LLM response against ArtistSchema: {e}"
            )

        # 3. Sanitize each artist name and drop empty results
        sanitized_artists = []
        for artist in validated.artists:
            cleaned = clean_artist_name(artist)
            if cleaned:
                sanitized_artists.append(cleaned)

        if not sanitized_artists:
            raise MoshpitException(
                "Sanitation pipeline resolved zero valid artists from LLM response."
            )

        return sanitized_artists
