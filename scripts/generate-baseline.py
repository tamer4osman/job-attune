#!/usr/bin/env python3
import json
import subprocess
import sys

# Run fallow health check and get JSON output
result = subprocess.run(
    ["npx", "--yes", "fallow@3.38.1", "health", "--ci", "--format", "json"],
    capture_output=True,
    text=True
)

# Parse the output - find the JSON part (starts with {)
output = result.stdout + result.stderr
lines = output.split('\n')

json_start = None
for i, line in enumerate(lines):
    if line.strip().startswith('{') and '"kind":"health"' in line:
        json_start = i
        break

if json_start is None:
    print("Could not find JSON in output", file=sys.stderr)
    sys.exit(1)

json_text = '\n'.join(lines[json_start:])
data = json.loads(json_text)

# Build the baseline with finding_counts
finding_counts = {}

for finding in data['findings']:
    path = finding['path']
    severity = finding['severity']  # critical, high, moderate
    crap_key = f'crap_{severity}'
    
    if path not in finding_counts:
        finding_counts[path] = {}
    
    if crap_key not in finding_counts[path]:
        finding_counts[path][crap_key] = {'count': 0}
    
    finding_counts[path][crap_key]['count'] += 1

# Build the baseline
baseline = {
    'kind': 'health',
    'finding_counts': finding_counts,
    'runtime_coverage_findings': [],
    'target_keys': []
}

# Print summary
total_critical = sum(1 for f in data['findings'] if f['severity'] == 'critical')
total_high = sum(1 for f in data['findings'] if f['severity'] == 'high')
total_moderate = sum(1 for f in data['findings'] if f['severity'] == 'moderate')

print(f"Total findings: {len(data['findings'])}")
print(f"  Critical: {total_critical}")
print(f"  High: {total_high}")
print(f"  Moderate: {total_moderate}")

# Write to health-current.json
with open('.codebase-intel/health-current.json', 'w') as f:
    json.dump(data, f, indent=2)

# Write the baseline (finding_counts only)
with open('.codebase-intel/fallow-health-baseline.json', 'w') as f:
    json.dump(baseline, f, indent=2)

print("Updated .codebase-intel/fallow-health-baseline.json")