from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal
from enum import Enum


class GeographyLevel(str, Enum):
    """All Census geography levels from CENSUS_DISCUSSION.md lines 314-328"""

    STATE = "state"
    COUNTY = "county"
    PLACE = "place"
    TRACT = "tract"
    BLOCK_GROUP = "block group"
    CBSA = "metropolitan statistical area/micropolitan statistical area"
    METRO_DIVISION = "metropolitan division"
    CSA = "combined statistical area"
    NECTA = "new england city and town area"
    NECTA_DIVISION = "new england city and town area division"
    URBAN_AREA = "urban area"
    ZCTA = "zip code tabulation area"
    PUMA = "public use microdata area"
    COUNTY_SUBDIVISION = "county subdivision"
    CONGRESSIONAL_DISTRICT = "congressional district"


class AreaResolutionInput(BaseModel):
    """Resolve single area name to Census code"""

    name: str = Field(
        ..., description="Area name like 'California' or 'Los Angeles County'"
    )
    geography_type: GeographyLevel = Field(
        default=GeographyLevel.STATE,
        description="Geography or summary level to enumerate",
    )
    dataset: str = Field(
        default="acs/acs5",
        description="A census dataset is a collection of statistical information gathered from every individual or household in a specific region, used for demographic, social, and economic analysis",
    )
    year: int = Field(
        default=2023,
        description="Census year which is the year of the data you want to analyze",
    )
    parent: Optional[Dict[str, str]] = Field(
        default=None,
        description="Parent geography or summary level like {'state': '06'} for example if you want to enumerate all counties in California, you would need to know the state code for California which is 06",
    )


class GeographyEnumerationInput(BaseModel):
    """Enumerate all areas at a geography level"""

    level: GeographyLevel = Field(..., description="Geography level to enumerate")
    dataset: str = Field(
        default="acs/acs5",
        description="A census dataset is a collection of statistical information gathered from every individual or household in a specific region, used for demographic, social, and economic analysis",
    )
    year: int = Field(
        default=2023,
        description="Census year which is the year of the data you want to analyze",
    )
    parent: Optional[Dict[str, str]] = Field(
        default=None,
        description="Parent geography constraint like {'state': '06'} for example if you want to enumerate all counties in California, you would need to know the state code for California which is 06",
    )


class ListLevelsInput(BaseModel):
    """List available geography levels for a dataset"""

    dataset: str = Field(
        default="acs/acs5",
        description="A census dataset is a collection of statistical information gathered from every individual or household in a specific region, used for demographic, social, and economic analysis",
    )
    year: int = Field(
        default=2023,
        description="Census year which is the year of the data you want to analyze",
    )
