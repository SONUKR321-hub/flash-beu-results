
import sys
import os
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from backend.api_client import BEUApiClient

def debug_gopalganj_cse():
    client = BEUApiClient()
    college = "149" # Gopalganj
    batch = 23
    sem = "I"
    dates = ["Dec/2023", "Jan/2024"]
    
    branches = {
        "105": "CSE (Core)",
        "155": "CSE (IoT)",
        "156": "CSE (Cyber)",
        "157": "CSE (DS)"
    }
    
    print("Checking Gopalganj (149) Batch 23 Sem I...")
    
    for b_code, b_name in branches.items():
        print(f"\nChecking {b_name} ({b_code})...")
        found = False
        for date in dates:
            # Check 001 to 010
            for i in range(1, 11):
                reg = f"{batch}{b_code}{college}{i:03d}"
                res = client.fetch_result(reg, sem, batch, date)
                if res and res.get('name'):
                    print(f"✅ FOUND! {b_name} exists. Student: {res['name']} ({reg}) Date: {date}")
                    found = True
                    break
            if found: break
        
        if not found:
            print(f"❌ {b_name} ({b_code}) NOT FOUND or no results.")

if __name__ == "__main__":
    debug_gopalganj_cse()
