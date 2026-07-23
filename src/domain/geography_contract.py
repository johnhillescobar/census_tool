from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

GeographySource = Literal[
    "explicit",
    "profile_default",
    "chroma",
]

GeographyLevel = Literal[
    "nation",
    "state",
    "region",
    "division",
    "county",
    "county_subdivision",
    "subminor_civil_division",
    "place",
    "place_remainder",
    "consolidated_city",
    "tract",
    "block_group",
    "tribal_census_tract",
    "tribal_block_group",
    "tribal_subdivision_remainder",
    "alaska_native_regional_corporation",
    "american_indian_area_alaska_native_area_hawaiian_home_land",
    "american_indian_area_alaska_native_area",
    "american_indian_area_off_reservation_trust_land_hawaiian_home_land",
    "cbsa",
    "metropolitan_division",
    "combined_statistical_area",
    "necta",
    "principal_city",
    "urban_area",
    "zcta",
    "puma",
    "congressional_district",
    "state_legislative_district_lower",
    "state_legislative_district_upper",
    "school_district_elementary",
    "school_district_secondary",
    "school_district_unified",
]

CensusGeographyToken = Literal[
    "alaska native regional corporation",
    "american indian area (off-reservation trust land only)/hawaiian home land",
    "american indian area (off-reservation trust land only)/hawaiian home land (or part)",
    "american indian area/alaska native area (reservation or statistical entity only)",
    "american indian area/alaska native area (reservation or statistical entity only) (or part)",
    "american indian area/alaska native area/hawaiian home land",
    "american indian area/alaska native area/hawaiian home land (or part)",
    "block group",
    "combined statistical area",
    "combined statistical area (or part)",
    "congressional district",
    "consolidated city",
    "county",
    "county (or part)",
    "county subdivision",
    "division",
    "metropolitan division",
    "metropolitan division (or part)",
    "metropolitan statistical area/micropolitan statistical area",
    "metropolitan statistical area/micropolitan statistical area (or part)",
    "new england city and town area",
    "place",
    "place (or part)",
    "place/remainder (or part)",
    "principal city (or part)",
    "public use microdata area",
    "region",
    "school district (elementary)",
    "school district (secondary)",
    "school district (unified)",
    "state",
    "state (or part)",
    "state legislative district (lower chamber)",
    "state legislative district (upper chamber)",
    "subminor civil division",
    "tract",
    "tribal block group",
    "tribal block group (or part)",
    "tribal census tract",
    "tribal census tract (or part)",
    "tribal subdivision/remainder",
    "urban area",
    "us",
    "zip code tabulation area",
]


class GeographyIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: GeographyLevel
    geo_for: dict[str, str] = Field(default_factory=dict)
    geo_in: dict[str, str] = Field(default_factory=dict)
    display_name: str
    source: GeographySource
    requested_text: str | None = None
    census_token: CensusGeographyToken | None = None


class ClarificationOption(BaseModel):
    option_id: str
    label: str


class ClarificationPrompt(BaseModel):
    template_id: str
    reason_code: str
    question_text: str
    options: list[ClarificationOption]
    expected_response_shape: Literal["single_select"] = "single_select"


class GeographyResolved(BaseModel):
    status: Literal["resolved"] = "resolved"
    geography: GeographyIntent


class GeographyClarificationRequired(BaseModel):
    status: Literal["clarification_required"] = "clarification_required"
    reason_code: str
    clarification_prompt: ClarificationPrompt


GeographyResolution = Annotated[
    GeographyResolved | GeographyClarificationRequired,
    Field(discriminator="status"),
]
