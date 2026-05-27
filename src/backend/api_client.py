
import requests
import time
import logging
import re
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any

# Disable SSL warnings for BEU legacy ASPX servers
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://beu-bih.ac.in/backend/v1/result/get-result"
TOKEN_URL = "https://beu-bih.ac.in/backend/v1/result/token"

class BEUApiClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False  # Critical for old BEU ASPX portals with expired certs
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://beu-bih.ac.in/result-one',
        })

    def fetch_result(self, registration_no: str, semester: str, batch_year: int, exam_held: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a single result from the BEU API or legacy ASPX portals.
        """
        # Explicit markers used for automated fetching
        if exam_held == "ASPX_2023_SEM1":
            return self._fetch_aspx_2023_sem1(registration_no)
        if exam_held == "ASPX_2023_SEM2":
            return self._fetch_aspx_2023_sem2(registration_no)

        # Dynamic routing for UI searches based on target batch and semester
        try:
            b_yr = int(batch_year)
            if b_yr == 23 and semester == "I":
                return self._fetch_aspx_2023_sem1(registration_no)
            if b_yr == 23 and semester == "II":
                return self._fetch_aspx_2023_sem2(registration_no)
        except Exception:
            pass

        # 1. Fetch a fresh single-use token from the BEU API
        token = None
        try:
            r_token = self.session.get(TOKEN_URL, timeout=10)
            if r_token.status_code == 200:
                token = r_token.json().get("token")
            else:
                logger.error(f"Failed to fetch token: {r_token.status_code} - {r_token.text}")
        except Exception as e:
            logger.error(f"Error fetching token: {e}")

        if not token:
            logger.warning(f"Could not proceed for {registration_no} due to missing token.")
            return None

        # 2. Fetch result using the single-use token
        params = {
            "year": batch_year,
            "redg_no": registration_no,
            "semester": semester,
            "exam_held": exam_held,
            "token": token
        }

        # Debug: Print the exact URL being requested (excluding raw token details for brevity)
        print(f"DEBUG FETCH: {BASE_URL} params={{'year': {batch_year}, 'redg_no': {registration_no}, 'semester': '{semester}', 'exam_held': '{exam_held}', 'token': '...'}}")

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


    def find_active_colleges(
        self,
        branch_code: str,
        batch_year: int,
        semester: str,
        exam_held: str,
        college_codes_list: List[str]
    ) -> List[str]:
        """
        Probes a list of colleges (rolls 001 and 002) in parallel to find which ones offer the branch
        and have results published for this semester/exam session.
        """
        active_colleges = []
        tasks = {}
        
        # Adjust thread pool size dynamically up to 60 workers
        max_workers = min(60, len(college_codes_list) * 2)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for c_code in college_codes_list:
                for roll in ["001", "002"]:
                    reg_no = f"{batch_year}{branch_code}{c_code}{roll}"
                    # Probing using fetch_result
                    future = executor.submit(self.fetch_result, reg_no, semester, batch_year, exam_held)
                    tasks[future] = c_code
                    
            for future in as_completed(tasks):
                c_code = tasks[future]
                res = future.result()
                if res and c_code not in active_colleges:
                    active_colleges.append(c_code)
                    
        return active_colleges

    def fetch_batch_results(
        self, 
        start_reg: int, 
        end_reg: int, 
        branch_code: str, 
        college_code: Any, 
        batch_year: int, 
        semester: str, 
        exam_held: str,
        include_lateral: bool = False,
        workers: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches results for a range of students.
        Supports single college_code (str) or multiple college_codes (list/tuple/set/iterable).
        """
        if isinstance(college_code, str):
            colleges = [college_code]
        else:
            colleges = list(college_code)

        results = []
        tasks = {}

        # Generator for registration numbers across all target colleges
        def generate_reg_nos():
            for c_code in colleges:
                # Regular students
                for i in range(start_reg, end_reg + 1):
                    yield f"{batch_year}{branch_code}{c_code}{i:03d}", batch_year
                
                # Lateral Entry (LE) students
                if include_lateral:
                    le_batch = batch_year + 1
                    for i in range(901, 931):
                        yield f"{le_batch}{branch_code}{c_code}{i:03d}", le_batch

        # Adjust workers dynamically if fetching multiple colleges in parallel
        if workers is None:
            workers = min(60, len(colleges) * 15)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            for reg_no, year_param in generate_reg_nos():
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
            mother = _get(r'id="ContentPlaceHolder1_DataList1_MotherNameLabel_0"[^>]*>([^<]+)</span>')
            college_code = _get(r'id="ContentPlaceHolder1_DataList1_CollegeCodeLabel_0"[^>]*>([^<]+)</span>')
            college_name = _get(r'id="ContentPlaceHolder1_DataList1_CollegeNameLabel_0"[^>]*>([^<]+)</span>')
            course_name = _get(r'id="ContentPlaceHolder1_DataList1_CourseLabel_0"[^>]*>([^<]+)</span>')
            remark = _get(r'id="ContentPlaceHolder1_DataList3_remarkLabel_0"[^>]*>([^<]*)</span>')
            status = "PASS" if not remark else "FAIL"
            
            # Helper to extract subjects from a specific HTML block
            def _extract_subjects(html_block):
                rows = re.findall(
                    r'<td align="center">([^<]+)</td><td align="left">([^<]+)</td>'
                    r'<td align="center">([^<]+)</td><td align="center">([^<]+)</td>'
                    r'<td align="center">([^<]+)</td><td align="center">([^<]+)</td>'
                    r'<td align="center">([^<]+)</td>',
                    html_block
                )
                subjects = []
                for row in rows:
                    code, subj_name, ese, ia, total, grade, credit = row
                    try: credit_f = float(credit)
                    except ValueError: credit_f = None
                    subjects.append({
                        "code": code.strip(), "name": subj_name.strip(),
                        "ese": ese.strip(), "ia": ia.strip(),
                        "total": total.strip(), "grade": grade.strip(), "credit": credit_f,
                    })
                return subjects

            # Isolate GridView1 (Theory) and GridView2 (Practical) blocks
            theory_block = ""
            prac_block = ""
            gv1_match = re.search(r'id="ContentPlaceHolder1_GridView1"[^>]*>(.*?)</table>', html, re.DOTALL)
            if gv1_match: theory_block = gv1_match.group(1)
            
            gv2_match = re.search(r'id="ContentPlaceHolder1_GridView2"[^>]*>(.*?)</table>', html, re.DOTALL)
            if gv2_match: prac_block = gv2_match.group(1)

            theory_subjects = _extract_subjects(theory_block)
            practical_subjects = _extract_subjects(prac_block)

            return {
                "redg_no": registration_no,
                "name": name.strip(),
                "father_name": father.strip() if father else None,
                "mother_name": mother.strip() if mother else None,
                "college_code": college_code.strip() if college_code else None,
                "college_name": college_name.strip().title() if college_name else None,
                "course": course_name.strip().title() if course_name else None,
                "semester": semester,
                "exam_held": exam_held,
                "sgpa": [sgpa_str] if sgpa_str else [],
                "cgpa": sgpa_str,
                "fail_any": status,
                "theorySubjects": theory_subjects,
                "practicalSubjects": practical_subjects,
                "raw_html": html,
            }
        except requests.RequestException as e:
            logger.warning(f"ASPX legacy request failed for {registration_no}: {e}")
        return None
