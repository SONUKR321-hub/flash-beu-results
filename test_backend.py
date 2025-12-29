
import sys
import os

# Create source path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from backend.api_client import BEUApiClient

def test_fetch():
    client = BEUApiClient()
    # Test Data: Gaya College (110), CSE (105), Batch 23, Sem III
    # Reg No: 23105110001
    
    reg_no = "23105110001"
    
    print(f"Testing fetch for {reg_no}...")
    result = client.fetch_result(reg_no, "III", 23, "July/2025")
    
    if result:
        print("Success!")
        print(f"Student: {result.get('name')}")
        print(f"SGPA: {result.get('sgpa')}")
    else:
        print("Failed to fetch result. (Note: This might be expected if the specific student doesn't exist or exam data is old)")

if __name__ == "__main__":
    test_fetch()
