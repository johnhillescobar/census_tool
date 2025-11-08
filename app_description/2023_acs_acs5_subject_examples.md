# Census Data API: /data/2023/acs/acs5/subject/examples

- Source: https://api.census.gov/data/2023/acs/acs5/subject/examples.html
- Retrieved: 2025-11-08 01:50:55 UTC
- Notes:
  - 72 examples

## Table 1

| Geography Hierarchy | Geography Level | Example URL | Number |
| --- | --- | --- | --- |
| us | 010 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=us:* |  |
| us | 010 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=us:1 |  |
| region | 020 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=region:* |  |
| region | 020 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=region:3 |  |
| division | 030 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=division:* |  |
| division | 030 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=division:5 |  |
| state | 040 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=state:* |  |
| state | 040 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=state:06 |  |
| state › county | 050 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=county:* |  |
| state › county | 050 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=county:*&in=state:* |  |
| state › county | 050 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=county:037&in=state:06 |  |
| state › county › county subdivision | 060 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=county%20subdivision:*&in=state:48 |  |
| state › county › county subdivision | 060 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=county%20subdivision:*&in=state:48&in=county:* |  |
| state › county › county subdivision | 060 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=county%20subdivision:91835&in=state:48%20county:201 |  |
| state › county › county subdivision › subminor civil division | 067 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=subminor%20civil%20division:*&in=state:72%20county:127%20county%20subdivision:57247 |  |
| state › county › county subdivision › subminor civil division | 067 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=subminor%20civil%20division:76644&in=state:72%20county:127%20county%20subdivision:57247 |  |
| state › county › tract | 140 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=tract:*&in=state:06 |  |
| state › county › tract | 140 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=tract:*&in=state:06&in=county:* |  |
| state › county › tract | 140 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=tract:018700&in=state:06%20county:073 |  |
| state › place | 160 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=place:* |  |
| state › place | 160 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=place:*&in=state:* |  |
| state › place | 160 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=place:51000&in=state:36 |  |
| state › consolidated city | 170 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=consolidated%20city:* |  |
| state › consolidated city | 170 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=consolidated%20city:*&in=state:* |  |
| state › consolidated city | 170 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=consolidated%20city:36000&in=state:18 |  |
| state › alaska native regional corporation | 230 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=alaska%20native%20regional%20corporation:* |  |
| state › alaska native regional corporation | 230 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=alaska%20native%20regional%20corporation:*&in=state:* |  |
| state › alaska native regional corporation | 230 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=alaska%20native%20regional%20corporation:17140&in=state:02 |  |
| american indian area/alaska native area/hawaiian home land | 250 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=american%20indian%20area/alaska%20native%20area/hawaiian%20home%20land:* |  |
| american indian area/alaska native area/hawaiian home land | 250 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=american%20indian%20area/alaska%20native%20area/hawaiian%20home%20land:5620 |  |
| american indian area/alaska native area/hawaiian home land › tribal subdivision/remainder | 251 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=tribal%20subdivision/remainder:* |  |
| american indian area/alaska native area/hawaiian home land › tribal subdivision/remainder | 251 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=tribal%20subdivision/remainder:*&in=american%20indian%20area/alaska%20native%20area/hawaiian%20home%20land:* |  |
| american indian area/alaska native area/hawaiian home land › tribal subdivision/remainder | 251 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=tribal%20subdivision/remainder:640&in=american%20indian%20area/alaska%20native%20area/hawaiian%20home%20land:5550 |  |
| american indian area/alaska native area (reservation or statistical entity only) | 252 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=american%20indian%20area/alaska%20native%20area%20(reservation%20or%20statistical%20entity%20only):* |  |
| american indian area/alaska native area (reservation or statistical entity only) | 252 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=american%20indian%20area/alaska%20native%20area%20(reservation%20or%20statistical%20entity%20only):5620R |  |
| american indian area (off-reservation trust land only)/hawaiian home land | 254 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=american%20indian%20area%20(off-reservation%20trust%20land%20only)/hawaiian%20home%20land:* |  |
| american indian area (off-reservation trust land only)/hawaiian home land | 254 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=american%20indian%20area%20(off-reservation%20trust%20land%20only)/hawaiian%20home%20land:2430T |  |
| american indian area/alaska native area/hawaiian home land › tribal census tract | 256 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=tribal%20census%20tract:*&in=american%20indian%20area/alaska%20native%20area/hawaiian%20home%20land:3000 |  |
| american indian area/alaska native area/hawaiian home land › tribal census tract | 256 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=tribal%20census%20tract:T00500&in=american%20indian%20area/alaska%20native%20area/hawaiian%20home%20land:3000 |  |
| american indian area/alaska native area/hawaiian home land › state (or part) | 260 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=state%20(or%20part):*&in=american%20indian%20area/alaska%20native%20area/hawaiian%20home%20land:5620 |  |
| american indian area/alaska native area/hawaiian home land › state (or part) | 260 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=state%20(or%20part):40&in=american%20indian%20area/alaska%20native%20area/hawaiian%20home%20land:5620 |  |
| metropolitan statistical area/micropolitan statistical area | 310 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:* |  |
| metropolitan statistical area/micropolitan statistical area | 310 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620 |  |
| metropolitan statistical area/micropolitan statistical area › state (or part) › principal city (or part) | 312 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=principal%20city%20(or%20part):*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620%20state%20(or%20part):36 |  |
| metropolitan statistical area/micropolitan statistical area › state (or part) › principal city (or part) | 312 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=principal%20city%20(or%20part):51000&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620%20state%20(or%20part):36 |  |
| metropolitan statistical area/micropolitan statistical area › metropolitan division | 314 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=metropolitan%20division:*&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620 |  |
| metropolitan statistical area/micropolitan statistical area › metropolitan division | 314 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=metropolitan%20division:35614&in=metropolitan%20statistical%20area/micropolitan%20statistical%20area:35620 |  |
| combined statistical area | 330 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=combined%20statistical%20area:* |  |
| combined statistical area | 330 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=combined%20statistical%20area:408 |  |
| urban area | 400 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=urban%20area:* |  |
| urban area | 400 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=urban%20area:63217 |  |
| state › congressional district | 500 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=congressional%20district:* |  |
| state › congressional district | 500 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=congressional%20district:*&in=state:* |  |
| state › congressional district | 500 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=congressional%20district:98&in=state:72 |  |
| state › state legislative district (upper chamber) | 610 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=state%20legislative%20district%20(upper%20chamber):*&in=state:06 |  |
| state › state legislative district (upper chamber) | 610 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=state%20legislative%20district%20(upper%20chamber):039&in=state:06 |  |
| state › state legislative district (lower chamber) | 620 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=state%20legislative%20district%20(lower%20chamber):*&in=state:06 |  |
| state › state legislative district (lower chamber) | 620 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=state%20legislative%20district%20(lower%20chamber):027&in=state:06 |  |
| state › public use microdata area | 795 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=public%20use%20microdata%20area:* |  |
| state › public use microdata area | 795 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=public%20use%20microdata%20area:*&in=state:* |  |
| state › public use microdata area | 795 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=public%20use%20microdata%20area:04412&in=state:36 |  |
| zip code tabulation area | 860 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=zip%20code%20tabulation%20area:* |  |
| zip code tabulation area | 860 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=zip%20code%20tabulation%20area:77494 |  |
| state › school district (elementary) | 950 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(elementary):* |  |
| state › school district (elementary) | 950 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(elementary):*&in=state:* |  |
| state › school district (elementary) | 950 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(elementary):99999&in=state:48 |  |
| state › school district (secondary) | 960 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(secondary):* |  |
| state › school district (secondary) | 960 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(secondary):*&in=state:* |  |
| state › school district (secondary) | 960 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(secondary):99999&in=state:48 |  |
| state › school district (unified) | 970 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(unified):* |  |
| state › school district (unified) | 970 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(unified):*&in=state:* |  |
| state › school district (unified) | 970 | https://api.census.gov/data/2023/acs/acs5/subject?get=NAME,S0101_C01_001E&for=school%20district%20(unified):99999&in=state:06 |  |
