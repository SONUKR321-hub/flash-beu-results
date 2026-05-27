
import streamlit as st
import pandas as pd
import logging
logger = logging.getLogger(__name__)
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import time
from io import BytesIO

import importlib

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Force reload backend modules to clear Streamlit's cache
if 'backend.api_client' in sys.modules:
    importlib.reload(sys.modules['backend.api_client'])
if 'backend.data_processing' in sys.modules:
    importlib.reload(sys.modules['backend.data_processing'])
if 'backend.constants' in sys.modules:
    importlib.reload(sys.modules['backend.constants'])

from backend.api_client import BEUApiClient
from backend.data_processing import (
    process_results_to_dataframe,
    analyze_batch_performance,
    build_excel_report,
    get_top_students,
)
from backend.constants import (
    BRANCH_CODES, COLLEGE_CODES, COLLEGE_LOCATIONS,
    SEMESTERS, SEMESTER_MAPPING, BRANCH_SHORT_NAMES,
)


# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BEU Insights Master",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load CSS ──────────────────────────────────────────────────────────────────
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), 'src/frontend/styles.css')
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css()

# ── Session State ─────────────────────────────────────────────────────────────
for key in ['results_df', 'batch_stats', 'last_refresh_time', 'quick_search_reg', 'quick_search_sem', 'quick_search_exam', 'show_full_analytics']:
    if key not in st.session_state:
        st.session_state[key] = None

# ── Helper: Parse Registration Number ──────────────────────────────────────────
def parse_registration_no(reg_no: str):
    reg_no = reg_no.strip()
    if len(reg_no) != 11 or not reg_no.isdigit():
        return None
    return {
        "batch_year": int(reg_no[:2]),
        "branch_code": reg_no[2:5],
        "college_code": reg_no[5:8],
        "roll": reg_no[8:]
    }

# ── Helper: Fetch B.Tech Exams dynamically from sem-get ───────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_btech_exams():
    try:
        client = BEUApiClient()
        resp = client.session.get("https://beu-bih.ac.in/backend/v1/result/sem-get", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for course in data:
                if course.get("courseid") == 3:  # courseid 3 represents B.Tech
                    return course.get("exams", [])
    except Exception as e:
        logger.error(f"Error fetching B.Tech exams: {e}")
    return []

def get_exams_for_batch(batch_year: int):
    exams = fetch_btech_exams()
    matching = []
    year_str = str(2000 + batch_year)
    for e in exams:
        session = str(e.get("session", ""))
        if year_str in session:
            matching.append(e)
    # Sort by semId descending so latest exams are first
    matching.sort(key=lambda x: x.get("semId", 1), reverse=True)
    return matching


# ── Helper: Stat Card HTML ────────────────────────────────────────────────────
def stat_card(label, value, bg="rgba(255,255,255,0.12)"):
    return f"""
    <div style="background:{bg};padding:12px 20px;border-radius:10px;min-width:110px;text-align:center;">
        <p style="margin:0;font-size:0.75rem;opacity:0.8;text-transform:uppercase;letter-spacing:.05em;">{label}</p>
        <h3 style="margin:4px 0 0;color:white;font-size:1.3rem;">{value}</h3>
    </div>"""

# ── Helper: Fetch Semester SGPA with cache ─────────────────────────────────────
@st.cache_data(show_spinner=False)
def _fetch_sem_sgpa(reg_no: str, sem: str):
    # Mapping for semester probes
    SEM_PROBES = {
        "I":   ("I",   23, "ASPX_2023_SEM1"),
        "II":  ("II",  23, "ASPX_2023_SEM2"),
        "III": ("III", 23, "July/2025"),
        "IV":  ("IV",  23, "December/2025"),
    }
    if sem not in SEM_PROBES:
        return None
    s_roman, batch, exam = SEM_PROBES[sem]
    try:
        r = BEUApiClient().fetch_result(reg_no, s_roman, batch, exam)
        if r:
            sgpa_raw = r.get("sgpa")
            if isinstance(sgpa_raw, list) and sgpa_raw:
                for v in reversed(sgpa_raw):
                    try: return float(v)
                    except: pass
            elif sgpa_raw:
                try: return float(sgpa_raw)
                except: pass
    except Exception as e:
        logger.error(f"Error fetching sem SGPA: {e}")
    return None

def render_student_scorecard(student, df_filtered):
    status_color = "#10b981" if str(student.get("Status", "")).upper() == "PASS" else "#f87171"

    cards_html = "".join([
        stat_card("SGPA", f"{student.get('SGPA', 'N/A'):.2f}" if pd.notna(student.get('SGPA')) else "N/A"),
        stat_card("CGPA", f"{student.get('CGPA', 'N/A'):.2f}" if pd.notna(student.get('CGPA')) else "N/A"),
        stat_card("Class Rank", f"#{student.get('Class Rank', 'N/A')}"),
        stat_card("College Rank", f"#{student.get('College Rank', 'N/A')}"),
        stat_card("Branch Rank", f"#{student.get('Branch Rank', 'N/A')}"),
        stat_card("Uni Rank", f"#{student.get('University Rank', 'N/A')}"),
        stat_card("Status", str(student.get('Status', 'N/A')), bg=status_color + "44"),
    ])

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e3a8a,#3b82f6);
        padding:28px 32px;border-radius:16px;color:white;
        margin-bottom:24px;box-shadow:0 6px 24px rgba(30,58,138,.4);">
        <h2 style="margin:0;color:white;">{student['Student Name']}</h2>
        <p style="margin:4px 0 0;opacity:0.85;font-size:0.9rem;">
            REG: {student['Registration No']} &nbsp;|&nbsp;
            Father: {student.get('Father Name','N/A')} &nbsp;|&nbsp;
            {student.get('College Name','')}</p>
        <p style="margin:2px 0 16px;opacity:0.75;font-size:0.85rem;">
            Branch: {student.get('Branch','')} &nbsp;|&nbsp;
            Semester: {student.get('Semester','')} &nbsp;|&nbsp;
            Exam: {student.get('Exam Held','')}</p>
        <div style="display:flex;flex-wrap:wrap;gap:12px;">{cards_html}</div>
    </div>""", unsafe_allow_html=True)

    # ── Official BEU Marksheet (PDF-style) ───────────────────────────
    st.markdown("#### 📄 Official Marksheet")
    
    reg_no_str = str(student.get('Registration No', ''))
    batch = int(reg_no_str[:2]) if len(reg_no_str) >= 2 and reg_no_str[:2].isdigit() else 23
    r_marksheet = BEUApiClient().fetch_result(reg_no_str, student.get('Semester', 'I'), batch, str(student.get('Exam Held', '')))
    
    subject_grades = [c for c in df_filtered.columns if c.startswith("Sub_") and c.endswith("_Grade")]
    
    if r_marksheet and r_marksheet.get('raw_html'):
        target_url = "https://results.beup.ac.in/"
        beu_html = r_marksheet['raw_html'].replace('<head>', f'<head><base href="{target_url}">')
        print_btn = '<div style="text-align:center;padding:20px;background:#fff;"><button onclick="window.print()" style="padding:10px 20px;font-size:16px;cursor:pointer;background:#000;color:#fff;border-radius:4px;font-weight:bold;">🖨️ Print Marksheet</button></div>'
        beu_html = beu_html.replace('</form>', f'{print_btn}</form>')
        if print_btn not in beu_html:
            beu_html = beu_html.replace('</body>', f'{print_btn}</body>')
        st.components.v1.html(beu_html, height=1000, scrolling=True)
    elif subject_grades:
        subj_data = []
        for col in subject_grades:
            s_base = col.replace("_Grade", "")
            s_name = s_base.replace("Sub_", "")
            s_grade = student.get(col)
            s_ia = student.get(f"{s_base}_IA")
            s_ese = student.get(f"{s_base}_ESE")
            s_total = student.get(f"{s_base}_Total")
            s_credit = student.get(f"{s_base}_Credit")
            if pd.notna(s_grade) and s_grade != "":
                subj_data.append({
                    "name": s_name,
                    "ese": s_ese if pd.notna(s_ese) else "-",
                    "ia": s_ia if pd.notna(s_ia) else "-",
                    "total": s_total if pd.notna(s_total) else "-",
                    "grade": str(s_grade).strip(),
                    "credit": s_credit if pd.notna(s_credit) else "-",
                })

        if subj_data:
            def grade_bg(g):
                g = str(g).strip().upper().rstrip()
                if g in ("O", "A+", "A"): return "#dcfce7", "#166534"
                if g in ("B+", "B"): return "#dbeafe", "#1e40af"
                if g in ("C", "D"): return "#fef9c3", "#854d0e"
                if g in ("F", "AB"): return "#fee2e2", "#991b1b"
                return "#f3f4f6", "#374151"

            rows_html = ""
            for i, s in enumerate(subj_data):
                gbg, gfg = grade_bg(s['grade'])
                bg = "#fafafa" if i % 2 == 0 else "#fff"
                rows_html += f"""<tr style="background:{bg};">
<td style="padding:7px 10px;border:1px solid #999;font-size:13px;">{s['name']}</td>
<td style="padding:7px 10px;border:1px solid #999;text-align:center;font-size:13px;">{s['ese']}</td>
<td style="padding:7px 10px;border:1px solid #999;text-align:center;font-size:13px;">{s['ia']}</td>
<td style="padding:7px 10px;border:1px solid #999;text-align:center;font-weight:700;font-size:13px;">{s['total']}</td>
<td style="padding:7px 10px;border:1px solid #999;text-align:center;font-weight:700;font-size:13px;background:{gbg};color:{gfg};">{s['grade']}</td>
<td style="padding:7px 10px;border:1px solid #999;text-align:center;font-size:13px;">{s['credit']}</td>
</tr>"""

            sgpa_val = f"{student.get('SGPA'):.2f}" if pd.notna(student.get('SGPA')) else "N/A"
            cgpa_val = f"{student.get('CGPA'):.2f}" if pd.notna(student.get('CGPA')) else "N/A"
            status_val = str(student.get('Status', '')).upper()
            exam_held  = student.get('Exam Held', 'N/A')
            sem_val    = student.get('Semester', 'N/A')
            college    = student.get('College Name', 'N/A')
            branch     = student.get('Branch', 'N/A')
            father     = student.get('Father Name', 'N/A')
            reg_no     = student.get('Registration No', 'N/A')
            name_val   = student.get('Student Name', 'N/A')

            sem_order = ["I","II","III","IV","V","VI","VII","VIII"]
            current_sem_idx = sem_order.index(sem_val) if sem_val in sem_order else -1
            sem_sgpas = {}
            sgpa_list = r_marksheet.get('sgpa') if r_marksheet else None

            if isinstance(sgpa_list, list) and any(x is not None for x in sgpa_list):
                for i, s in enumerate(sem_order):
                    if i < len(sgpa_list) and sgpa_list[i] is not None:
                        try: sem_sgpas[s] = float(sgpa_list[i])
                        except: sem_sgpas[s] = None
                    else:
                        sem_sgpas[s] = None
            else:
                for s in sem_order[:current_sem_idx]:
                    sem_sgpas[s] = _fetch_sem_sgpa(reg_no, s)
                sem_sgpas[sem_val] = student.get('SGPA')

            filled = [v for v in sem_sgpas.values() if v is not None and not (isinstance(v, float) and pd.isna(v))]
            running_cgpa = round(sum(filled) / len(filled), 2) if filled else None
            cgpa_cells = ""
            for s in sem_order:
                v = sem_sgpas.get(s)
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    cgpa_cells += '<td style="border:1px solid #444;padding:6px 8px;text-align:center;font-size:12px;color:#666;">-</td>'
                else:
                    cgpa_cells += f'<td style="border:1px solid #444;padding:6px 8px;text-align:center;font-size:12px;">{v:.1f}</td>'
            rc = f"{running_cgpa:.1f}" if running_cgpa else "-"
            cgpa_cells += f'<td style="border:1px solid #444;padding:6px 8px;text-align:center;font-size:12px;">{rc}</td>'
            cgpa_val = rc

            remark_text = "" if status_val == "PASS" else "BACK"
            remark_color = "#e11d48" if status_val != "PASS" else "#444"

            mother = student.get('Mother Name', 'N/A')
            if pd.isna(mother): mother = ""

            theory_rows_html = ""
            prac_rows_html = ""
            for i, s in enumerate(subj_data):
                bg = "#fff"
                is_prac = ("Lab" in s['name'] or "Practical" in s['name'] or "Sessional" in s['name'] or s['name'].endswith(" P"))
                scode = s.get('code', '-')
                
                c_val = s['credit']
                if isinstance(c_val, (int, float)) and pd.notna(c_val):
                    c_str = f"{c_val:.0f}"
                elif isinstance(c_val, str) and c_val.replace('.', '', 1).isdigit():
                    c_str = f"{float(c_val):.0f}"
                else:
                    c_str = str(c_val)

                row_html = (
                    f'<tr align="left">\n'
                    f'<td align="center">{scode}</td>\n'
                    f'<td align="left">{s["name"].upper()}</td>\n'
                    f'<td align="center">{s["ese"]}</td>\n'
                    f'<td align="center">{s["ia"]}</td>\n'
                    f'<td align="center">{s["total"]}</td>\n'
                    f'<td align="center">{s["grade"].replace("+", " ")}</td>\n'
                    f'<td align="center">{c_str}</td>\n'
                    f'</tr>\n'
                )
                if is_prac:
                    prac_rows_html += row_html
                else:
                    theory_rows_html += row_html

            import base64
            import os
            logo_path = os.path.join(os.path.dirname(__file__), "images", "BEUP_ENlogo1.png")
            logo_b64 = ""
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    logo_b64 = base64.b64encode(f.read()).decode()

            sgpa_numeric = f"{student.get('SGPA', 0):.2f}"
            if pd.isna(student.get('SGPA')):
                sgpa_numeric = sgpa_val
            
            college_code_val = student.get('College Code', '')
            if pd.isna(college_code_val) or not college_code_val:
                college_code_val = ""
            else:
                college_code_val = f"{college_code_val} -"
            
            course_code_val = student.get('Course Code', '')
            if pd.isna(course_code_val) or not course_code_val:
                course_code_val = ""
            else:
                course_code_val = f"{course_code_val} -"

            marksheet_html = f"""<style>
#printarea {{ font-family: Arial, Tahoma, sans-serif; font-size: 13px; max-width: 900px; margin: 0 auto; background: #fff; color: #000; padding: 20px; }}
#printarea table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
#printarea th, #printarea td {{ border: 1px solid #000; padding: 10px; }}
#printarea td {{ text-align: center; }}
#printarea td.left-align {{ text-align: left; }}
#printarea th {{ text-align: center; font-weight: bold; background-color: #fff; }}
.info-table th, .info-table td {{ padding: 8px 10px; border: 1px solid #000; }}
.info-table td.label-col {{ width: 15%; font-weight: bold; text-align: left; }}
.info-table td.data-col {{ text-align: left; }}
@media print {{
  .stApp>header, .stSidebar, div[data-testid="stToolbar"], div[data-testid="stDecoration"], .stButton, footer {{ display: none !important; }}
  #printarea {{ border: none; width: 100%; max-width: none; padding: 0; }}
}}
</style>
<div id="printarea">
    <div style="display:flex;align-items:center;margin-bottom:20px;">
        <div style="flex:0 0 100px;">
            <img src="data:image/png;base64,{logo_b64}" width="90" />
        </div>
        <div style="flex:1;text-align:center;">
            <div style="font-size: 24px; font-weight: bold; text-transform: uppercase;">Bihar Engineering University, Patna</div>
            <div style="font-size: 16px; font-weight: bold; color: red; margin-top: 5px;">B.Tech. {sem_val}{"^{th}" if sem_val.isdigit() else ""} Semester Examination, {exam_held.split('/')[-1]}</div>
        </div>
        <div style="flex:0 0 100px;"></div>
    </div>
    
    <table class="info-table" style="margin-bottom: 0; border-bottom: none;">
        <tr>
            <td class="label-col">Semester:</td>
            <td class="data-col" style="width: 35%;">{sem_val}</td>
            <td class="label-col" style="width: 20%;">Examination(Month/Year):</td>
            <td class="data-col" style="width: 30%;">{exam_held.upper()}</td>
        </tr>
    </table>
    
    <table class="info-table">
        <tr>
            <td class="label-col" style="width: 15%;">Registration No:</td>
            <td class="data-col" colspan="3" style="font-weight: bold;">{reg_no}</td>
        </tr>
        <tr>
            <td class="label-col">Student Name:</td>
            <td class="data-col" colspan="3" style="font-weight: bold;">{name_val.upper()}</td>
        </tr>
        <tr>
            <td class="label-col">Father Name:</td>
            <td class="data-col" style="width: 35%;">{father.upper()}</td>
            <td class="label-col" style="width: 15%;">Mother Name:</td>
            <td class="data-col" style="width: 35%;">{mother.upper()}</td>
        </tr>
        <tr>
            <td class="label-col">College Name:</td>
            <td class="data-col" colspan="3">{college_code_val} {college.upper()}</td>
        </tr>
        <tr>
            <td class="label-col">Course Name:</td>
            <td class="data-col" colspan="3">{course_code_val} {branch.upper()}</td>
        </tr>
    </table>
    
    <table>
        <tr>
            <td colspan="7" style="font-weight: bold; text-align: center; padding: 12px; background: #fff;">THEORY</td>
        </tr>
        <tr>
            <th style="width: 10%;">Subject<br>Code</th>
            <th style="text-align: left;">Subject Name</th>
            <th style="width: 8%;">ESE</th>
            <th style="width: 8%;">IA</th>
            <th style="width: 8%;">Total</th>
            <th style="width: 8%;">Grade</th>
            <th style="width: 8%;">Credit</th>
        </tr>
        {theory_rows_html.replace('align="left"', 'class="left-align"').replace('align="center"', '')}
        
        {"" if not prac_rows_html else f'''
        <tr>
            <td colspan="7" style="font-weight: bold; text-align: center; padding: 12px; border-top: 2px solid #000; background: #fff;">PRACTICAL</td>
        </tr>
        <tr>
            <th style="width: 10%;">Subject<br>Code</th>
            <th style="text-align: left;">Subject Name</th>
            <th style="width: 8%;">ESE</th>
            <th style="width: 8%;">IA</th>
            <th style="width: 8%;">Total</th>
            <th style="width: 8%;">Grade</th>
            <th style="width: 8%;">Credit</th>
        </tr>
        {prac_rows_html.replace('align="left"', 'class="left-align"').replace('align="center"', '')}
        '''}
        
        <tr>
            <td colspan="7" style="text-align: right; font-weight: bold; padding: 12px; border-top: 2px solid #000;">SGPA : {sgpa_numeric}</td>
        </tr>
    </table>
    
    <table>
        <tr>
            <th colspan="10" style="padding: 12px; background: #fff;">SGPA / CGPA</th>
        </tr>
        <tr>
            <th style="width: 12%;">Semester</th>
            <th style="width: 8%;">I</th>
            <th style="width: 8%;">II</th>
            <th style="width: 8%;">III</th>
            <th style="width: 8%;">IV</th>
            <th style="width: 8%;">V</th>
            <th style="width: 8%;">VI</th>
            <th style="width: 8%;">VII</th>
            <th style="width: 8%;">VIII</th>
            <th style="width: 16%;">Cur. CGPA</th>
        </tr>
        <tr>
            <td style="font-weight: bold;">SGPA</td>
            {cgpa_cells.replace('<td style="border:1px solid #000;padding:6px 8px;text-align:center;font-size:12px;">', '<td>').replace('<td style="border:1px solid #000;padding:6px 8px;text-align:center;font-size:12px;color:#666;">-</td>', '<td>-</td>')}
        </tr>
    </table>
    
    <table class="info-table" style="margin-bottom: 20px;">
        <tr>
            <td class="label-col" style="width: 15%;">Remarks :</td>
            <td class="data-col" style="font-weight: bold;">{remark_text.upper()}</td>
        </tr>
    </table>
    
    <div style="display: flex; justify-content: space-between; margin-top: 30px;">
        <div><b>Publish Date: </b></div>
        <div style="text-align: center;">
            <br/><br/>
            <b>Controller of Examination</b>
        </div>
    </div>
    
    <div style="margin-top: 30px; font-size: 11px;">
        <b>NOTE:</b><br/>
        ESE: End Semester Exam | IA: Internal Assessment | SGPA: Semester Grade Point Average | CGPA: Cumulative Grade Point Average<br/>
        AB: Absent | NA: Not Applicable<br/>
        Grade: O &gt; A+ &gt; A &gt; B+ &gt; B &gt; C &gt; D &gt; F(Fail)
    </div>

    <div style="text-align:center;padding:20px;">
        <button onclick="window.print()" style="background:#000;color:#fff;border:none;padding:10px 24px;font-size:14px;cursor:pointer;border-radius:4px;font-weight:bold;">Print Result</button>
    </div>
</div>"""
            if hasattr(st, "html"):
                st.html(marksheet_html)
            else:
                st.markdown(marksheet_html, unsafe_allow_html=True)
        else:
            st.info("No subject grades found for this student.")
    else:
        st.warning("Subject details not available for this session.")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎓 Config Panel")
    st.caption("⚡ Version: **1.1.0 (Token Fix)**")

    if st.session_state.quick_search_reg is not None:
        st.markdown("---")
        st.success(f"🔍 Viewing: **{st.session_state.quick_search_reg}**")
        if st.button("⬅️ Search Another Student", key="sidebar_reset_search", use_container_width=True):
            st.session_state.results_df = None
            st.session_state.batch_stats = None
            st.session_state.quick_search_reg = None
            st.session_state.quick_search_sem = None
            st.session_state.quick_search_exam = None
            st.session_state.show_full_analytics = None
            st.rerun()
        st.markdown("---")

    st.markdown("### Batch Details")
    batch_year = st.number_input("Batch Year (e.g. 23 for 2023)", min_value=15, max_value=30, value=22)

    semester_num = st.selectbox(
        "Semester",
        options=list(SEMESTER_MAPPING.keys()),
        format_func=lambda x: f"{x} ({SEMESTERS[SEMESTER_MAPPING[x]]})",
        index=5,  # Default to 6th semester
    )
    semester_roman = SEMESTER_MAPPING[semester_num]

    st.markdown("### Institution")
    college_options = ["ALL"] + list(COLLEGE_CODES.keys())
    college_code = st.selectbox(
        "College",
        options=college_options,
        format_func=lambda x: "ALL 38 COLLEGES" if x == "ALL" else f"{x} - {COLLEGE_CODES.get(x, x)}",
        index=college_options.index("107"),
    )

    branch_code = st.selectbox(
        "Branch",
        options=list(BRANCH_CODES.keys()),
        format_func=lambda x: f"{x} - {BRANCH_CODES[x]}",
        index=list(BRANCH_CODES.keys()).index("101"),
    )

    st.markdown("### Range")
    col1, col2 = st.columns(2)
    with col1:
        start_reg = st.number_input("Start", value=1, min_value=1)
    with col2:
        end_reg = st.number_input("End", value=60, min_value=1)

    include_lateral = st.checkbox("Include LE Students?", value=False)

    st.markdown("---")
    st.markdown("### ⚙️ Advanced Settings")
    
    exam_override = st.selectbox(
        "Manual Exam Session Override (Optional)",
        ["Auto-Detect", "February/2026", "January/2026", "December/2025", "November/2025", "July/2025", "May/2025", "Dec/2024", "Sep/2024", "Aug/2024", "July/2024", "May/2024", "Dec/2023"],
        index=0
    )
    
    enable_auto_refresh = st.checkbox("🔄 Auto-Refresh Results", value=False)
    if enable_auto_refresh:
        refresh_interval = st.number_input("Refresh Interval (minutes)", min_value=1, max_value=30, value=5)
    else:
        refresh_interval = 5

    st.markdown("---")

    # ── Fetch Button ────────────────────────────────────────────────────────
    if st.button("🚀 Fetch Results", use_container_width=True, type="primary"):
        client = BEUApiClient()

        with st.spinner("Analyzing exam sessions and active institutions..."):
            detected_date = None
            probe_college = college_code if college_code != "ALL" else "107"
            
            # 1. Determine the exam session (date)
            if exam_override != "Auto-Detect":
                detected_date = exam_override
            else:
                dates = [
                    "February/2026", "January/2026", "December/2025", "November/2025", "July/2025", "May/2025",
                    "Dec/2024", "Sep/2024", "Aug/2024",
                    "July/2024", "May/2024", "Dec/2023",
                ]
                if semester_roman == "I" and batch_year == 23:
                    dates = ["ASPX_2023_SEM1"] + dates
                if semester_roman == "II" and batch_year == 23:
                    dates = ["ASPX_2023_SEM2"] + dates
                    
                my_bar = st.progress(0, text="Searching for correct exam session...")
                for idx, date in enumerate(dates):
                    st.toast(f"Probing session: {date}...", icon="🔍")
                    # Try probing a small range to see if there is any data for the probe college
                    probe_results = client.fetch_batch_results(
                        start_reg, start_reg + 2, branch_code, probe_college, batch_year, semester_roman, date, include_lateral
                    )
                    if probe_results:
                        detected_date = date
                        st.toast(f"Found data in {date}!", icon="✅")
                        my_bar.progress(100, text=f"Data found in {date}! Probing colleges...")
                        break
                    my_bar.progress(int((idx + 1) / len(dates) * 100), text=f"Checking {date}...")
                
                if 'my_bar' in locals():
                    my_bar.empty()

            if detected_date:
                # 2. Find active colleges offering this branch for the detected date
                all_colleges = list(COLLEGE_CODES.keys())
                st.toast("Finding active colleges offering this branch...", icon="🏫")
                active_colleges = client.find_active_colleges(
                    branch_code, batch_year, semester_roman, detected_date, all_colleges
                )
                
                if not active_colleges:
                    # Fallback to at least the probe college
                    active_colleges = [probe_college]
                
                st.toast(f"Found {len(active_colleges)} colleges offering this branch. Fetching all results in parallel...", icon="🚀")
                
                # Fetch all active colleges in parallel
                raw_results = client.fetch_batch_results(
                    start_reg, end_reg, branch_code, active_colleges,
                    batch_year, semester_roman, detected_date, include_lateral
                )
            else:
                raw_results = []

            if raw_results:
                df = process_results_to_dataframe(raw_results)
                # Keep full university-wide dataframe in session state for comparative rankings
                st.session_state.results_df = df
                st.session_state.batch_stats = analyze_batch_performance(df)
                
                fetched_count = len(df[df["College Code"].astype(str) == str(college_code)]) if college_code != "ALL" else len(df)
                st.success(f"✅ Fetched university-wide results! Loaded {fetched_count} records for your college (out of {len(df)} total university-wide records).")
            else:
                st.error("No results found in any recent exam session.")
                st.info(f"Tried: ASPX 2023 portal, February/2026, January/2026, December/2025, November/2025, July/2025, May/2025, Dec/2024, Sep/2024, Aug/2024, July/2024, May/2024, Dec/2023.")
                st.warning("**Tips:** Check batch year, semester, and branch code.")
                if batch_year == 24:
                    check_23 = client.fetch_batch_results(
                        start_reg, start_reg, branch_code, probe_college, 23, "I", "Dec/2023", include_lateral
                    )
                    if check_23:
                        st.success("✅ Found results for Batch 2023! Change Batch Year to **23**.")


# ── Main Header ───────────────────────────────────────────────────────────────
st.markdown("# 🎓 BEU Insights Master")
st.markdown(
    "<div style='text-align:center;color:#555;font-size:1.1rem;margin-top:0.2rem;font-weight:600;'>"
    "Bihar Engineering University · Advanced Analytics Platform</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='text-align:center;color:#888;font-size:0.85rem;margin-bottom:1rem;'>"
    "Designed & Built by <b>Kumar Sonu</b> from MIT Muzaffarpur</div>",
    unsafe_allow_html=True,
)

# Hero banner
st.markdown("""
<div style='height:140px;background:linear-gradient(135deg,#1e3a8a,#3b82f6,#06b6d4,#10b981);
border-radius:14px;margin:0 0 1.5rem;box-shadow:0 6px 24px rgba(30,58,138,.3);
display:flex;align-items:center;justify-content:center;'>
<span style='color:white;font-size:2rem;font-weight:700;letter-spacing:.05em;'>
🏛️ बिहार इंजीनियरिंग विश्वविद्यालय
</span></div>""", unsafe_allow_html=True)

# Check if we should render Quick Scorecard or Full Dashboard
if st.session_state.results_df is not None:
    df = st.session_state.results_df
    stats = st.session_state.batch_stats

    # Always use the rank-enriched df from stats
    df = stats.get('df_with_ranks', df)
    college_rankings = stats.get('college_rankings', pd.DataFrame())
    branch_rankings = stats.get('branch_rankings', pd.DataFrame())

    # Check if we are in the Quick Search mode
    if st.session_state.quick_search_reg is not None and not st.session_state.show_full_analytics:
        # 1. Quick Scorecard mode
        student_rows = df[df["Registration No"].astype(str).str.strip() == str(st.session_state.quick_search_reg).strip()]
        if not student_rows.empty:
            student = student_rows.iloc[0]
            
            # Show a beautiful banner for the Quick Scorecard
            st.markdown(f"### 🎖️ Quick Scorecard for **{student.get('Student Name', 'Student')}**")
            st.markdown(f"**College:** {student.get('College Name')} · **Branch:** {student.get('Branch')} · **Semester:** {student.get('Semester')}")
            
            st.markdown("---")
            
            # Action buttons
            c_act1, c_act2 = st.columns([1, 1])
            with c_act1:
                if st.button("📊 View Full Batch Analytics & Leaderboard", use_container_width=True, type="primary"):
                    st.session_state.show_full_analytics = True
                    st.rerun()
            with c_act2:
                if st.button("🔍 Check Another Registration Number", use_container_width=True):
                    # Reset search state
                    st.session_state.results_df = None
                    st.session_state.batch_stats = None
                    st.session_state.quick_search_reg = None
                    st.session_state.quick_search_sem = None
                    st.session_state.quick_search_exam = None
                    st.session_state.show_full_analytics = None
                    st.rerun()
            
            st.markdown("---")
            
            render_student_scorecard(student, df)
        else:
            st.error(f"Registration number {st.session_state.quick_search_reg} not found in the loaded dataset.")
            if st.button("⬅️ Go Back to Search"):
                st.session_state.results_df = None
                st.session_state.batch_stats = None
                st.session_state.quick_search_reg = None
                st.rerun()
    else:
        # 2. Full Analytics mode
        st.markdown(
            f"**{COLLEGE_CODES.get(college_code, 'Unknown College')}** · "
            f"Batch 20{batch_year} · {SEMESTERS.get(semester_roman, semester_roman)}"
        )
        
        # Show a button to return to scorecard if came from Quick Checker
        if st.session_state.quick_search_reg is not None:
            if st.button("⬅️ Back to My Scorecard & Ranks", type="secondary"):
                st.session_state.show_full_analytics = False
                st.rerun()
                
        # Filter dataset for UI displays if a specific college is selected
        if college_code != "ALL":
            df_filtered = df[df["College Code"].astype(str) == str(college_code)].reset_index(drop=True)
        else:
            df_filtered = df

        # Compute overview metrics specifically for the filtered subset
        total_students_f = len(df_filtered)
        passed_f = df_filtered[df_filtered["Status"].astype(str).str.upper() == "PASS"].shape[0] if not df_filtered.empty else 0
        failed_f = total_students_f - passed_f
        pass_rate_f = (passed_f / total_students_f) * 100 if total_students_f > 0 else 0.0
        avg_sgpa_f = df_filtered["SGPA"].mean() if not df_filtered.empty else 0.0
        avg_cgpa_f = df_filtered["CGPA"].mean() if not df_filtered.empty else 0.0

        # ── Overview Metrics ──────────────────────────────────────────────────────
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("👥 Total Students", total_students_f)
        m2.metric("✅ Pass Rate", f"{pass_rate_f:.1f}%")
        m3.metric("📈 Avg SGPA", f"{avg_sgpa_f:.2f}")
        m4.metric("🏅 Avg CGPA", f"{avg_cgpa_f:.2f}")
        m5.metric("❌ Failed", failed_f)

        st.markdown("---")

        # ── Tabs ──────────────────────────────────────────────────────────────────
        (tab_analytics, tab_leaderboard, tab_rankings,
         tab_college, tab_branch, tab_search,
         tab_data, tab_export) = st.tabs([
            "📊 Analytics", "🏆 Leaderboard", "🎖️ Rankings",
            "🏫 College Rankings", "🌿 Branch Rankings",
            "🔍 Search Student", "📝 All Data", "📤 Export",
        ])

        # ── Tab 1: Analytics ─────────────────────────────────────────────────────
        with tab_analytics:
            c1, c2 = st.columns([2, 1])
            with c1:
                fig_sgpa = px.histogram(
                    df_filtered, x="SGPA", nbins=20,
                    title="SGPA Distribution",
                    color_discrete_sequence=["#3b82f6"],
                    template="plotly_white",
                )
                fig_sgpa.update_layout(bargap=0.05)
                st.plotly_chart(fig_sgpa, use_container_width=True)

            with c2:
                status_counts = df_filtered["Status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Count"]
                fig_pie = px.pie(
                    status_counts, values="Count", names="Status",
                    title="Pass vs Fail",
                    color_discrete_sequence=["#10b981", "#f87171"],
                    hole=0.45,
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            fig_scatter = px.scatter(
                df_filtered, x="CGPA", y="SGPA", color="Status",
                hover_data=["Student Name", "Registration No"],
                title="Correlation: CGPA vs SGPA",
                template="plotly_white",
                color_discrete_map={"PASS": "#10b981", "FAIL": "#f87171"},
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

            # CGPA distribution
            fig_cgpa = px.histogram(
                df_filtered, x="CGPA", nbins=20,
                title="CGPA Distribution",
                color_discrete_sequence=["#8b5cf6"],
                template="plotly_white",
            )
            st.plotly_chart(fig_cgpa, use_container_width=True)

        # ── Tab 2: Leaderboard ────────────────────────────────────────────────────
        with tab_leaderboard:
            st.markdown("### 🌟 Top 3 Podium")
            toppers = df_filtered.nsmallest(3, "University Rank").to_dict("records")
            medals = ["🥇", "🥈", "🥉"]
            colors = ["#f59e0b", "#9ca3af", "#b45309"]
            cols = st.columns(3)
            for i, topper in enumerate(toppers):
                with cols[i]:
                    st.markdown(f"""
                    <div style="background:white;padding:24px 20px;border-radius:14px;
                        border:2px solid {colors[i]};text-align:center;
                        box-shadow:0 4px 16px rgba(0,0,0,0.1);">
                        <div style="font-size:2.5rem;">{medals[i]}</div>
                        <h3 style="margin:8px 0 4px;color:#1e293b;">{topper['Student Name']}</h3>
                        <p style="margin:0;color:#64748b;font-size:0.85rem;">{topper.get('Registration No','')}</p>
                        <p style="margin:4px 0 0;color:#64748b;font-size:0.8rem;">{topper.get('College Name','')}</p>
                        <div style="display:flex;justify-content:center;gap:16px;margin-top:12px;">
                            <div><span style="font-size:0.75rem;color:#94a3b8;">CGPA</span><br>
                            <b style="font-size:1.2rem;color:{colors[i]};">{topper.get('CGPA','N/A')}</b></div>
                            <div><span style="font-size:0.75rem;color:#94a3b8;">SGPA</span><br>
                            <b style="font-size:1.2rem;color:{colors[i]};">{topper.get('SGPA','N/A')}</b></div>
                        </div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 🏅 Top 10 Students")
            top10 = get_top_students(df_filtered, 10)
            if not top10.empty:
                st.dataframe(top10, use_container_width=True, hide_index=True)

        # ── Tab 3: Rankings ───────────────────────────────────────────────────────
        with tab_rankings:
            st.markdown("### 🎖️ Student Rankings")
            st.caption("Rankings are computed by SGPA (descending). Ties share the same rank.")

            r1, r2, r3 = st.columns(3)
            rank_cols = ["University Rank", "College Rank", "Class Rank"]
            for col, label, icon in zip(
                [r1, r2, r3],
                ["University Rank #1", "College Rank #1", "Class Rank #1"],
                ["🌐", "🏫", "📚"],
            ):
                rank_key = [k for k in rank_cols if label.split()[0] in k][0]
                top_row = df_filtered[df_filtered[rank_key] == df_filtered[rank_key].min()]
                name = top_row["Student Name"].iloc[0] if not top_row.empty else "N/A"
                col.metric(f"{icon} {label.replace(' #1','')}", name)

            display_cols = [c for c in [
                "University Rank", "Branch Rank", "College Rank", "Class Rank",
                "Student Name", "Registration No", "College Name", "Branch",
                "CGPA", "SGPA", "Status",
            ] if c in df_filtered.columns]

            st.dataframe(
                df_filtered[display_cols].sort_values("University Rank"),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "University Rank": st.column_config.NumberColumn("🌐 Uni Rank", format="%d"),
                    "Branch Rank": st.column_config.NumberColumn("🌿 Branch Rank", format="%d"),
                    "College Rank": st.column_config.NumberColumn("🏫 College Rank", format="%d"),
                    "Class Rank": st.column_config.NumberColumn("📚 Class Rank", format="%d"),
                    "CGPA": st.column_config.NumberColumn("CGPA", format="%.2f"),
                    "SGPA": st.column_config.NumberColumn("SGPA", format="%.2f"),
                },
            )


        # ── Tab 4: College Rankings ───────────────────────────────────────────────
        with tab_college:
            st.markdown("### 🏫 College Performance Rankings")
            st.caption(
                "Colleges ranked by average CGPA. "
                "Data scope: currently fetched students only. "
                "For full rankings, fetch multiple colleges."
            )
            if not college_rankings.empty:
                cr = college_rankings.copy()

                # Bar chart
                fig_cr = px.bar(
                    cr.head(20), x="Avg CGPA", y="College Name",
                    orientation="h", color="Avg CGPA",
                    color_continuous_scale="blues",
                    title="College Rankings by Avg CGPA",
                    template="plotly_white",
                    text="Avg CGPA",
                )
                fig_cr.update_layout(yaxis={"autorange": "reversed"}, height=max(400, len(cr) * 35))
                fig_cr.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                st.plotly_chart(fig_cr, use_container_width=True)

                # Table
                st.dataframe(
                    cr,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "College Rank": st.column_config.NumberColumn("🏆 Rank", format="%d"),
                        "Avg CGPA": st.column_config.NumberColumn(format="%.2f"),
                        "Avg SGPA": st.column_config.NumberColumn(format="%.2f"),
                        "Best CGPA": st.column_config.NumberColumn(format="%.2f"),
                        "Pass %": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
            else:
                st.info("Fetch students from multiple colleges to see cross-college rankings. Currently only one college is loaded.")

        # ── Tab 5: Branch Rankings ────────────────────────────────────────────────
        with tab_branch:
            st.markdown("### 🌿 Branch-Wise Rankings")
            st.caption("Branch rankings by average CGPA across all fetched students.")
            if not branch_rankings.empty:
                br = branch_rankings.copy()

                fig_br = px.bar(
                    br, x="Branch", y="Avg CGPA",
                    color="Avg CGPA",
                    color_continuous_scale="teal",
                    title="Branch Rankings by Avg CGPA",
                    template="plotly_white",
                    text="Avg CGPA",
                )
                fig_br.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                fig_br.update_layout(xaxis_tickangle=-30)
                st.plotly_chart(fig_br, use_container_width=True)

                # Pass % chart
                fig_pass = px.bar(
                    br, x="Branch", y="Pass %",
                    color="Pass %",
                    color_continuous_scale="greens",
                    title="Branch-Wise Pass Percentage",
                    template="plotly_white",
                    text="Pass %",
                )
                fig_pass.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                st.plotly_chart(fig_pass, use_container_width=True)

                st.dataframe(
                    br,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Branch Rank": st.column_config.NumberColumn("🏆 Rank", format="%d"),
                        "Avg CGPA": st.column_config.NumberColumn(format="%.2f"),
                        "Avg SGPA": st.column_config.NumberColumn(format="%.2f"),
                        "Best CGPA": st.column_config.NumberColumn(format="%.2f"),
                        "Pass %": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )
            else:
                st.info("No branch data available yet.")

        # ── Tab 6: Search Student ─────────────────────────────────────────────────
        with tab_search:
            st.markdown("### 🔍 Student Search")
            search_query = st.selectbox(
                "Search by Registration No / Name",
                options=df_filtered["Registration No"].tolist(),
                format_func=lambda x: f"{x} — {df_filtered[df_filtered['Registration No'].astype(str).str.strip() == str(x).strip()]['Student Name'].values[0]}",
            )
            if search_query:
                student = df_filtered[df_filtered["Registration No"].astype(str).str.strip() == str(search_query).strip()].iloc[0]
                render_student_scorecard(student, df_filtered)


        # ── Tab 7: All Data ───────────────────────────────────────────────────────

        with tab_data:
            st.markdown("#### Filter & Explore Data")
            f1, f2, f3 = st.columns(3)
            with f1:
                status_filter = st.multiselect(
                    "Filter by Status",
                    options=df_filtered["Status"].unique().tolist(),
                    default=df_filtered["Status"].unique().tolist(),
                    key="status_filter_data",
                )
            with f2:
                sort_by = st.selectbox("Sort By", ["University Rank", "CGPA", "SGPA", "Student Name", "Registration No"], key="sort_data")
            with f3:
                if "Branch" in df_filtered.columns:
                    branch_filter = st.multiselect(
                        "Filter by Branch",
                        options=df_filtered["Branch"].dropna().unique().tolist(),
                        default=df_filtered["Branch"].dropna().unique().tolist(),
                        key="branch_filter_data",
                    )
                else:
                    branch_filter = []

            filtered = df_filtered[df_filtered["Status"].isin(status_filter)]
            if branch_filter and "Branch" in filtered.columns:
                filtered = filtered[filtered["Branch"].isin(branch_filter)]

            if sort_by == "University Rank":
                filtered = filtered.sort_values("University Rank")
            elif sort_by in ("CGPA", "SGPA"):
                filtered = filtered.sort_values(sort_by, ascending=False)
            elif sort_by == "Student Name":
                filtered = filtered.sort_values("Student Name")

            st.dataframe(filtered, use_container_width=True, height=600)

        # ── Tab 8: Export ─────────────────────────────────────────────────────────
        with tab_export:
            st.markdown("### 📤 Download Data")
            st.markdown("Download the complete student results with rankings in your preferred format.")

            # Prepare export columns
            export_cols = [c for c in [
                "University Rank", "Branch Rank", "College Rank", "Class Rank",
                "Student Name", "Registration No", "Father Name",
                "College Name", "Branch", "Semester", "Exam Held",
                "SGPA", "CGPA", "Status",
            ] if c in df_filtered.columns]

            export_df = df_filtered[export_cols].sort_values("University Rank") if "University Rank" in df_filtered.columns else df_filtered[export_cols]

            e1, e2 = st.columns(2)

            with e1:
                st.markdown("#### 📄 CSV Download")
                st.markdown("Basic format. Opens in any spreadsheet.")
                csv_data = export_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Download Student Results (CSV)",
                    csv_data,
                    f"beu_results_batch{batch_year}_sem{semester_num}.csv",
                    "text/csv",
                    key="dl-csv",
                    use_container_width=True,
                )

                if not college_rankings.empty:
                    cr_csv = college_rankings.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "🏫 Download College Rankings (CSV)",
                        cr_csv,
                        "beu_college_rankings.csv",
                        "text/csv",
                        key="dl-college-csv",
                        use_container_width=True,
                    )

                if not branch_rankings.empty:
                    br_csv = branch_rankings.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "🌿 Download Branch Rankings (CSV)",
                        br_csv,
                        "beu_branch_rankings.csv",
                        "text/csv",
                        key="dl-branch-csv",
                        use_container_width=True,
                    )

            with e2:
                st.markdown("#### 📊 Excel Download (Multi-Sheet)")
                st.markdown("Includes **Student Results + College Rankings + Branch Rankings + Top 10** in one file.")
                try:
                    excel_bytes = build_excel_report(df_filtered, college_rankings, branch_rankings)
                    st.download_button(
                        "⬇️ Download Full Report (Excel)",
                        excel_bytes,
                        f"beu_full_report_batch{batch_year}_sem{semester_num}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl-excel",
                        use_container_width=True,
                    )
                except ImportError:
                    st.warning("Install `openpyxl` to enable Excel export: `pip install openpyxl`")
                except Exception as e:
                    st.error(f"Excel export error: {e}")

            st.markdown("---")
            st.markdown("#### 📋 Data Preview")
            st.markdown(f"**{len(export_df)} students** | **{len(export_df.columns)} columns**")
            st.dataframe(export_df.head(10), use_container_width=True, hide_index=True)

else:
    # Landing state (Quick Rank Checker UI)
    st.markdown("""
    <div style="background:rgba(255, 255, 255, 0.05);padding:30px;border-radius:16px;border:1px solid rgba(255, 255, 255, 0.1);max-width:800px;margin:20px auto;box-shadow:0 8px 32px 0 rgba(31,38,135,0.2);color:inherit;">
        <h2 style="color:#3b82f6;margin:0 0 8px;text-align:center;">🔍 Quick Rank & Marksheet Checker</h2>
        <p style="color:inherit;opacity:0.85;font-size:1rem;margin:0 0 20px;text-align:center;line-height:1.5;">
            Enter your 11-digit BEU Registration Number to view your comparative ranks (University, Branch, College, and Class) and access your official marksheet.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Wrap the input controls in a clean container
    with st.container():
        reg_input = st.text_input(
            "Registration Number",
            value="",
            max_chars=11,
            placeholder="Enter your 11-digit Registration Number (e.g., 22101107001)...",
            help="Your registration number encodes your batch, branch, and college.",
            label_visibility="collapsed"
        )
        
        parsed = parse_registration_no(reg_input)
        if parsed:
            batch_year_val = parsed["batch_year"]
            branch_code_val = parsed["branch_code"]
            college_code_val = parsed["college_code"]
            
            branch_name = BRANCH_CODES.get(branch_code_val, "Unknown Branch")
            college_name = COLLEGE_CODES.get(college_code_val, "Unknown College")
            
            # Show the detected details dynamically
            st.markdown(f"""
            <div style="background:rgba(16, 185, 129, 0.1);padding:15px;border-radius:10px;margin:15px 0;border:1px solid rgba(16, 185, 129, 0.2);">
                <span style="color:#10b981;font-weight:bold;font-size:1.1rem;">✅ Registration Details Detected:</span>
                <table style="width:100%; border:none; margin:10px 0 0 0; background:transparent; color:inherit;">
                    <tr style="background:transparent;"><td style="border:none;padding:4px;font-weight:bold;width:25%;opacity:0.7;">Batch Year:</td><td style="border:none;padding:4px;font-weight:bold;">20{batch_year_val}</td></tr>
                    <tr style="background:transparent;"><td style="border:none;padding:4px;font-weight:bold;opacity:0.7;">Branch/Course:</td><td style="border:none;padding:4px;font-weight:bold;">{branch_name} ({branch_code_val})</td></tr>
                    <tr style="background:transparent;"><td style="border:none;padding:4px;font-weight:bold;opacity:0.7;">College:</td><td style="border:none;padding:4px;font-weight:bold;">{college_name} ({college_code_val})</td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
            
            # Fetch exams for this batch
            with st.spinner("🔍 Fetching available semesters and exam sessions..."):
                exams = get_exams_for_batch(batch_year_val)
                
                # Prepend ASPX legacy portals if batch is 23
                if batch_year_val == 23:
                    aspx_exams = [
                        {"semId": 1, "examHeld": "ASPX_2023_SEM1", "examName": "B.Tech 1st Sem Examination 2023 (ASPX Portal)", "session": "ASPX_2023_SEM1"},
                        {"semId": 2, "examHeld": "ASPX_2023_SEM2", "examName": "B.Tech 2nd Sem Examination 2024 (ASPX Portal)", "session": "ASPX_2023_SEM2"},
                    ]
                    for ae in reversed(aspx_exams):
                        if not any(e.get("examHeld") == ae["examHeld"] for e in exams):
                            exams.insert(0, ae)
                
                # Fallback if empty
                if not exams:
                    exams = [
                        {"semId": 6, "examHeld": "December/2025", "examName": "B.Tech 6th Semester (December/2025)", "session": "December/2025"},
                        {"semId": 5, "examHeld": "July/2025", "examName": "B.Tech 5th Semester (July/2025)", "session": "July/2025"},
                        {"semId": 4, "examHeld": "December/2025", "examName": "B.Tech 4th Semester (December/2025)", "session": "December/2025"},
                        {"semId": 3, "examHeld": "July/2025", "examName": "B.Tech 3rd Semester (July/2025)", "session": "July/2025"},
                        {"semId": 2, "examHeld": "May/2025", "examName": "B.Tech 2nd Semester (May/2025)", "session": "May/2025"},
                        {"semId": 1, "examHeld": "February/2026", "examName": "B.Tech 1st Semester (February/2026)", "session": "February/2026"},
                        {"semId": 1, "examHeld": "January/2026", "examName": "B.Tech 1st Semester (January/2026)", "session": "January/2026"},
                    ]
            
            selected_exam = st.selectbox(
                "Select Semester / Exam Session",
                options=exams,
                format_func=lambda x: x.get("examName", f"Semester {x.get('semId')} ({x.get('examHeld')})"),
                key="quick_exam_select"
            )
            
            if st.button("🔍 Check Rank & Marksheet", type="primary", use_container_width=True):
                semester_roman = SEMESTER_MAPPING.get(selected_exam["semId"], "I")
                exam_held = selected_exam["examHeld"]
                
                client = BEUApiClient()
                
                # 1. Fetch searched student's specific result first to fail fast
                with st.spinner("⏳ Locating your result on BEU servers..."):
                    student_res = client.fetch_result(reg_input, semester_roman, batch_year_val, exam_held)
                
                if not student_res:
                    st.error("❌ No result found for this registration number in the selected semester/exam session.")
                    st.info("Please verify the registration number and ensure results have been published for this semester.")
                else:
                    # 2. Student found! Query active colleges and download batch for ranking
                    with st.spinner("🏫 Locating all active colleges offering this branch..."):
                        all_colleges = list(COLLEGE_CODES.keys())
                        active_colleges = client.find_active_colleges(
                            branch_code_val, batch_year_val, semester_roman, exam_held, all_colleges
                        )
                        # Ensure student's college is in the list
                        if college_code_val not in active_colleges:
                            active_colleges.append(college_code_val)
                            
                    with st.spinner(f"🚀 Fetching results for all {len(active_colleges)} colleges to compute true rankings..."):
                        # Fetch all active colleges
                        raw_results = client.fetch_batch_results(
                            start_reg=1,
                            end_reg=60,
                            branch_code=branch_code_val,
                            college_code=active_colleges,
                            batch_year=batch_year_val,
                            semester=semester_roman,
                            exam_held=exam_held,
                            include_lateral=False
                        )
                        
                        # Make sure our searched student's result is in the collection (handles edge case rolls > 60)
                        if not any(str(r.get("redg_no")).strip() == reg_input.strip() for r in raw_results):
                            raw_results.append(student_res)
                            
                        # Process and compute ranks
                        df = process_results_to_dataframe(raw_results)
                        st.session_state.results_df = df
                        st.session_state.batch_stats = analyze_batch_performance(df)
                        
                        # Set search variables to switch view
                        st.session_state.quick_search_reg = reg_input.strip()
                        st.session_state.quick_search_sem = semester_roman
                        st.session_state.quick_search_exam = exam_held
                        st.session_state.show_full_analytics = False
                        
                        st.success("🎉 Comparative ranks calculated!")
                        st.rerun()
        else:
            if reg_input:
                st.warning("⚠️ Please enter a valid 11-digit numeric Registration Number (e.g. 22101107001).")
            else:
                st.markdown("""
                <div style="margin-top:20px;display:flex;justify-content:center;gap:20px;flex-wrap:wrap;color:inherit;">
                    <div style="background:rgba(255,255,255,0.02);padding:15px;border-radius:10px;border:1px solid rgba(255,255,255,0.05);min-width:180px;text-align:center;color:inherit;">
                        <span style="font-size:1.5rem;">🌐</span>
                        <h4 style="margin:8px 0 4px;color:inherit;">University Ranking</h4>
                        <p style="margin:0;font-size:0.8rem;color:inherit;opacity:0.7;">Compare against all colleges</p>
                    </div>
                    <div style="background:rgba(255,255,255,0.02);padding:15px;border-radius:10px;border:1px solid rgba(255,255,255,0.05);min-width:180px;text-align:center;color:inherit;">
                        <span style="font-size:1.5rem;">🌿</span>
                        <h4 style="margin:8px 0 4px;color:inherit;">Branch Ranking</h4>
                        <p style="margin:0;font-size:0.8rem;color:inherit;opacity:0.7;">See standing in your branch</p>
                    </div>
                    <div style="background:rgba(255,255,255,0.02);padding:15px;border-radius:10px;border:1px solid rgba(255,255,255,0.05);min-width:180px;text-align:center;color:inherit;">
                        <span style="font-size:1.5rem;">🏫</span>
                        <h4 style="margin:8px 0 4px;color:inherit;">College Ranking</h4>
                        <p style="margin:0;font-size:0.8rem;color:inherit;opacity:0.7;">Find rank in your college</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

# ── Auto-Refresh Logic ────────────────────────────────────────────────────────
if enable_auto_refresh and st.session_state.results_df is not None:
    if st.session_state.last_refresh_time is None:
        st.session_state.last_refresh_time = time.time()

    time_elapsed = time.time() - st.session_state.last_refresh_time
    time_until_refresh = (refresh_interval * 60) - time_elapsed

    if time_until_refresh <= 0:
        st.session_state.last_refresh_time = time.time()
        st.toast("🔄 Auto-refreshing results...", icon="🔄")
        time.sleep(1)
        st.rerun()
    else:
        m = int(time_until_refresh // 60)
        s = int(time_until_refresh % 60)
        st.sidebar.info(f"⏱️ Next refresh in: {m}m {s}s")
        time.sleep(1)
        st.rerun()

# ── Floating Risso Chatbot ────────────────────────────────────────────────────
if "risso_messages" not in st.session_state:
    st.session_state.risso_messages = [{
        "role": "assistant",
        "content": "🎓 Hi! I'm Risso, your BEU Results Assistant. How can I help you today?",
    }]

gemini_api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

with st.container():
    st.markdown("""
    <style>
    .stPopover {position:fixed;bottom:30px;right:30px;z-index:1000;width:65px!important;height:65px!important;}
    .stPopover > div {width:65px!important;}
    .stPopover > button {
        background-color:#1a1a4b!important;color:white!important;border-radius:50%!important;
        width:65px!important;height:65px!important;display:flex!important;
        align-items:center!important;justify-content:center!important;
        transition:all 0.3s!important;box-shadow:0 6px 16px rgba(0,0,0,.4)!important;
        border:2px solid rgba(255,255,255,.1)!important;padding:0!important;
    }
    .stPopover > button:hover {transform:scale(1.1)!important;background-color:#242461!important;}
    .stPopover > button div p {font-size:28px!important;margin:0!important;}
    .stPopover > button > div:last-child {display:none!important;}
    </style>""", unsafe_allow_html=True)

    chat_popover = st.popover("✨", use_container_width=False)
    with chat_popover:
        st.markdown("### 🤖 Risso Chatbot")
        st.caption("Your AI assistant for BEU results")

        for msg in st.session_state.risso_messages:
            if msg["role"] == "user":
                st.markdown(
                    f"<div style='text-align:right;padding:5px;border-radius:10px;margin:5px;color:#333;'>"
                    f"<b>You:</b> {msg['content']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<div style='background:#f0f2f6;padding:10px;border-radius:10px;margin:5px;color:#333;'>"
                    f"🤖 <b>Risso:</b> {msg['content']}</div>", unsafe_allow_html=True)

        if len(st.session_state.risso_messages) <= 1:
            st.markdown("<p style='font-size:0.8rem;color:#666;'>Try asking:</p>", unsafe_allow_html=True)
            for suggestion in ["What's the class average?", "Who are the top students?", "How many passed?"]:
                if st.button(suggestion, key=f"suggest_{suggestion}", use_container_width=True):
                    st.session_state.risso_messages.append({"role": "user", "content": suggestion})
                    if st.session_state.results_df is not None:
                        sdf = st.session_state.results_df
                        ss = st.session_state.batch_stats or {}
                        ctx = (f"You are Risso, an AI for BEU students. "
                               f"Total: {ss.get('total_students','?')}, "
                               f"Pass%: {ss.get('pass_percentage',0):.1f}%, "
                               f"Avg SGPA: {ss.get('avg_sgpa',0):.2f}. Q: {suggestion}")
                        try:
                            import google.generativeai as genai
                            genai.configure(api_key=gemini_api_key)
                            model = genai.GenerativeModel('models/gemini-flash-latest')
                            resp = model.generate_content(ctx)
                            st.session_state.risso_messages.append({"role": "assistant", "content": resp.text or "No response."})
                        except Exception as e:
                            st.session_state.risso_messages.append({"role": "assistant", "content": f"Error: {e}"})
                    else:
                        st.session_state.risso_messages.append({"role": "assistant", "content": "Fetch results first! 😊"})
                    st.rerun()

        user_input = st.text_input("Type here...", key="risso_input", placeholder="Ask Risso anything...")
        c_send, c_clear = st.columns([4, 1])
        with c_send:
            if st.button("Send ➤", key="risso_send", use_container_width=True) and user_input:
                st.session_state.risso_messages.append({"role": "user", "content": user_input})
                if st.session_state.results_df is not None:
                    sdf = st.session_state.results_df
                    ss = st.session_state.batch_stats or {}
                    student_data = sdf[["Student Name", "SGPA", "CGPA", "Status"]].to_string(index=False)
                    ctx = (f"You are Risso, AI for BEU students.\n"
                           f"Stats: Total={ss.get('total_students','?')}, Pass%={ss.get('pass_percentage',0):.1f}%, "
                           f"AvgSGPA={ss.get('avg_sgpa',0):.2f}\n"
                           f"Students:\n{student_data}\nQ: {user_input}")
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=gemini_api_key)
                        model = genai.GenerativeModel('models/gemini-flash-latest')
                        resp = model.generate_content(ctx)
                        st.session_state.risso_messages.append({"role": "assistant", "content": resp.text or "No response."})
                    except Exception as e:
                        st.session_state.risso_messages.append({"role": "assistant", "content": f"Error: {e}"})
                else:
                    st.session_state.risso_messages.append({"role": "assistant", "content": "Fetch results first! 🎓"})
                st.rerun()
        with c_clear:
            if st.button("🗑️", key="risso_clear", use_container_width=True):
                st.session_state.risso_messages = []
                st.rerun()
