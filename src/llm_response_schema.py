from pydantic import BaseModel, ConfigDict, Field, field_validator

MISSING_TOKEN = "[MISSING_TEXT]"


class ReconstructionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reconstructed_excerpt: str = Field(min_length=1)

    @field_validator("reconstructed_excerpt")
    @classmethod
    def validate_reconstructed_excerpt(cls, value: str) -> str:
        cleaned = " ".join(value.split())

        if not cleaned:
            raise ValueError("reconstructed_excerpt cannot be empty")

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
