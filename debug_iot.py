
import sys
import os
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from backend.api_client import BEUApiClient

def debug_iot():
    client = BEUApiClient()
    college = "149" # Gopalganj
    branch = "155" # CSE IoT (Assumed)
    
    print("Debugging CSE IoT (155) for Gopalganj (149)...")
    
    scenarios = [
        # Batch 23
        {"batch": 23, "sem": "I", "dates": ["Dec/2023", "Nov/2023", "Jan/2024"]},
        {"batch": 23, "sem": "II", "dates": ["July/2024", "May/2024", "June/2024"]},
        # Batch 24
        {"batch": 24, "sem": "I", "dates": ["May/2025", "July/2025", "Dec/2024"]}
    ]
    
    for s in scenarios:
        batch = s['batch']
        sem = s['sem']
        print(f"\n--- Checking Batch {batch} Sem {sem} ---")
        
        # Try first 5 students
        for i in range(1, 6):
            reg = f"{batch}{branch}{college}{i:03d}"
            
            for date in s['dates']:
                print(f"Checking {reg} @ {date}...", end=" ")
                res = client.fetch_result(reg, sem, batch, date)
                if res:
                    print("✅ FOUND!")
                    print(f"Name: {res.get('name')}")
                    print(f"SGPA: {res.get('sgpa')}")
                    return
                else:
                    print("❌")

if __name__ == "__main__":
    debug_iot()
