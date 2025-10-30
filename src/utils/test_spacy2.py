import re
import spacy
from spacy.tokens import Span

STATE_ABBR_TO_FIPS = {
    "AL": "01",
    "AK": "02",
    "AZ": "04",
    "AR": "05",
    "CA": "06",
    "CO": "08",
    "CT": "09",
    "DE": "10",
    "DC": "11",
    "FL": "12",
    "GA": "13",
    "HI": "15",
    "ID": "16",
    "IL": "17",
    "IN": "18",
    "IA": "19",
    "KS": "20",
    "KY": "21",
    "LA": "22",
    "ME": "23",
    "MD": "24",
    "MA": "25",
    "MI": "26",
    "MN": "27",
    "MS": "28",
    "MO": "29",
    "MT": "30",
    "NE": "31",
    "NV": "32",
    "NH": "33",
    "NJ": "34",
    "NM": "35",
    "NY": "36",
    "NC": "37",
    "ND": "38",
    "OH": "39",
    "OK": "40",
    "OR": "41",
    "PA": "42",
    "RI": "44",
    "SC": "45",
    "SD": "46",
    "TN": "47",
    "TX": "48",
    "UT": "49",
    "VT": "50",
    "VA": "51",
    "WA": "53",
    "WV": "54",
    "WI": "55",
    "WY": "56",
}

STATE_NAME_TO_ABBR = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}


def normalize_cd_number(text: str) -> str:
    t = text.strip().lower().replace(" ", "").replace("-", "")
    if t in ("al", "atlarge", "atlargecd", "atlargecongressionaldistrict"):
        return "00"
    # remove ordinal suffixes
    t = re.sub(r"(st|nd|rd|th)$", "", t)
    if t.isdigit():
        return t.zfill(2)
    return ""


def extract_state_context(doc, start_i, end_i):
    # Look within a small window around the match for a state mention
    window = doc[max(0, start_i - 6) : min(len(doc), end_i + 6)]
    # Try abbr (uppercase tokens)
    for tok in window:
        if tok.text.isupper() and tok.text in STATE_ABBR_TO_FIPS:
            abbr = tok.text
            return abbr, STATE_ABBR_TO_FIPS[abbr]
    # Try full names (case-insensitive)
    wtext = window.text.lower()
    for name, abbr in STATE_NAME_TO_ABBR.items():
        if re.search(rf"\b{re.escape(name)}\b", wtext):
            return abbr, STATE_ABBR_TO_FIPS[abbr]
    return None, None


def make_nlp_with_cd():
    nlp = spacy.load("en_core_web_sm")
    ruler = nlp.add_pipe("entity_ruler", before="ner")

    patterns = [
        # IL-07, TX-32, WY-AL
        {
            "label": "CD",
            "pattern": [
                {"TEXT": {"REGEX": "^[A-Z]{2}$"}},
                {"TEXT": "-"},
                {"TEXT": {"REGEX": "^(AL|[0-9]{1,2})$"}},
            ],
        },
        # congressional district 7 / cd 7 / cd: 7
        {
            "label": "CD",
            "pattern": [
                {"LOWER": {"IN": ["congressional", "cd"]}},
                {"LOWER": "district", "OP": "?"},
                {"IS_PUNCT": True, "OP": "?"},
                {
                    "TEXT": {
                        "REGEX": "^(AL|al|at[- ]?large|[0-9]{1,2}|[0-9]{1,2}(st|nd|rd|th))$"
                    }
                },
            ],
        },
        # 7th congressional district
        {
            "label": "CD",
            "pattern": [
                {"TEXT": {"REGEX": "^[0-9]{1,2}(st|nd|rd|th)$"}},
                {"LOWER": "congressional"},
                {"LOWER": "district"},
            ],
        },
        # congressional district of IL
        {
            "label": "CD",
            "pattern": [
                {"LOWER": {"IN": ["congressional", "cd"]}},
                {"LOWER": "district"},
                {"LOWER": {"IN": ["of", "in"]}},
                {"TEXT": {"REGEX": "^[A-Za-z]{2}$"}},
            ],
        },
        # <state name> at-large congressional district
        {
            "label": "CD",
            "pattern": [
                {"IS_TITLE": True},
                {"LOWER": "at-large"},
                {"LOWER": "congressional"},
                {"LOWER": "district"},
            ],
        },
    ]
    ruler.add_patterns(patterns)

    # Span extensions to hold normalized info
    if not Span.has_extension("cd_state_abbr"):
        Span.set_extension("cd_state_abbr", default=None)
    if not Span.has_extension("cd_state_fips"):
        Span.set_extension("cd_state_fips", default=None)
    if not Span.has_extension("cd_code"):
        Span.set_extension("cd_code", default=None)

    @nlp.component("cd_postprocess")
    def cd_postprocess(doc):
        ents = list(doc.ents)
        new_ents = []
        for ent in ents:
            if ent.label_ != "CD":
                new_ents.append(ent)
                continue

            # Try to parse state + district code from the text and context
            text = ent.text
            cd_code = ""
            state_abbr = None
            state_fips = None

            # Case: AB-## or AB-AL
            m = re.match(r"^([A-Z]{2})-(AL|[0-9]{1,2})$", text)
            if m:
                state_abbr = m.group(1)
                state_fips = STATE_ABBR_TO_FIPS.get(state_abbr)
                cd_code = normalize_cd_number(m.group(2))
            else:
                # Look for a number/ordinal/AL in the span
                num = re.search(
                    r"(AL|al|at[- ]?large|[0-9]{1,2}(?:st|nd|rd|th)?|\b[0-9]{1,2}\b)",
                    text,
                    flags=re.I,
                )
                if num:
                    cd_code = normalize_cd_number(num.group(0))
                # Find state in local context
                state_abbr, state_fips = extract_state_context(doc, ent.start, ent.end)

            # If still missing, try span itself for state name
            if not state_abbr:
                t = text.lower()
                for name, abbr in STATE_NAME_TO_ABBR.items():
                    if re.search(rf"\b{re.escape(name)}\b", t):
                        state_abbr = abbr
                        state_fips = STATE_ABBR_TO_FIPS[abbr]
                        break

            # Attach normalized info
            ent._.cd_state_abbr = state_abbr
            ent._.cd_state_fips = state_fips
            ent._.cd_code = cd_code if cd_code else None

            new_ents.append(ent)
        doc.ents = tuple(new_ents)
        return doc

    nlp.add_pipe("cd_postprocess", last=True)
    return nlp


# Example
if __name__ == "__main__":
    nlp = make_nlp_with_cd()
    text = "Compare IL-07 to the 12th Congressional District of California and the Wyoming at-large congressional district. Also CD 3 in TX."
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "CD":
            print(ent.text, ent._.cd_state_abbr, ent._.cd_state_fips, ent._.cd_code)
            # Build Census filters when both state_fips and cd_code are present:
            if ent._.cd_state_fips and ent._.cd_code:
                filters = f"for=congressional%20district:{ent._.cd_code}&in=state:{ent._.cd_state_fips}"
                print("filters:", filters)
