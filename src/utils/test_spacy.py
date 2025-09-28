import spacy

# Load the pre-trained English model
nlp = spacy.load("en_core_web_sm")


def extract_locations(text):
    doc = nlp(text)
    locations = []
    for ent in doc.ents:
        # 'GPE' refers to Geo-Political Entity (countries, cities, states)
        # 'LOC' refers to Non-GPE locations (mountains, rivers, etc.)
        if ent.label_ in ["GPE", "LOC"]:
            locations.append(ent.text)
        # 'FAC' entities that look like geographical locations (counties, etc.)
        elif ent.label_ == "FAC" and any(
            keyword in ent.text.lower()
            for keyword in ["county", "parish", "borough", "city", "town", "village"]
        ):
            locations.append(ent.text)
    return locations

    # Example usage


sentence1 = "Paris is the capital of France, known for the Eiffel Tower."
sentence2 = "He traveled to the Rocky Mountains and then visited London."
sentence3 = "The meeting will be held in New York City."
sentence4 = "What's the population of Chicago?"
sentence5 = "What's the population of DuPage County IL?"
sentence6 = "What's the population of Cook County IL?"
sentence7 = "What's the population of Texas?"

print(f"Locations in sentence 1: {extract_locations(sentence1)}")
print(f"Locations in sentence 2: {extract_locations(sentence2)}")
print(f"Locations in sentence 3: {extract_locations(sentence3)}")
print(f"Locations in sentence 4: {extract_locations(sentence4)}")
print(f"Locations in sentence 5: {extract_locations(sentence5)}")
print(f"Locations in sentence 6: {extract_locations(sentence6)}")
print(f"Locations in sentence 7: {extract_locations(sentence7)}")
