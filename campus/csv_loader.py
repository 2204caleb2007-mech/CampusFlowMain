import csv
import os
from typing import List, Dict, Any
from functools import lru_cache

# Adjust base directory based on execution context
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

@lru_cache(maxsize=10)
def load_csv(filename: str) -> List[Dict[str, str]]:
    """
    Load a CSV file from the data directory and return it as a list of dictionaries.
    Results are cached to improve performance.
    """
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return []
        
    results = []
    try:
        with open(filepath, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(row)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        
    return results

def get_lab_schedule() -> List[Dict[str, str]]:
    """Get the dynamic lab schedule from CSV."""
    return load_csv("lab_schedule.csv")

def get_lab_timetable() -> List[Dict[str, str]]:
    """Get the fixed curriculum lab timetable from CSV."""
    return load_csv("lab_timetable.csv")

def get_students() -> List[Dict[str, str]]:
    """Get student records from CSV."""
    return load_csv("students.csv")

def clear_cache():
    """Clear the CSV cache. Useful if the CSVs are updated during runtime."""
    load_csv.cache_clear()
