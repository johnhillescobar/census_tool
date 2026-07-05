import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.benchmark_contract import GeographyLevel

_FIPS_PATTERN = re.compile(r"^\d{2}$")


class DetectedGeoContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geo_level: GeographyLevel | None = None
    state_fips: list[str] = Field(default_factory=list)
    mapped_levels: list[GeographyLevel] = Field(default_factory=list)

    @field_validator("state_fips")
    @classmethod
    def validate_fips(cls, v: list[str]) -> list[str]:
        for fips in v:
            if not _FIPS_PATTERN.fullmatch(fips):
                raise ValueError(f"Invalid state FIPS: {fips}")
        return v
