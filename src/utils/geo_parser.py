import os
import sys
import logging
import spacy
import pandas as pd
from typing import List, Optional, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state.types import GeographyRequest, GeographyEntity

logger = logging.getLogger(__name__)


class GeographyParser:
    """Parser for geography entities"""

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.cities_df = pd.read_csv("src/locations/locations.csv")
        self.counties_df = pd.read_csv("src/locations/counties_processed.csv")
        self.states_df = pd.read_csv("src/locations/states_abbrev.csv")
        self.states = set(self.cities_df["State Name"].str.lower().unique())
        self.cities = set(self.cities_df["Name"].str.lower().unique())
        self.counties = set(self.counties_df["counties"].str.lower().unique())
        self.state_abbrev_map = self._build_state_abbrev_map()

    def _build_state_abbrev_map(self) -> Dict[str, str]:
        """Build complete state abbreviation mapping from CSV"""
        abbrev_map = {}
        for _, row in self.states_df.iterrows():
            abbrev = row["abbreviation"].lower()
            full_name = row["full_name"]
            abbrev_map[abbrev] = full_name
        return abbrev_map

    def _get_geo_type(self, text: str) -> str:
        text_lower = text.lower()

        # County detection (highest priority)
        county_keywords = ["county", "parish", "borough"]
        if any(keyword in text_lower for keyword in county_keywords):
            return "county"

        # State detection (exact match)
        if text_lower in self.states:
            return "state"

        # City detection (fuzzy match)
        for city in self.cities:
            if text_lower in city or city in text_lower:
                return "city"

        return "unknown"

    def extract_geography_entities(self, text: str) -> List[GeographyEntity]:
        """Extract geography entities from the text"""
        entities = []
        doc = self.nlp(text)

        print(f"Debug: Processing '{text}'")
        print(f"Debug: Found entities: {[(ent.text, ent.label_) for ent in doc.ents]}")

        # Check for nationwide indicators first
        nationwide_keywords = [
            "nationwide",
            "national",
            "usa",
            "united states",
            "country",
        ]
        text_lower = text.lower()
        for keyword in nationwide_keywords:
            if keyword in text_lower:
                entities.append(
                    GeographyEntity(
                        name="United States",
                        type="nation",
                        confidence=0.9,
                        context={},
                        start_pos=text_lower.find(keyword),
                        end_pos=text_lower.find(keyword) + len(keyword),
                    )
                )
                break

        # Process spaCy entities
        for ent in doc.ents:
            if ent.label_ in ["GPE", "LOC", "FAC"]:
                geo_type = self._get_geo_type(ent.text)

                if geo_type != "unknown":
                    entity = GeographyEntity(
                        name=ent.text,
                        type=geo_type,
                        confidence=0.9,
                        context={},
                        start_pos=ent.start_char,
                        end_pos=ent.end_char,
                    )
                    entities.append(entity)

        return entities

    def extract_state_context(self, text: str) -> Optional[str]:
        text_lower = text.lower()

        # Skip generic references
        generic_keywords = [
            "across states",
            "all states",
            "every state",
            "nationwide",
            "national",
        ]
        if any(keyword in text_lower for keyword in generic_keywords):
            return None

        # Special cases for common abbreviations (HIGHEST PRIORITY)
        if "nyc" in text_lower:
            return "New York"

        # Look for explicit state mentions
        for state in self.states:
            if state in text_lower:
                return state.title()

        # Look for state abbreviations
        for abbrev, full_name in self.state_abbrev_map.items():
            if f" {abbrev} " in text_lower or text_lower.startswith(f"{abbrev} "):
                return full_name

        # City-state association (only if no state found above)
        for _, row in self.cities_df.iterrows():
            city_name = row["Name"].lower()
            state_name = row["State Name"]
            # Only match if it's clearly a city name, not a state name
            if city_name in text_lower and city_name not in self.states:
                return state_name

        return None

    def extract_geography_level(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        if "by county" in text_lower:
            return "county"
        elif "by tract" in text_lower or "census tract" in text_lower:
            return "tract"
        elif "by state" in text_lower:
            return "state"
        return None

    def parse_query(self, text: str) -> GeographyRequest:
        """Parse the query and return a GeographyRequest object"""

        entities = self.extract_geography_entities(text)
        state_context = self.extract_state_context(text)
        requested_level = self.extract_geography_level(text)

        return GeographyRequest(
            raw_text=text,
            entities=entities,
            requested_level=requested_level,
            state_context=state_context,
        )


if __name__ == "__main__":
    questions = [
        "What's the population of Chicago?",
        "Can you give me the population of IL Cook County by census tract",
        "What's the population of New York City?",
        "Population of California in 2023",
        "Population by county in Texas",
        "Median income in NYC",
        "Hispanic median income trends from 2015 to 2020",
        "Income comparison across states",
        "Population of Los Angeles County",
        "Median income by county in New York",
        "Nationwide population trends",
        "Population changes in NYC from 2015 to 2020",
        "Income trends over time in California",
        "What's the median income of Washington DC?",
        "What's the median income of Washington state?",
    ]
    for question in questions:
        parser = GeographyParser()
        print("--------------------------------")
        request = parser.parse_query(question)
        print(question, request)
