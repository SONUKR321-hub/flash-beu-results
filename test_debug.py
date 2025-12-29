
import sys
import os

# Create source path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from backend.api_client import BEUApiClient

def test_fetch():
    client = BEUApiClient()
    
    # User's failed query
    reg_no = "24105110001"
    sem = "III"
    exam = "Dec/2024"
    
    print(f"Testing User Query: Reg={reg_no}, Sem={sem}, Exam={exam}")
    result = client.fetch_result(reg_no, sem, 24, exam)
    
    if result:
        print("Success!")
    else:
        print("Failed (Expected, as Batch 24 shouldn't be in Sem III yet)")

    # Correct query for Sem III (Batch 23)
    reg_no_23 = "23105110001"
    print(f"\nTesting Corrected Query (Batch 23): Reg={reg_no_23}, Sem={sem}, Exam={exam}")
    result_23 = client.fetch_result(reg_no_23, sem, 23, exam) # Note: Exam might need to be July/2024 or Dec/2024 depending on session
    
    # Actually, if Batch 23 started in 2023:
    # Dec 2023 -> Sem I
    # June 2024 -> Sem II
    # Dec 2024 -> Sem III
    # So Dec/2024 is correct for Batch 23 Sem III.
    
    if result_23:
        print("Success with Batch 23!")
    else:
        print("Failed Batch 23 too. Trying batch 22...")

if __name__ == "__main__":
    test_fetch()
