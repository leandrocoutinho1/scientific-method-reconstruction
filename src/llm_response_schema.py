import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

MISSING_TOKEN = "[MISSING_TEXT]"
MIN_RECONSTRUCTION_WORDS = 8
PLACEHOLDER_RESPONSES = {
    "...",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "not available",
    "not enough context",
    "insufficient context",
    "cannot determine",
    "unable to determine",
}


class ReconstructionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reconstructed_excerpt: str = Field(min_length=1)

    @field_validator("reconstructed_excerpt")
    @classmethod
    def validate_reconstructed_excerpt(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        normalized = cleaned.strip().lower().rstrip(".")

        if not cleaned:
            raise ValueError("reconstructed_excerpt cannot be empty")

        if normalized in PLACEHOLDER_RESPONSES:
            raise ValueError("reconstructed_excerpt cannot be a placeholder response")

        word_count = len(re.findall(r"\b\w+\b", cleaned, flags=re.UNICODE))
        if word_count < MIN_RECONSTRUCTION_WORDS:
            raise ValueError(
                f"reconstructed_excerpt must contain at least {MIN_RECONSTRUCTION_WORDS} words"
            )

        if MISSING_TOKEN in cleaned:
            raise ValueError("reconstructed_excerpt cannot contain the missing text marker")

        if cleaned.startswith("{") or cleaned.startswith("["):
            raise ValueError("reconstructed_excerpt must be plain text, not nested JSON")

        return cleaned


def validate_reconstruction_response(data: dict) -> ReconstructionResponse:
    return ReconstructionResponse.model_validate(data)


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semantic_accuracy: int = Field(ge=1, le=5)
    methodological_fit: int = Field(ge=1, le=5)
    context_coherence: int = Field(ge=1, le=5)
    hallucination_risk: int = Field(ge=1, le=5)
    overall_score: int = Field(ge=1, le=5)
    verdict: str = Field(min_length=1)

    @field_validator("verdict")
    @classmethod
    def validate_verdict(cls, value: str) -> str:
        cleaned = " ".join(value.split())

        if not cleaned:
            raise ValueError("verdict cannot be empty")

        return cleaned


def validate_evaluation_response(data: dict) -> EvaluationResponse:
    return EvaluationResponse.model_validate(data)
