
import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from backend.api_client import BEUApiClient

def inspect_raw_result():
    client = BEUApiClient()
    # Using a known student from previous tests
    reg_no = "22105110001"
    sem = "IV"
    batch = 22
    dates = ["May/2024", "Dec/2023", "July/2024", "Sep/2024"]
    
    for date in dates:
        print(f"Trying {date}...")
        result = client.fetch_result(reg_no, sem, batch, date)
        
        if result:
            print(f"SUCCESS! Found result for {date}")
            theory = result.get("theorySubjects", [])
            if theory:
                print("\nRaw Theory Subject Example:")
                print(json.dumps(theory[0], indent=2))
            
            practical = result.get("practicalSubjects", [])
            if practical:
                print("\nRaw Practical Subject Example:")
                print(json.dumps(practical[0], indent=2))
            return
    
    print("Failed to fetch result for all dates.")

if __name__ == "__main__":
    inspect_raw_result()
