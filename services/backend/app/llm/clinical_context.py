from __future__ import annotations

from pydantic import BaseModel, Field


class QuestionnaireAnswerPayload(BaseModel):
    module_id: str
    question_id: str
    answer: str


class QuestionnaireResponsePayload(BaseModel):
    responder: str = "patient"
    comment: str = ""
    answers: list[QuestionnaireAnswerPayload] = Field(default_factory=list)


class ClinicalContextPayload(BaseModel):
    patient_factors: list[str] = Field(default_factory=list)
    perioperative_context: list[str] = Field(default_factory=list)
    free_text: str = ""
    questionnaire: QuestionnaireResponsePayload | None = None

    def as_prompt_dict(self) -> dict[str, object]:
        return {
            "patient_factors": [item.strip() for item in self.patient_factors if item.strip()],
            "perioperative_context": [item.strip() for item in self.perioperative_context if item.strip()],
            "free_text": self.free_text.strip(),
            "questionnaire": self.questionnaire.model_dump() if self.questionnaire else None,
        }
