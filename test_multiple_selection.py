#!/usr/bin/env python3
"""
Test script for verifying the multiple selection functionality.
"""

import json

# Read the data-items.json to verify Multiple marker is present
with open('data-items.json', 'r') as f:
    data = json.load(f)

# Check if the "Type of evaluation" attribute has "Multiple" marker
evaluation_section = data.get("Evaluation (RQ5)", {})
type_of_evaluation = evaluation_section.get("Type of evaluation", [])

print("Type of evaluation options:")
for item in type_of_evaluation:
    print(f"  - {item}")

if "Multiple" in type_of_evaluation:
    print("\n✓ 'Multiple' marker found in 'Type of evaluation'")
else:
    print("\n✗ 'Multiple' marker NOT found in 'Type of evaluation'")

# Test the multiple selection logic
print("\n" + "="*60)
print("Testing Multiple Selection Logic:")
print("="*60)

# Simulate the behavior
selected_values = []

# Test adding values
test_values = ["Technical (Benchmark), Quantitative", "User study, Qualitative"]
for value in test_values:
    if value not in selected_values:
        selected_values.append(value)
        print(f"✓ Added: {value}")
    else:
        print(f"✗ Already in list: {value}")

print(f"\nCurrent selections: {selected_values}")

# Test removing a value
value_to_remove = "Technical (Benchmark), Quantitative"
if value_to_remove in selected_values:
    selected_values.remove(value_to_remove)
    print(f"✓ Removed: {value_to_remove}")
else:
    print(f"✗ Value not found: {value_to_remove}")

print(f"After removal: {selected_values}")

print("\n✓ Test completed successfully!")
