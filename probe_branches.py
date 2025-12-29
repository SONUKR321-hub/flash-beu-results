
import sys
import os
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from backend.api_client import BEUApiClient

def probe_branches():
    client = BEUApiClient()
    college = "149" # Gopalganj
    batch = 23
    sem = "I"
    exam = "Dec/2023"
    
    print(f"Probing branches for College {college}...")
    
    # Sequential probe
    # Common codes + specialized ones
    codes = [101, 102, 103, 104, 105, 106, 110, 155, 156, 157, 158, 159, 160]
    
    for code in codes:
        s_code = f"{code:03d}"
        reg_no = f"{batch}{s_code}{college}001"
        try:
            res = client.fetch_result(reg_no, sem, batch, exam)
            if res:
                c_name = res.get("course", "Unknown")
                print(f"✅ FOUND! Code: {s_code} -> {c_name}")
            else:
                print(f"❌ Miss: {s_code}")
        except:
             print(f"❌ Error: {s_code}")

if __name__ == "__main__":
    probe_branches()
