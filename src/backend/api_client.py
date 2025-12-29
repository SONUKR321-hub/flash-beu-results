
import requests
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.beu-bih.ac.in/backend/v1/result/get-result"

class BEUApiClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.beu-bih.ac.in/',
        })

    def fetch_result(self, registration_no: str, semester: str, batch_year: int, exam_held: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a single result from the BEU API.
        
        Args:
            registration_no: The full registration number.
            semester: Roman numeral of the semester (e.g., 'I', 'III').
            batch_year: The 2-digit batch year (e.g., 23).
            exam_held: String like "July/2025".
        """
        params = {
            "year": batch_year,
            "redg_no": registration_no,
            "semester": semester,
            "exam_held": exam_held
        }

        # Debug: Print the exact URL being requested
        print(f"DEBUG FETCH: {BASE_URL} params={params}")

        try:
            response = self.session.get(BASE_URL, params=params, timeout=10)
            print(f"DEBUG STATUS: {response.status_code} for {registration_no}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    # The API returns structured data. We need to check 'status' or content.
                    # Based on reference, it returns { "status": 200, "data": { ... } }
                    if data.get("status") == 200 and data.get("data"):
                         return data["data"]
                except ValueError:
                    logger.error(f"Invalid JSON response for {registration_no}")
            
            return None
        except requests.RequestException as e:
            logger.warning(f"Request failed for {registration_no}: {e}")
            return None

    def fetch_batch_results(
        self, 
        start_reg: int, 
        end_reg: int, 
        branch_code: str, 
        college_code: str, 
        batch_year: int, 
        semester: str, 
        exam_held: str,
        include_lateral: bool = False,
        workers: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetches results for a range of students.
        """
        results = []
        tasks = {}

        # Generator for registration numbers
        def generate_reg_nos():
            # Regular students
            for i in range(start_reg, end_reg + 1):
                yield f"{batch_year}{branch_code}{college_code}{i:03d}", batch_year
            
            # Lateral Entry (LE) students
            # LE students usually join a year later but represent the same batch theoretically for exams?
            # Reference repo says: LE Batch = Batch + 1. Reg IDs 901-930.
            if include_lateral:
                le_batch = batch_year + 1
                for i in range(901, 931):
                    yield f"{le_batch}{branch_code}{college_code}{i:03d}", le_batch

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for reg_no, year_param in generate_reg_nos():
                # Note: The API 'year' param usually matches the registration prefix.
                future = executor.submit(self.fetch_result, reg_no, semester, year_param, exam_held)
                tasks[future] = reg_no

            for future in as_completed(tasks):
                res = future.result()
                if res:
                    results.append(res)
        
        return results

