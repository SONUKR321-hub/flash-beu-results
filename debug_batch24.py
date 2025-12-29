
import sys
import os
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from backend.api_client import BEUApiClient

def check_batch_24():
    client = BEUApiClient()
    
    # Target: Batch 24, Gopalganj (149), CSE IoT (155)
    college = "149"
    branch = "155"
    batch = 24
    sem = "I"
    
    # Try multiple students
    reg_start = 1
    reg_end = 5
    
    dates = ["Dec/2024", "Nov/2024", "Jan/2025", "May/2025"]
    
    print(f"Deep Check: Batch {batch} | Branch {branch} | College {college}")
    
    for i in range(reg_start, reg_end + 1):
        reg_no = f"{batch}{branch}{college}{i:03d}"
        print(f"\nChecking Student: {reg_no}")
        
        for date in dates:
            print(f"  > Probing {date}...", end=" ")
            # We want to see the RAW response to understand why 200 OK might fail
            try:
                params = {
                    "year": batch,
                    "redg_no": reg_no,
                    "semester": sem,
                    "exam_held": date
                }
                resp = client.session.get("https://www.beu-bih.ac.in/backend/v1/result/get-result", params=params, timeout=10)
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    try:
                        json_data = resp.json()
                        # Print keys to see if 'data' exists
                        print(f"    JSON Keys: {list(json_data.keys())}")
                        if json_data.get('data'):
                             print("    ✅ DATA FOUND found!")
                             print(f"    Name: {json_data['data'].get('name')}")
                             return
                        else:
                             print(f"    ⚠️ Data field empty/null. Message: {json_data.get('message')}")
                    except:
                        print("    ❌ Invalid JSON")
            except Exception as e:
                print(f"    ❌ Error: {e}")

if __name__ == "__main__":
    check_batch_24()
