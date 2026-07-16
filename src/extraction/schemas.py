from pydantic import BaseModel, ConfigDict, Field


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_chunk_ids: list[str] = Field(min_length=1)


class FoodMasterExtraction(EvidenceRecord):
    category: str | None
    type: str | None
    ethnic_group: str | None


class RawMaterialExtraction(EvidenceRecord):
    raw_material: str
    amount: str | None
    preparation_method: str | None


class GeographyExtraction(EvidenceRecord):
    state: str | None
    district: str | None
    ethnic_group: str | None
    village: str | None


class NutritionExtraction(EvidenceRecord):
    category: str
    parameter: str
    value: str
    unit: str | None


class MicrobiomeExtraction(EvidenceRecord):
    taxonomy_level: str | None
    taxonomy_name: str


class PredominantMicrobeExtraction(EvidenceRecord):
    microbe: str
    count: str | None
