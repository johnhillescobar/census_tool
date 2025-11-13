"""Analyze test log to compare expected vs actual API calls"""
import csv
import re
import json
from pathlib import Path

# Read expected API calls from CSV
test_questions_file = Path("test_questions/test_questions_new.csv")
log_file = Path("logs/test_logs/test_suite_20251111_212328.txt")

expected_calls = {}
with open(test_questions_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        q_no = row['No']
        expected_calls[q_no] = {
            'question': row['Question friendly human'],
            'expected_url': row['API call']
        }

# Parse log file to extract actual API calls
actual_calls = {}
current_q = None

with open(log_file, 'r', encoding='utf-8') as f:
    content = f.read()
    
# Find all question markers
q_pattern = r'Q(\d+):\s*(.+?)(?=\n|$)'
questions = re.findall(q_pattern, content)

# Find all census_api_call actions
api_pattern = r'Action: census_api_call\s+Action Input: ({[^}]+(?:{[^}]+})*[^}]*})'
api_matches = list(re.finditer(api_pattern, content, re.MULTILINE))

# Also find URLs in responses
url_pattern = r'"url":\s*"([^"]+)"'
url_matches = list(re.finditer(url_pattern, content))

print(f"Found {len(questions)} questions")
print(f"Found {len(api_matches)} API call actions")
print(f"Found {len(url_matches)} URLs in responses\n")

# Match questions to API calls
q_positions = {}
for q_match in re.finditer(r'Q(\d+):', content):
    q_no = q_match.group(1)
    q_pos = q_match.start()
    if q_no not in q_positions:
        q_positions[q_no] = []
    q_positions[q_no].append(q_pos)

# For each question, find API calls that occur after it
results = []
for q_no in sorted(expected_calls.keys(), key=int):
    if q_no not in q_positions:
        results.append({
            'q_no': q_no,
            'status': 'NOT_FOUND',
            'expected': expected_calls[q_no]['expected_url'],
            'actual': None,
            'question': expected_calls[q_no]['question']
        })
        continue
    
    q_start = min(q_positions[q_no])
    # Find next question start (or end of file)
    next_q_start = len(content)
    for other_q in q_positions:
        if int(other_q) > int(q_no):
            next_q_start = min(next_q_start, min(q_positions[other_q]))
    
    # Find API calls in this question's section
    section_calls = []
    for api_match in api_matches:
        if q_start <= api_match.start() < next_q_start:
            try:
                api_input = json.loads(api_match.group(1))
                section_calls.append(api_input)
            except:
                pass
    
    # Find URLs in this section
    section_urls = []
    for url_match in url_matches:
        if q_start <= url_match.start() < next_q_start:
            section_urls.append(url_match.group(1))
    
    # Build actual URL from API call parameters
    actual_url = None
    if section_calls:
        # Use the last API call (most likely the final one)
        last_call = section_calls[-1]
        dataset = last_call.get('dataset', '')
        year = last_call.get('year', '')
        variables = last_call.get('variables', [])
        geo_for = last_call.get('geo_for', {})
        geo_in = last_call.get('geo_in', {})
        
        # Build URL
        base = f"https://api.census.gov/data/{year}/{dataset}"
        vars_str = ','.join(variables) if isinstance(variables, list) else str(variables)
        
        geo_parts = []
        if geo_for:
            for k, v in geo_for.items():
                geo_parts.append(f"for={k}:{v}")
        if geo_in:
            in_parts = []
            for k, v in geo_in.items():
                in_parts.append(f"{k}:{v}")
            if in_parts:
                geo_parts.append(f"in={' '.join(in_parts)}")
        
        params = [f"get={vars_str}"] + geo_parts
        actual_url = f"{base}?{'&'.join(params)}"
    
    # Or use URL from response if available
    if not actual_url and section_urls:
        actual_url = section_urls[-1]
    
    results.append({
        'q_no': q_no,
        'status': 'FOUND' if section_calls else 'NO_CALLS',
        'expected': expected_calls[q_no]['expected_url'],
        'actual': actual_url,
        'question': expected_calls[q_no]['question'],
        'api_calls_count': len(section_calls)
    })

# Print comparison
print("=" * 100)
print("API CALL COMPARISON")
print("=" * 100)
print()

matches = 0
mismatches = 0
not_found = 0

for r in results:
    q_no = r['q_no']
    expected = r['expected']
    actual = r['actual']
    status = r['status']
    
    if status == 'NOT_FOUND':
        print(f"Q{q_no}: [X] QUESTION NOT FOUND IN LOG")
        not_found += 1
    elif status == 'NO_CALLS':
        print(f"Q{q_no}: [!] NO API CALLS FOUND")
        print(f"   Expected: {expected}")
        not_found += 1
    else:
        # Normalize URLs for comparison (remove key, normalize encoding)
        exp_norm = expected.replace(' ', '%20').split('&key=')[0] if '&key=' in expected else expected.replace(' ', '%20')
        act_norm = actual.replace(' ', '%20').split('&key=')[0] if actual and '&key=' in actual else (actual.replace(' ', '%20') if actual else None)
        
        # Compare core parts
        if actual and exp_norm in act_norm or (actual and act_norm and exp_norm == act_norm):
            print(f"Q{q_no}: [OK] MATCH")
            matches += 1
        else:
            print(f"Q{q_no}: [X] MISMATCH")
            print(f"   Question: {r['question'][:60]}...")
            print(f"   Expected: {expected}")
            print(f"   Actual:   {actual}")
            print(f"   API calls made: {r.get('api_calls_count', 0)}")
            mismatches += 1
    print()

print("=" * 100)
print(f"SUMMARY: {matches} matches, {mismatches} mismatches, {not_found} not found")
print("=" * 100)

