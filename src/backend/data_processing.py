
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

def clean_value(val: Any) -> Any:
    """Cleans numeric values from strings like 'NULL', 'NA'."""
    if val is None:
        return np.nan
    s_val = str(val).strip().upper()
    if s_val in ["NULL", "NA", "N/A", "-", "AB", "FAIL", "PASS"]: # 'PASS'/'FAIL' might be status not grade
        return np.nan
    try:
        return float(s_val)
    except ValueError:
        return np.nan

def process_results_to_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Transforms list of API result dicts into a pandas DataFrame.
    """
    data = []

    for res in results:
        # Extract basic info
        flat = {
            "Registration No": res.get("redg_no"),
            "Student Name": res.get("name"),
            "Father Name": res.get("father_name"),
            "College Code": res.get("college_code"),
            "College Name": res.get("college_name"),
            "Course": res.get("course"),
            "Semester": res.get("semester"), # e.g. "VII"
            "Exam Held": res.get("exam_held"),
        }

        # SGPA handling
        sgpa_list = res.get("sgpa")
        current_sgpa = np.nan
        if isinstance(sgpa_list, list) and sgpa_list:
             # Get the last non-null value
             for val in reversed(sgpa_list):
                 c_val = clean_value(val)
                 if not np.isnan(c_val):
                     current_sgpa = c_val
                     break
        
        flat["SGPA"] = current_sgpa
        
        # CGPA handling
        flat["CGPA"] = clean_value(res.get("cgpa"))
        if np.isnan(flat["CGPA"]) and not np.isnan(current_sgpa):
             # Fallback if CGPA is missing (often happens in 1st sem)
             flat["CGPA"] = current_sgpa

        # Status
        flat["Status"] = res.get("fail_any", "PROMOTED") # Default to promoted/pass if not specified? 
        # Actually API returns "PASS" or "FAIL" usually in fail_any or separate field?
        # Reference says fail_any.

        # Process Subjects (Theory & Practical)
        theory = res.get("theorySubjects", [])
        practical = res.get("practicalSubjects", [])
        
        flat["Theory Failure Count"] = 0
        
        all_subjects = []
        if theory:
            for i, subj in enumerate(theory):
                s_name = subj.get("name", f"Theory {i+1}")
                s_grade = subj.get("grade", "")
                flat[f"Sub_{s_name}_Grade"] = s_grade
                flat[f"Sub_{s_name}_Credit"] = subj.get("credit")
                flat[f"Sub_{s_name}_ESE"] = subj.get("ese")
                flat[f"Sub_{s_name}_IA"] = subj.get("ia")
                flat[f"Sub_{s_name}_Total"] = subj.get("total")
                
                if s_grade == "F" or s_grade == "Ab":
                    flat["Theory Failure Count"] += 1
                
        if practical:
             for i, subj in enumerate(practical):
                s_name = subj.get("name", f"Prac {i+1}")
                s_grade = subj.get("grade", "")
                flat[f"Sub_{s_name}_Grade"] = s_grade
                flat[f"Sub_{s_name}_IA"] = subj.get("ia") # Lab usually has IA
                flat[f"Sub_{s_name}_ESE"] = subj.get("ese") # Lab usually has ESE
                flat[f"Sub_{s_name}_Total"] = subj.get("total")

        data.append(flat)

    df = pd.DataFrame(data)
    return df

def analyze_batch_performance(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns high-level stats for the batch.
    """
    if df.empty:
        return {}

    total = len(df)
    passed = df[df["Status"] == "PASS"].shape[0] if "Status" in df.columns else 0
    # Sometimes status is "PASS" or "FAIL" or "PROMOTED"
    # Let's infer pass based on F grades or Status column
    
    # If Status column exists and has values
    if "Status" in df.columns and df["Status"].notna().any():
        passed = df[df["Status"].astype(str).str.upper() == "PASS"].shape[0]
    
    failed = total - passed
    
    avg_sgpa = df["SGPA"].mean()
    avg_cgpa = df["CGPA"].mean()

    return {
        "total_students": total,
        "passed": passed,
        "failed": failed,
        "pass_percentage": (passed / total) * 100 if total > 0 else 0,
        "avg_sgpa": avg_sgpa,
        "avg_cgpa": avg_cgpa,
        "toppers": df.nlargest(3, "SGPA")[["Student Name", "SGPA", "Registration No"]].to_dict('records')
    }
