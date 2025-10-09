
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