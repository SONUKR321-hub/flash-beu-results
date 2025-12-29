
import sys
import os
import requests

# Create source path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from backend.api_client import BEUApiClient

def probe_exam_date():
    client = BEUApiClient()
    
    reg_no = "23105110001" 
    # Batch 23, Civil (101), MIT (107), 001
    
    sem = "I" # Verify student exists first
    batch = 23
    
    # List of possible exam dates to try
    dates_to_try = [
        "Dec/2023", "Jan/2024", "Nov/2023", "May/2024", "July/2024", "Aug/2024", "Sep/2024", "Oct/2024"
    ]
    
    print(f"Probing Exam Dates for {reg_no} (Sem {sem})...")
    
    for date in dates_to_try:
        print(f"Trying {date}...", end=" ")
        result = client.fetch_result(reg_no, sem, batch, date)
        if result:
            print(f"SUCCESS! Found result with date: {date}")
            print(f"Student: {result.get('name')}")
            return
        else:
            print("No.")
            
    print("All probes failed.")

if __name__ == "__main__":
    probe_exam_date()
