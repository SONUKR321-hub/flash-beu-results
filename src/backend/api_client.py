
import requests
import time
import logging
import re
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
            exam_held: String like "July/2025" or "ASPX_2023_SEM1".
        """
        if exam_held == "ASPX_2023_SEM1":
            return self._fetch_aspx_2023_sem1(registration_no)
        if exam_held == "ASPX_2023_SEM2":
            return self._fetch_aspx_2023_sem2(registration_no)

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

    def _fetch_aspx_2023_sem1(self, registration_no: str) -> Optional[Dict[str, Any]]:
        return self._fetch_aspx_legacy(
            registration_no,
            url="https://results.beup.ac.in/BTech1stSem2023_B2023Results.aspx",
            semester="I",
            exam_held="July/2024",
        )


    def _fetch_aspx_2023_sem2(self, registration_no: str) -> Optional[Dict[str, Any]]:
        return self._fetch_aspx_legacy(
            registration_no,
            url="https://results.beup.ac.in/BTech2ndSem2024_B2023Results.aspx",
            semester="II",
            exam_held="Jan/2025",
        )

    def _fetch_aspx_legacy(self, registration_no: str, url: str, semester: str, exam_held: str) -> Optional[Dict[str, Any]]:
        """Generic ASPX scraper for BEU legacy result portals."""
        try:
            res = self.session.get(url, timeout=10)
            viewstate_match = re.search(r'id="__VIEWSTATE"\s+value="([^"]+)"', res.text)
            eventval_match = re.search(r'id="__EVENTVALIDATION"\s+value="([^"]+)"', res.text)
            if not viewstate_match or not eventval_match:
                return None
            data = {
                "__VIEWSTATE": viewstate_match.group(1),
                "__EVENTVALIDATION": eventval_match.group(1),
                "ctl00$ContentPlaceHolder1$TextBox_RegNo": registration_no,
                "ctl00$ContentPlaceHolder1$Button_Show": "Show Result"
            }
            res_post = self.session.post(url, data=data, timeout=10)
            html = res_post.text
            if "You may have entered a Wrong Registration Number" in html and "StudentNameLabel" not in html:
                return None
            def _get(pattern):
                m = re.search(pattern, html)
                return m.group(1).strip() if m else None
            name = _get(r'id="ContentPlaceHolder1_DataList1_StudentNameLabel_0"[^>]*>([^<]+)</span>')
            if not name:
                return None
            sgpa_str = _get(r'id="ContentPlaceHolder1_DataList5_GROSSTHEORYTOTALLabel_0"[^>]*>([^<]+)</span>')
            father = _get(r'id="ContentPlaceHolder1_DataList1_FatherNameLabel_0"[^>]*>([^<]+)</span>')
            college_code = _get(r'id="ContentPlaceHolder1_DataList1_CollegeCodeLabel_0"[^>]*>([^<]+)</span>')
            college_name = _get(r'id="ContentPlaceHolder1_DataList1_CollegeNameLabel_0"[^>]*>([^<]+)</span>')
            course_name = _get(r'id="ContentPlaceHolder1_DataList1_CourseLabel_0"[^>]*>([^<]+)</span>')
            remark = _get(r'id="ContentPlaceHolder1_DataList3_remarkLabel_0"[^>]*>([^<]*)</span>')
            status = "PASS" if not remark else "FAIL"
            theory_rows = re.findall(
                r'<td align="center">(\d+)</td><td align="left">([^<]+)</td>'
                r'<td align="center">([^<]+)</td><td align="center">([^<]+)</td>'
                r'<td align="center">([^<]+)</td><td align="center">([^<]+)</td>'
                r'<td align="center">([^<]+)</td>',
                html
            )
            theory_subjects = []
            for row in theory_rows:
                code, subj_name, ese, ia, total, grade, credit = row
                try:
                    credit_f = float(credit)
                except ValueError:
                    credit_f = None
                theory_subjects.append({
                    "code": code, "name": subj_name.strip(),
                    "ese": ese.strip(), "ia": ia.strip(),
                    "total": total.strip(), "grade": grade.strip(), "credit": credit_f,
                })
            return {
                "redg_no": registration_no,
                "name": name,
                "father_name": father,
                "college_code": college_code,
                "college_name": college_name.title() if college_name else None,
                "course": course_name.title() if course_name else None,
                "semester": semester,
                "exam_held": exam_held,
                "sgpa": [sgpa_str] if sgpa_str else [],
                "cgpa": sgpa_str,
                "fail_any": status,
                "theorySubjects": theory_subjects,
                "practicalSubjects": [],
            }
        except requests.RequestException as e:
            logger.warning(f"ASPX legacy request failed for {registration_no}: {e}")
        return None
