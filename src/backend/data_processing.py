
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from io import BytesIO

def clean_value(val: Any) -> Any:
    """Cleans numeric values from strings like 'NULL', 'NA'."""
    if val is None:
        return np.nan
    s_val = str(val).strip().upper()
    if s_val in ["NULL", "NA", "N/A", "-", "AB", "FAIL", "PASS"]:
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
        flat = {
            "Registration No": res.get("redg_no"),
            "Student Name": res.get("name"),
            "Father Name": res.get("father_name"),
            "College Code": res.get("college_code"),
            "College Name": res.get("college_name"),
            "Branch": res.get("course"),
            "Course": res.get("course"),
            "Semester": res.get("semester"),
            "Exam Held": res.get("exam_held"),
        }

        # SGPA handling
        sgpa_list = res.get("sgpa")
        current_sgpa = np.nan
        if isinstance(sgpa_list, list) and sgpa_list:
            for val in reversed(sgpa_list):
                c_val = clean_value(val)
                if not np.isnan(c_val):
                    current_sgpa = c_val
                    break

        flat["SGPA"] = current_sgpa

        # CGPA handling
        flat["CGPA"] = clean_value(res.get("cgpa"))
        if np.isnan(flat["CGPA"]) and not np.isnan(current_sgpa):
            flat["CGPA"] = current_sgpa

        # Status
        flat["Status"] = res.get("fail_any", "PROMOTED")

        # Process Subjects (Theory & Practical)
        theory = res.get("theorySubjects", [])
        practical = res.get("practicalSubjects", [])

        flat["Theory Failure Count"] = 0

        if theory:
            for i, subj in enumerate(theory):
                s_name = subj.get("name", f"Theory {i+1}")
                s_grade = subj.get("grade", "")
                flat[f"Sub_{s_name}_Grade"] = s_grade
                flat[f"Sub_{s_name}_Credit"] = subj.get("credit")
                flat[f"Sub_{s_name}_ESE"] = subj.get("ese")
                flat[f"Sub_{s_name}_IA"] = subj.get("ia")
                flat[f"Sub_{s_name}_Total"] = subj.get("total")
                if s_grade in ("F", "Ab"):
                    flat["Theory Failure Count"] += 1

        if practical:
            for i, subj in enumerate(practical):
                s_name = subj.get("name", f"Prac {i+1}")
                s_grade = subj.get("grade", "")
                flat[f"Sub_{s_name}_Grade"] = s_grade
                flat[f"Sub_{s_name}_IA"] = subj.get("ia")
                flat[f"Sub_{s_name}_ESE"] = subj.get("ese")
                flat[f"Sub_{s_name}_Total"] = subj.get("total")

        data.append(flat)

    df = pd.DataFrame(data)
    return df


def calculate_ranks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates University, College, and Class (Branch+College) ranks for students.
    All ranks based on SGPA descending (ties share same rank).
    """
    if df.empty:
        return df

    # We use SGPA for ranking as requested, fallback to CGPA if SGPA is missing
    rank_col = "SGPA" if "SGPA" in df.columns else "CGPA"

    # University Rank — global, across all fetched students
    df["University Rank"] = df[rank_col].rank(ascending=False, method="min").fillna(0).astype(int)

    # College Rank — within the same college
    if "College Code" in df.columns:
        df["College Rank"] = (
            df.groupby("College Code")[rank_col]
            .rank(ascending=False, method="min")
            .fillna(0).astype(int)
        )
    else:
        df["College Rank"] = df["University Rank"]

    # Branch Rank — within the same branch across all colleges
    if "Branch" in df.columns:
        df["Branch Rank"] = (
            df.groupby("Branch")[rank_col]
            .rank(ascending=False, method="min")
            .fillna(0).astype(int)
        )
    else:
        df["Branch Rank"] = df["University Rank"]

    # Class Rank — within the same branch at the same college
    group_cols = [c for c in ["College Code", "Branch"] if c in df.columns]
    if group_cols:
        df["Class Rank"] = (
            df.groupby(group_cols)[rank_col]
            .rank(ascending=False, method="min")
            .fillna(0).astype(int)
        )
    else:
        df["Class Rank"] = df["University Rank"]

    return df


def calculate_college_rankings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Groups students by college and computes performance metrics.
    Returns a college-level summary DataFrame ranked by Avg SGPA.
    """
    if df.empty or "College Code" not in df.columns:
        return pd.DataFrame()

    def pass_pct(grp):
        total = len(grp)
        if total == 0:
            return 0.0
        passed = grp[grp["Status"].astype(str).str.upper() == "PASS"].shape[0]
        return round(passed / total * 100, 1)

    agg = df.groupby("College Code").agg(
        College_Name=("College Name", "first"),
        Total_Students=("Registration No", "count"),
        Avg_SGPA=("SGPA", "mean"),
        Avg_CGPA=("CGPA", "mean"),
        Max_SGPA=("SGPA", "max"),
    ).reset_index()

    # Pass percentage per college
    pass_data = df.groupby("College Code").apply(pass_pct).reset_index()
    pass_data.columns = ["College Code", "Pass_Percentage"]
    agg = agg.merge(pass_data, on="College Code", how="left")

    # Rank by Avg SGPA primarily
    agg = agg.sort_values("Avg_SGPA", ascending=False).reset_index(drop=True)
    agg["College Rank"] = range(1, len(agg) + 1)

    # Round numeric columns
    agg["Avg_SGPA"] = agg["Avg_SGPA"].round(2)
    agg["Avg_CGPA"] = agg["Avg_CGPA"].round(2)
    agg["Max_SGPA"] = agg["Max_SGPA"].round(2)

    return agg.rename(columns={
        "College_Name": "College Name",
        "Total_Students": "Total Students",
        "Avg_SGPA": "Avg SGPA",
        "Avg_CGPA": "Avg CGPA",
        "Max_SGPA": "Best SGPA",
        "Pass_Percentage": "Pass %",
    })


def calculate_branch_rankings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Groups students by Branch and computes cross-college branch performance.
    Returns a branch-level summary DataFrame ranked by Avg SGPA.
    """
    if df.empty or "Branch" not in df.columns:
        return pd.DataFrame()

    def pass_pct(grp):
        total = len(grp)
        if total == 0:
            return 0.0
        passed = grp[grp["Status"].astype(str).str.upper() == "PASS"].shape[0]
        return round(passed / total * 100, 1)

    agg = df.groupby("Branch").agg(
        Total_Students=("Registration No", "count"),
        Avg_SGPA=("SGPA", "mean"),
        Avg_CGPA=("CGPA", "mean"),
        Max_SGPA=("SGPA", "max"),
        Colleges=("College Code", "nunique"),
    ).reset_index()

    pass_data = df.groupby("Branch").apply(pass_pct).reset_index()
    pass_data.columns = ["Branch", "Pass_Percentage"]
    agg = agg.merge(pass_data, on="Branch", how="left")

    agg = agg.sort_values("Avg_SGPA", ascending=False).reset_index(drop=True)
    agg["Branch Rank"] = range(1, len(agg) + 1)

    agg["Avg_SGPA"] = agg["Avg_SGPA"].round(2)
    agg["Avg_CGPA"] = agg["Avg_CGPA"].round(2)
    agg["Max_SGPA"] = agg["Max_SGPA"].round(2)

    return agg.rename(columns={
        "Total_Students": "Total Students",
        "Avg_SGPA": "Avg SGPA",
        "Avg_CGPA": "Avg CGPA",
        "Max_SGPA": "Best SGPA",
        "Pass_Percentage": "Pass %",
        "Colleges": "Colleges Represented",
    })


def get_top_students(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Returns top N students university-wide, sorted by SGPA then CGPA."""
    if df.empty:
        return pd.DataFrame()
    cols = ["University Rank", "Student Name", "Registration No", "College Name", "Branch", "CGPA", "SGPA", "Status"]
    available = [c for c in cols if c in df.columns]
    return df.nsmallest(n, "University Rank")[available]


def build_excel_report(df: pd.DataFrame, college_rankings: pd.DataFrame, branch_rankings: pd.DataFrame) -> bytes:
    """Builds a multi-sheet Excel report and returns it as bytes."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: All Student Results
        export_cols = [c for c in [
            "University Rank", "College Rank", "Branch Rank", "Class Rank",
            "Student Name", "Registration No", "Father Name",
            "College Name", "Branch", "Semester", "Exam Held",
            "SGPA", "CGPA", "Status"
        ] if c in df.columns]
        df[export_cols].sort_values("University Rank").to_excel(writer, sheet_name="Student Results", index=False)

        # Sheet 2: College Rankings
        if not college_rankings.empty:
            college_rankings.to_excel(writer, sheet_name="College Rankings", index=False)

        # Sheet 3: Branch Rankings
        if not branch_rankings.empty:
            branch_rankings.to_excel(writer, sheet_name="Branch Rankings", index=False)

        # Sheet 4: Top 10 Students
        top10 = get_top_students(df, 10)
        if not top10.empty:
            top10.to_excel(writer, sheet_name="Top 10 Students", index=False)

    return output.getvalue()


def analyze_batch_performance(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Returns high-level stats for the batch, including rankings and college/branch comparisons.
    """
    if df.empty:
        return {}

    # Calculate student-level ranks
    df = calculate_ranks(df)

    total = len(df)

    passed = 0
    if "Status" in df.columns and df["Status"].notna().any():
        passed = df[df["Status"].astype(str).str.upper() == "PASS"].shape[0]

    failed = total - passed

    avg_sgpa = df["SGPA"].mean() if "SGPA" in df.columns else 0
    avg_cgpa = df["CGPA"].mean() if "CGPA" in df.columns else 0

    # College & Branch level analytics
    college_rankings = calculate_college_rankings(df)
    branch_rankings = calculate_branch_rankings(df)

    return {
        "total_students": total,
        "passed": passed,
        "failed": failed,
        "pass_percentage": (passed / total) * 100 if total > 0 else 0,
        "avg_sgpa": avg_sgpa,
        "avg_cgpa": avg_cgpa,
        "toppers": df.nsmallest(5, "University Rank")[
            [c for c in ["Student Name", "SGPA", "CGPA", "Registration No", "University Rank", "College Name", "Branch"] if c in df.columns]
        ].to_dict("records"),
        "df_with_ranks": df,
        "college_rankings": college_rankings,
        "branch_rankings": branch_rankings,
    }
