import pandas as pd
from pathlib import Path

# Base directory to simulate test cases
output_dir = Path("/home/shanks/data/github/preptura/data/preptura_test_csvs")
output_dir.mkdir(exist_ok=True)

# Case 1: Good CSV
df_good = pd.DataFrame({
    "Name": ["Alice", "Bob", "Charlie"],
    "Age": [25, 30, 35],
    "City": ["New York", "Los Angeles", "Chicago"]
})
df_good.to_csv(output_dir / "good_data.csv", index=False)

# Case 2: Missing headers
df_missing_headers = pd.DataFrame([
    ["Alice", 25, "New York"],
    ["Bob", 30, "Los Angeles"],
    ["Charlie", 35, "Chicago"]
])
df_missing_headers.to_csv(output_dir / "missing_headers.csv", index=False, header=False)

# Case 3: Empty columns
df_empty_cols = pd.DataFrame({
    "Name": ["Alice", "Bob", "Charlie"],
    "Unused1": [None, None, None],
    "Age": [25, 30, 35],
    "Unused2": [None, None, None]
})
df_empty_cols.to_csv(output_dir / "empty_columns.csv", index=False)

# Case 4: Mixed data types in a column
df_mixed_types = pd.DataFrame({
    "ID": [1, 2, "three", 4],
    "Value": [10.5, "unknown", 8.2, 7.1]
})
df_mixed_types.to_csv(output_dir / "mixed_types.csv", index=False)

# Case 5: Empty rows
df_empty_rows = pd.DataFrame({
    "Name": ["Alice", None, "Charlie", None],
    "Age": [25, None, 35, None],
    "City": ["New York", None, "Chicago", None]
})
df_empty_rows.to_csv(output_dir / "empty_rows.csv", index=False)

