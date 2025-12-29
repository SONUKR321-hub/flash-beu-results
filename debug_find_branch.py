
import sys
import os
import requests
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from backend.api_client import BEUApiClient

def find_correct_branch():
    client = BEUApiClient()
    college = "149" # Gopalganj
    batch = 24 # Batch 24
    sem = "I"
    date = "May/2025" # Likely date from screenshot analysis context
    
    print(f"Brute Forcing Branch Code for Batch {batch} College {college}...")
    
    def check(code):
        s_code = f"{code:03d}"
        # Try a few students to be safe
        for i in range(1, 4):
            reg = f"{batch}{s_code}{college}{i:03d}"
            res = client.fetch_result(reg, sem, batch, date)
            if res:
                return f"{s_code} -> {res.get('course')} (Student: {res.get('name')})"
        return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(check, c): c for c in range(100, 200)}
        
        for future in futures:
            res = future.result()
            if res:
                print(f"🔥 MATCH FOUND! {res}")

if __name__ == "__main__":
    find_correct_branch()
