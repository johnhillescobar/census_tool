
## Explaining the Census APIs

The following explanation can be expanded in this link:

https://www.census.gov/programs-surveys/acs/data/data-tables/table-ids-explained.html 


We find these different data categories in the census:

* Detail Tables (B or C): https://api.census.gov/data/2018/acs/acs5
* Detail Profiles (DP): https://api.census.gov/data/2018/acs/acs1/profile
* Comparison Tables (CP): https://api.census.gov/data/2018/acs/acs5/cprofile
* Selected Population Profiles (S0201): https://api.census.gov/data/2018/acs/acs1/spp
* Subject Tables (S): https://api.census.gov/data/2018/acs/acs5/subject

Census uses each categories to access different topics at different level of granularity. Some of them can achieve high granularity like acs/acs5, and others don't. Furthermore, not all categories have the same number of years of available data.

Let's use ACS5 dataset (acs/acs5) to illustrate how things are interconnected:

1. Groups have an overarching compendium of tables by name, description, variables location and universe.  In our example, the URL would look like this:

https://api.census.gov/data/2023/acs/acs5/groups.json

2. This is an excerpt of you will find there:

```json
{
  "groups": [
    {
      "name": "B18104",
      "description": "Sex by Age by Cognitive Difficulty",
      "variables": "http://api.census.gov/data/2023/acs/acs5/groups/B18104.json",
      "universe ": "Civilian noninstitutionalized population 5 years and over"
    },
    {
      "name": "B17015",
      "description": "Poverty Status in the Past 12 Months of Families by Family Type by Social Security Income by Supplemental Security Income (SSI) and Cash Public Assistance Income",
      "variables": "http://api.census.gov/data/2023/acs/acs5/groups/B17015.json",
      "universe ": "Families"
    },
    {
      "name": "B18105",
      "description": "Sex by Age by Ambulatory Difficulty",
      "variables": "http://api.census.gov/data/2023/acs/acs5/groups/B18105.json",
      "universe ": "Civilian noninstitutionalized population 5 years and over"
    }
}

```

3. Then within a variables placeholder URL, you can find the whole description by label, concpet, predicate type, group, universe, etc.  For instance, in "http://api.census.gov/data/2023/acs/acs5/groups/B18104.json" from our previous example, you will find variables like this:

```json
"B18104_028E": {
      "label": "Estimate!!Total:!!Female:!!65 to 74 years:",
      "concept": "Sex by Age by Cognitive Difficulty",
      "predicateType": "int",
      "group": "B18104",
      "limit": 0,
      "predicateOnly": true,
      "universe": "Civilian noninstitutionalized population 5 years and over"
    }
```
4. You will find the full list of variables here as well: https://api.census.gov/data/2023/acs/acs5/variables.json

5. This is how this would look like:

```json
{
  "variables": {
    "for": {
      "label": "Census API FIPS 'for' clause",
      "concept": "Census API Geography Specification",
      "predicateType": "fips-for",
      "group": "N/A",
      "limit": 0,
      "predicateOnly": true
    },
    "in": {
      "label": "Census API FIPS 'in' clause",
      "concept": "Census API Geography Specification",
      "predicateType": "fips-in",
      "group": "N/A",
      "limit": 0,
      "predicateOnly": true
    },

```


### This relationship can be replicated in the other categories. For example, in case you want to do the same for "subject":

1. Groups: https://api.census.gov/data/2023/acs/acs5/subject/groups.json
2. You will find:
```json
{
  "groups": [
    {
      "name": "S0103PR",
      "description": "Population 65 Years and Over in Puerto Rico",
      "variables": "http://api.census.gov/data/2023/acs/acs5/subject/groups/S0103PR.json"
    },
    {
      "name": "S1601",
      "description": "Language Spoken at Home",
      "variables": "http://api.census.gov/data/2023/acs/acs5/subject/groups/S1601.json"
    }
  }
```
3. The variables placeholder will be find here: https://api.census.gov/data/2023/acs/acs5/subject/groups/S0103PR.json

4. The full list will be here: https://api.census.gov/data/2023/acs/acs5/subject/variables.json

5. It will look like this:
```json

  "variables": {
    "for": {
      "label": "Census API FIPS 'for' clause",
      "concept": "Census API Geography Specification",
      "predicateType": "fips-for",
      "group": "N/A",
      "limit": 0,
      "predicateOnly": true
    },
    "in": {
      "label": "Census API FIPS 'in' clause",
      "concept": "Census API Geography Specification",
      "predicateType": "fips-in",
      "group": "N/A",
      "limit": 0,
      "predicateOnly": true
    },

  }
```

## Explaining the Census APIs Build

Census APIs are pretty flexible or dynamic. These are some basic examples:

|| Geography Hierarchy | Geography Level | Example URL |
|---------------------|-----------------|-------------|
| us                  | 010             | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=us:*&key=YOUR_KEY_GOES_HERE`  |
|                     |                 | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=us:1&key=YOUR_KEY_GOES_HERE`  |
| region              | 020             | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=region:*&key=YOUR_KEY_GOES_HERE`  |
|                     |                 | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=region:3&key=YOUR_KEY_GOES_HERE`  |
| division            | 030             | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=division:*&key=YOUR_KEY_GOES_HERE`  |
|                     |                 | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=division:5&key=YOUR_KEY_GOES_HERE`  |
| state               | 040             | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=state:*&key=YOUR_KEY_GOES_HERE`  |
|                     |                 | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=state:06&key=YOUR_KEY_GOES_HERE`  |
| state > county      | 050             | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=county:*&key=YOUR_KEY_GOES_HERE`  |
|                     |                 | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=county:*&in=state:*&key=YOUR_KEY_GOES_HERE`  |
|                     |                 | `https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=county:037&in=state:06&key=YOUR_KEY_GOES_HERE`  |


You will find the full description for geography hierarchy and summary level / geography level here: https://api.census.gov/data/2023/acs/acs5/examples.html

Caveat: Notice that examples are delivered by year. Data is pretty stable year to year, but it can change, though.

You also can use the group function to bring all data:
https://api.census.gov/data/2019/acs/acs1/subject?get=group(S0101)&for=state:*


## How is this translated into our application

The application must be able to create those APIs call dynamically (preferably hybrid approach) tha help properly account for geography hierarchy and summary level / geography level

Also, the vector database can use multiple collections to use groups as the first step to get the meaning of the table and then, go to a much more granular analysis in the collection storing the information per variable. This can happen using filters when querying the vector database.

These are NOT commands but examples to help you think through.


# Complex APIs

## Question:

When I need to create a complex api with the census data like this https://api.census.gov/data/2023/acs/acs5?get=NAME,B01001_001E&for=state%20(or%20part):*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620%20metropolitan%20division:35614&key=YOUR_KEY_GOES_HERE	How levels like metropolitan statistical are or metropolitan division are defined? is there an api url that has those areas?

## Short Answer:

- These are OMB-defined areas. The Census Bureau uses OMB’s Core-Based Statistical Area (CBSA) delineations in its data products.
- You can list them directly from the Census Data API by querying the geography level in the for= parameter (examples below).

### What the levels mean

- Core-Based Statistical Area (CBSA): OMB-defined areas based on urban cores and commuting ties.
  - Metropolitan Statistical Area (MSA): CBSA with urban core of 50,000+ people.
  - Micropolitan Statistical Area (µSA): CBSA with urban core of 10,000–49,999.
- Metropolitan Division (MDIV): County groupings within certain large MSAs (population 2.5M+) that represent distinct employment centers.
- Combined Statistical Area (CSA): Groupings of adjacent CBSAs with strong commuting interchange.
- In New England, there are equivalents called NECTAs and NECTA divisions (based on cities/towns rather than counties).

### How to get lists of these areas via the Census API (2023 ACS 5-year)

  - All MSAs and Micropolitan Areas (CBSAs): https://api.census.gov/data/2023/acs/acs5?get=NAME&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*
  - All Metropolitan Divisions: https://api.census.gov/data/2023/acs/acs5?get=NAME&for=metropolitan%20division:*
  - All Combined Statistical Areas: https://api.census.gov/data/2023/acs/acs5?get=NAME&for=combined%20statistical%20area:*
  - New England City and Town Areas (NECTAs): https://api.census.gov/data/2023/acs/acs5?get=NAME&for=new%20england%20city%20and%20town%20area:*
  - NECTA Divisions: https://api.census.gov/data/2023/acs/acs5?get=NAME&for=new%20england%20city%20and%20town%20area%20division:*

### Useful crosswalk-style queries

  - State parts within a given MSA (your example, NY-NJ-PA CBSA 35620): https://api.census.gov/data/2023/acs/acs5?get=NAME&for=state%20(or%20part):*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620 Note: “state (or part)” means the portion of each state that lies within the MSA.
  - Counties within a given MSA: https://api.census.gov/data/2023/acs/acs5?get=NAME&for=county:*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620
  - Counties within a Metropolitan Division (example: 35614): https://api.census.gov/data/2023/acs/acs5?get=NAME&for=county:*&in=metropolitan%20division:35614

### Where definitions come from

  - OMB definitions and bulletins: https://www.whitehouse.gov/omb/information-regulatory-affairs/statistical-programs-standards/
  - Census overview of metro/micro areas: https://www.census.gov/programs-surveys/metro-micro/about.html

### Discover available geography levels for a dataset

  - Human-readable list (recommended): https://api.census.gov/data/2023/acs/acs5/geography.html
  - You can then use those labels literally in the for= and in= parameters as shown above.

## Question

But if I want to a list of statistical areas or areas like indicated here: https://api.census.gov/data/2023/acs/acs5/examples.html or here: https://api.census.gov/data/2023/acs/acs5/geography.html to help my AI Agent to build up their own api calls. What should I do?

## Short Anser

# Building Census Data API calls for statistical areas (cheat sheet)

## Summary
- There isn’t a single JSON endpoint that lists all valid “for/in” geography levels for a dataset. The authoritative list is the HTML page at [geography.html](https://api.census.gov/data/2023/acs/acs5/geography.html).
- To help an agent build calls:
  1) Seed it with known geography tokens (CBSA, CSA, MDIV, NECTA, etc.).
  2) Enumerate actual areas by calling `for=<level>:*` (and, when needed, with `in=`…) and cache the results.

Reference pages:
- Human-readable geography list: https://api.census.gov/data/2023/acs/acs5/geography.html
- Examples: https://api.census.gov/data/2023/acs/acs5/examples.html

---

## Programmatically list areas (IDs and names)
Use the dataset itself to list every area for a geography level. Include `NAME` and `GEO_ID` so you can map names to codes later.

All examples below are for 2023 ACS 5-year.

- All CBSAs (Metropolitan/Micropolitan Statistical Areas):
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*

- All Metropolitan Divisions:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=metropolitan%20division:*

- All Combined Statistical Areas:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=combined%20statistical%20area:*

- NECTAs (New England City and Town Areas):
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=new%20england%20city%20and%20town%20area:*

- NECTA Divisions:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=new%20england%20city%20and%20town%20area%20division:*

- Urban Areas:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=urban%20area:*

### Common building blocks
- States:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=state:*

- Counties within a state (example NY=36):
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=county:*&in=state:36

- Places (cities/towns) within a state:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=place:*&in=state:36

- Tracts within a county:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=tract:*&in=state:36%20county:061

- Block groups within a tract:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=block%20group:*&in=state:36%20county:061%20tract:003100

- ZCTAs:
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=zip%20code%20tabulation%20area:*

---

## Crosswalk-style queries
Useful patterns for moving between geographies.

- Counties within a CBSA (example CBSA 35620):
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=county:*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620

- Counties within a Metropolitan Division (example 35614):
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=county:*&in=metropolitan%20division:35614

- States overlapping a CBSA (“state (or part)” requires an `in=`):
    
    https://api.census.gov/data/2023/acs/acs5?get=NAME,GEO_ID&for=state%20(or%20part):*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620

---

## What to give your AI agent

### Mapping of friendly names to API tokens
- CBSA, MSA, Micropolitan, “metro area” => `metropolitan statistical area/micropolitan statistical area`
- Metropolitan Division => `metropolitan division`
- Combined Statistical Area, CSA => `combined statistical area`
- NECTA => `new england city and town area`
- NECTA Division => `new england city and town area division`
- Urban Area => `urban area`
- State => `state`
- County => `county`
- Place (city/town) => `place`
- County Subdivision => `county subdivision`
- Census Tract => `tract`
- Block Group => `block group`
- ZCTA => `zip code tabulation area`
- PUMA => `public use microdata area`

### Procedure
1) Pick dataset and year (e.g., `2023/acs/acs5`).
2) If the user needs “a list of X,” call `get=NAME,GEO_ID&for=<token>:*` and cache results for lookup.
3) When a hierarchy is implied (e.g., tracts in a county, counties in a CBSA), construct `in=` chains using the codes from step 2.
4) Add variables (e.g., `B01001_001E`) to `get=` once the geo selection is known.

---

## Notes and caveats
- There is no official JSON for “all valid geography levels” per dataset; the authoritative listing is the HTML geography page linked above. Many teams scrape it once per vintage to seed their registry.
- Align geography vintage with the dataset year (e.g., 2023 ACS 5-year with 2023 geographies).
- Include `GEO_ID` in your `get=` list; it’s a stable identifier you can store.
- Discover and verify available geography levels (human-readable): https://api.census.gov/data/2023/acs/acs5/geography.html

---

## If you also need boundaries/shapes
TIGERweb REST services expose current CBSA, MDIV, CSA, and NECTA layers with codes and geometry.

- Service root: https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb
- Example CBSA codes and names (no geometry):  
  https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/CBSA/MapServer/0/query?where=1%3D1&outFields=CBSAFP,NAME,LSAD&returnGeometry=false&f=json

---

If you want, tell me which levels you need and I can return a ready-to-use JSON registry of codes and names for those levels.
