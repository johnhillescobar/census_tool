# Manual QA Checklist - Geography Validation

Run these queries through main.py before declaring validation "fixed":

## Basic Queries (Should Work)
- [ ] "What's the population of California?" (state level)
- [ ] "Show population for all states" (state enumeration)
- [ ] "Population of Los Angeles County" (county level)

## Complex Queries (May Fail - Document Behavior)
- [ ] "Population by metropolitan division" (complex hierarchy)
- [ ] "Show data for CBSA 35620" (CBSA level)

## Expected Failures (Should Return Clear Error)
- [ ] "Population of Mars" (invalid geography)
- [ ] "Show me data from 1800" (invalid year)

## Validation
For each query:
1. Run: `python main.py`
2. Enter query
3. Check logs for:
   - Does it complete within 3 minutes? (Y/N)
   - Does it return an answer or clear error? (Y/N)
   - Does it loop with repeated tool calls? (Y/N - should be N)

Status: 🔴 Fails / 🟡 Works with caveats / 🟢 Passes

