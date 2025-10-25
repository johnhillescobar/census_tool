import os
import sys
import logging
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.llm.config import LLM_CONFIG

# Handle both relative and absolute imports
from src.state.types import ResolvedGeography

load_dotenv()

logger = logging.getLogger(__name__)


class GeographyResolution(BaseModel):
    "Structured output for geography resolution"

    place_name: str = Field(..., description="The standardized place name")
    state: Optional[str] = Field(
        ..., description="State name or abbreviation if specified"
    )
    state_fips: Optional[str] = Field(..., description="State FIPS code if resolvable")
    place_fips: Optional[str] = Field(..., description="Place FIPS code if resolvable")
    confidence: float = Field(..., description="Confidence score between 0-1")
    resolution_method: str = Field(..., description="Method used to resolve geography")
    notes: Optional[str] = Field(
        ..., description="Additional notes about the resolution"
    )


class LLMGeographyResolver:
    """Intelligent geography resolver using LangChain and structured output parsing"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=LLM_CONFIG["model"], temperature=LLM_CONFIG["temperature_text"]
        )

        # Create the parser FIRST
        self.parser = PydanticOutputParser(pydantic_object=GeographyResolution)

        # Create the prompt template
        self.prompt_template = PromptTemplate(
            template="""
            You are a geography expert specializing in US Census geography resolution. Your task is to intelligently resolve location names to their proper Census geography codes.

            User Input: "{location_input}"

            Your task:
            1. Identify the most likely place name the user is referring to
            2. Determine the appropriate state if not specified
            3. Provide the most accurate Census FIPS codes possible

            Common abbreviations and their expansions:
            - NYC → New York City, New York (state FIPS: 36, place FIPS: 51000)
            - LA → Los Angeles, California (state FIPS: 06, place FIPS: 44000)  
            - SF → San Francisco, California (state FIPS: 06, place FIPS: 67000)
            - DC → Washington, District of Columbia (state FIPS: 11, place FIPS: 50000)
            - Chicago → Chicago, Illinois (state FIPS: 17, place FIPS: 14000)
            - Miami → Miami, Florida (state FIPS: 12, place FIPS: 45000)
            - Houston → Houston, Texas (state FIPS: 48, place FIPS: 35000)
            - Phoenix → Phoenix, Arizona (state FIPS: 04, place FIPS: 55000)
            - Philadelphia → Philadelphia, Pennsylvania (state FIPS: 42, place FIPS: 60000)
            - San Antonio → San Antonio, Texas (state FIPS: 48, place FIPS: 65000)
            - San Diego → San Diego, California (state FIPS: 06, place FIPS: 66000)
            - Dallas → Dallas, Texas (state FIPS: 48, place FIPS: 19000)
            - San Jose → San Jose, California (state FIPS: 06, place FIPS: 68000)
            - Austin → Austin, Texas (state FIPS: 48, place FIPS: 05000)
            - Jacksonville → Jacksonville, Florida (state FIPS: 12, place FIPS: 35000)

            Important rules:
            - If the input is ambiguous (like "Springfield"), provide the most common/likely interpretation
            - Always include state context when resolving cities
            - Use your knowledge of major US cities and their common abbreviations
            - If you're not confident about FIPS codes, leave them as null but provide the best place name and state
            - Confidence should reflect how certain you are about the resolution

            {format_instructions}
            """,
            input_variables=["location_input"],
            partial_variables={
                "format_instructions": self.parser.get_format_instructions()
            },
        )

        # Create the chain (fixed syntax)
        self.chain = self.prompt_template | self.llm | self.parser

    def resolve_location(self, location_input: str) -> ResolvedGeography:
        """Resolve a location using LLM with structured output"""

        try:
            logger.info(f"Resolving geography for: {location_input}")

            # Get structured resolution from LLM
            resolution = self.chain.invoke({"location_input": location_input})

            logger.info(f"Geography resolution result: {resolution}")

            # Convert to ResolvedGeography format

            return self._convert_to_resolved_geography(resolution, location_input)

        except Exception as e:
            logger.error(f"LLM geography resolution failed: {e}")
            # Return error result
            return ResolvedGeography(
                level="error",
                filters={},
                display_name=location_input,
                fips_codes={},
                confidence=0.0,
                note=f"LLM resolution failed: {str(e)}",
                geocoding_metadata={},
            )

    def _convert_to_resolved_geography(
        self, resolution: GeographyResolution, original_input: str
    ) -> ResolvedGeography:
        """Convert structured resolution to ResolvedGeography format"""

        filters = {}
        fips_codes = {}

        if resolution.state_fips and resolution.place_fips:
            # We have both state and place - this is a city
            filters = {
                "for": f"place:{resolution.place_fips}",
                "in": f"state:{resolution.state_fips}",
            }
            fips_codes = {
                "place": resolution.place_fips,
                "state": resolution.state_fips,
            }
            level = "place"
        elif resolution.state_fips:
            # We have only state - this is a state
            filters = {"for": f"state:{resolution.state_fips}"}
            fips_codes = {"state": resolution.state_fips}
            level = "state"
        else:
            # We have neither state nor place - this is a county
            # No FIPS codes available - return error
            return ResolvedGeography(
                level="error",
                filters={},
                display_name=original_input,
                fips_codes={},
                confidence=resolution.confidence,
                note=f"Could not resolve FIPS codes for '{resolution.place_name}'",
                geocoding_metadata={
                    "llm_resolution": resolution.dict(),
                    "method": "llm_no_fips",
                },
            )

        # Build display name
        display_name = resolution.place_name
        if resolution.state and resolution.state not in display_name:
            display_name = f"{display_name}, {resolution.state}"

        return ResolvedGeography(
            level=level,
            filters=filters,
            display_name=display_name,
            fips_codes=fips_codes,
            confidence=resolution.confidence,
            note=f"Resolved via LLM: {resolution.resolution_method}",
            geocoding_metadata={
                "llm_resolution": resolution.dict(),
                "method": "llm_structured",
            },
        )


# Convenience function for backward compatibility
def resolve_geography_hint(location_input: str) -> ResolvedGeography:
    """Resolve geography using LLM - convenience function"""

    resolver = LLMGeographyResolver()
    return resolver.resolve_location(location_input)


if __name__ == "__main__":
    # Test the resolver
    resolver = LLMGeographyResolver()

    test_locations = [
        "NYC",
        "New York City",
        "Chicago",
        "LA",
        "San Francisco",
        "Springfield",  # Ambiguous case
        "Miami, FL",
        "Houston, Texas",
    ]

    for location in test_locations:
        print(f"\n{'=' * 50}")
        print(f"Testing: '{location}'")
        result = resolver.resolve_location(location)
        print(f"Result: {result}")
