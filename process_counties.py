#!/usr/bin/env python3
"""
Script to process counties data and create a column with county names only (without state).
"""

import pandas as pd
import re
from pathlib import Path


def extract_county_name(name):
    """
    Extract county name from a location name, removing state-specific suffixes.

    Args:
        name (str): The full location name

    Returns:
        str: The county name without state suffixes
    """
    if pd.isna(name):
        return name

    # Common patterns to remove state-specific suffixes
    patterns_to_remove = [
        r",\s*\w+$",  # Remove ", State" pattern
        r"\s+County$",  # Remove " County" suffix
        r"\s+Parish$",  # Remove " Parish" suffix (Louisiana)
        r"\s+Borough$",  # Remove " Borough" suffix (Alaska)
        r"\s+City$",  # Remove " City" suffix
        r"\s+Town$",  # Remove " Town" suffix
        r"\s+Township$",  # Remove " Township" suffix
        r"\s+Municipality$",  # Remove " Municipality" suffix
    ]

    county_name = name.strip()

    # Apply each pattern
    for pattern in patterns_to_remove:
        county_name = re.sub(pattern, "", county_name, flags=re.IGNORECASE)

    return county_name.strip()


def process_counties_data(input_file, output_file):
    """
    Process the counties data and create a new column with county names only.

    Args:
        input_file (str): Path to the input CSV file
        output_file (str): Path to the output CSV file
    """
    print(f"Reading data from {input_file}...")

    # Read the CSV file
    df = pd.read_csv(input_file)

    print(f"Loaded {len(df)} records")
    print(f"Columns: {list(df.columns)}")

    # Create a new column with county names only
    print("Creating county-only names...")
    df["County_Name_Only"] = df["Name"].apply(extract_county_name)

    # Show some examples
    print("\nSample of original names vs county-only names:")
    sample_df = df[["Name", "State Name", "County_Name_Only"]].head(10)
    for idx, row in sample_df.iterrows():
        print(
            f"Original: {row['Name']} | State: {row['State Name']} | County Only: {row['County_Name_Only']}"
        )

    # Save the processed data
    print(f"\nSaving processed data to {output_file}...")
    df.to_csv(output_file, index=False)

    print(f"Processing complete! Saved {len(df)} records to {output_file}")

    # Show statistics
    print(f"\nStatistics:")
    print(f"Total records: {len(df)}")
    print(f"Unique county names: {df['County_Name_Only'].nunique()}")
    print(f"Records with null county names: {df['County_Name_Only'].isna().sum()}")


if __name__ == "__main__":
    # Set up file paths
    input_file = "src/locations/locations.csv"
    output_file = "src/locations/locations_with_county_names.csv"

    # Check if input file exists
    if not Path(input_file).exists():
        print(f"Error: Input file {input_file} not found!")
        exit(1)

    # Process the data
    process_counties_data(input_file, output_file)
