
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import time
from io import BytesIO

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

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
for key in ['results_df', 'batch_stats', 'last_refresh_time']:
    if key not in st.session_state:
        st.session_state[key] = None

# ── Helper: Stat Card HTML ────────────────────────────────────────────────────
def stat_card(label, value, bg="rgba(255,255,255,0.12)"):
    return f"""
    <div style="background:{bg};padding:12px 20px;border-radius:10px;min-width:110px;text-align:center;">
        <p style="margin:0;font-size:0.75rem;opacity:0.8;text-transform:uppercase;letter-spacing:.05em;">{label}</p>
        <h3 style="margin:4px 0 0;color:white;font-size:1.3rem;">{value}</h3>
    </div>"""

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎓 Config Panel")

    st.markdown("### Batch Details")
    batch_year = st.number_input("Batch Year (e.g. 23 for 2023)", min_value=15, max_value=30, value=23)

    semester_num = st.selectbox(
        "Semester",
        options=list(SEMESTER_MAPPING.keys()),
        format_func=lambda x: f"{x} ({SEMESTERS[SEMESTER_MAPPING[x]]})",
        index=2,  # Default to 3rd semester
    )
    semester_roman = SEMESTER_MAPPING[semester_num]

    st.markdown("### Institution")
    college_code = st.selectbox(
        "College",
        options=list(COLLEGE_CODES.keys()),
        format_func=lambda x: f"{x} - {COLLEGE_CODES[x]}",
        index=list(COLLEGE_CODES.keys()).index("107"),
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
    enable_auto_refresh = st.checkbox("🔄 Auto-Refresh Results", value=False)
    if enable_auto_refresh:
        refresh_interval = st.number_input("Refresh Interval (minutes)", min_value=1, max_value=30, value=5)
    else:
        refresh_interval = 5

    st.markdown("---")

    # ── Fetch Button ────────────────────────────────────────────────────────
    if st.button("🚀 Fetch Results", use_container_width=True, type="primary"):
        client = BEUApiClient()

        def fetch_with_auto_probe(start, end, branch, college, batch, sem, lateral):
            dates = [
                "January/2026", "November/2025", "July/2025", "May/2025",
                "Dec/2024", "Sep/2024", "Aug/2024",
                "July/2024", "May/2024", "Dec/2023",
            ]
            # Legacy ASPX portal probes for 2023 batch
            if sem == "I" and batch == 23:
                dates = ["ASPX_2023_SEM1"] + dates
            if sem == "II" and batch == 23:
                dates = ["ASPX_2023_SEM2"] + dates
            my_bar = st.progress(0, text="Searching for correct exam session...")
            for idx, date in enumerate(dates):
                st.toast(f"Trying session: {date}...", icon="🔍")
                probe_end = start + 4
                probe_results = client.fetch_batch_results(
                    start, probe_end, branch, college, batch, sem, date, lateral, workers=5
                )
                if probe_results:
                    st.toast(f"Found data in {date}!", icon="✅")
                    my_bar.progress(100, text=f"Data found in {date}! Fetching full batch...")
                    return client.fetch_batch_results(
                        start, end, branch, college, batch, sem, date, lateral
                    )
                my_bar.progress(int((idx + 1) / len(dates) * 100), text=f"Checking {date}...")
            return []

        with st.spinner(f"Auto-detecting results for {COLLEGE_CODES.get(college_code, college_code)}..."):
            raw_results = fetch_with_auto_probe(
                start_reg, end_reg, branch_code, college_code,
                batch_year, semester_roman, include_lateral,
            )

            if raw_results:
                df = process_results_to_dataframe(raw_results)
                st.session_state.results_df = df
                st.session_state.batch_stats = analyze_batch_performance(df)
                st.success(f"✅ Fetched {len(df)} records!")
            else:
                st.error("No results found in any recent exam session.")
                st.info(f"Tried: ASPX 2023 portal, November/2025, July/2025, May/2025, Dec/2024, Sep/2024, Aug/2024, July/2024, May/2024, Dec/2023.")
                st.warning("**Tips:** Check batch year, semester, and branch code.")
                if batch_year == 24:
                    check_23 = client.fetch_batch_results(
                        start_reg, start_reg, branch_code, college_code, 23, "I", "Dec/2023", include_lateral, workers=1
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

st.markdown(
    f"**{COLLEGE_CODES.get(college_code, 'Unknown College')}** · "
    f"Batch 20{batch_year} · {SEMESTERS.get(semester_roman, semester_roman)}"
)

# ── Dashboard ─────────────────────────────────────────────────────────────────
if st.session_state.results_df is not None:
    df = st.session_state.results_df
    stats = st.session_state.batch_stats

    # Always use the rank-enriched df from stats
    df = stats.get('df_with_ranks', df)
    college_rankings = stats.get('college_rankings', pd.DataFrame())
    branch_rankings = stats.get('branch_rankings', pd.DataFrame())

    # ── Overview Metrics ──────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("👥 Total Students", stats['total_students'])
    m2.metric("✅ Pass Rate", f"{stats['pass_percentage']:.1f}%")
    m3.metric("📈 Avg SGPA", f"{stats['avg_sgpa']:.2f}")
    m4.metric("🏅 Avg CGPA", f"{stats['avg_cgpa']:.2f}")
    m5.metric("❌ Failed", stats['failed'])

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
                df, x="SGPA", nbins=20,
                title="SGPA Distribution",
                color_discrete_sequence=["#3b82f6"],
                template="plotly_white",
            )
            fig_sgpa.update_layout(bargap=0.05)
            st.plotly_chart(fig_sgpa, use_container_width=True)

        with c2:
            status_counts = df["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig_pie = px.pie(
                status_counts, values="Count", names="Status",
                title="Pass vs Fail",
                color_discrete_sequence=["#10b981", "#f87171"],
                hole=0.45,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        fig_scatter = px.scatter(
            df, x="CGPA", y="SGPA", color="Status",
            hover_data=["Student Name", "Registration No"],
            title="Correlation: CGPA vs SGPA",
            template="plotly_white",
            color_discrete_map={"PASS": "#10b981", "FAIL": "#f87171"},
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # CGPA distribution
        fig_cgpa = px.histogram(
            df, x="CGPA", nbins=20,
            title="CGPA Distribution",
            color_discrete_sequence=["#8b5cf6"],
            template="plotly_white",
        )
        st.plotly_chart(fig_cgpa, use_container_width=True)

    # ── Tab 2: Leaderboard ────────────────────────────────────────────────────
    with tab_leaderboard:
        st.markdown("### 🌟 Top 3 Podium")
        toppers = stats.get('toppers', [])[:3]
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
        top10 = get_top_students(df, 10)
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
            top_row = df[df[rank_key] == 1]
            name = top_row["Student Name"].iloc[0] if not top_row.empty else "N/A"
            col.metric(f"{icon} {label.replace(' #1','')}", name)

        display_cols = [c for c in [
            "University Rank", "Branch Rank", "College Rank", "Class Rank",
            "Student Name", "Registration No", "College Name", "Branch",
            "CGPA", "SGPA", "Status",
        ] if c in df.columns]

        st.dataframe(
            df[display_cols].sort_values("University Rank"),
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
            options=df["Registration No"].tolist(),
            format_func=lambda x: f"{x} — {df[df['Registration No'] == x]['Student Name'].values[0]}",
        )
        if search_query:
            student = df[df["Registration No"] == search_query].iloc[0]
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

            # Marksheet
            st.markdown("#### 📊 Detailed Marksheet")
            subject_grades = [c for c in df.columns if c.startswith("Sub_") and c.endswith("_Grade")]
            if subject_grades:
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
                            "Subject": s_name,
                            "External (ESE)": s_ese if pd.notna(s_ese) else "-",
                            "Internal (IA)": s_ia if pd.notna(s_ia) else "-",
                            "Total": s_total if pd.notna(s_total) else "-",
                            "Grade": s_grade,
                            "Credits": s_credit if pd.notna(s_credit) else "-",
                        })
                if subj_data:
                    subj_df = pd.DataFrame(subj_data)
                    st.dataframe(subj_df, use_container_width=True, hide_index=True,
                        column_config={
                            "Subject": st.column_config.TextColumn("Subject", width="large"),
                            "External (ESE)": st.column_config.TextColumn("Ext"),
                            "Internal (IA)": st.column_config.TextColumn("Int"),
                            "Total": st.column_config.TextColumn("Total"),
                            "Grade": st.column_config.TextColumn("Grade"),
                            "Credits": st.column_config.TextColumn("Cr"),
                        })
                else:
                    st.info("No subject grades found for this student.")
            else:
                st.warning("Subject details not available for this session.")

    # ── Tab 7: All Data ───────────────────────────────────────────────────────
    with tab_data:
        st.markdown("#### Filter & Explore Data")
        f1, f2, f3 = st.columns(3)
        with f1:
            status_filter = st.multiselect(
                "Filter by Status",
                options=df["Status"].unique().tolist(),
                default=df["Status"].unique().tolist(),
                key="status_filter_data",
            )
        with f2:
            sort_by = st.selectbox("Sort By", ["University Rank", "CGPA", "SGPA", "Student Name", "Registration No"], key="sort_data")
        with f3:
            if "Branch" in df.columns:
                branch_filter = st.multiselect(
                    "Filter by Branch",
                    options=df["Branch"].dropna().unique().tolist(),
                    default=df["Branch"].dropna().unique().tolist(),
                    key="branch_filter_data",
                )
            else:
                branch_filter = []

        filtered = df[df["Status"].isin(status_filter)]
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
        ] if c in df.columns]

        export_df = df[export_cols].sort_values("University Rank") if "University Rank" in df.columns else df[export_cols]

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
                excel_bytes = build_excel_report(df, college_rankings, branch_rankings)
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
    # Landing state
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;">
        <div style="font-size:5rem;">🎓</div>
        <h2 style="color:#1e3a8a;margin-top:16px;">Welcome to BEU Insights Master</h2>
        <p style="color:#64748b;font-size:1.1rem;max-width:600px;margin:8px auto;">
            Configure your search in the sidebar and click <b>🚀 Fetch Results</b> to get started.
        </p>
        <div style="display:flex;justify-content:center;gap:24px;margin-top:32px;flex-wrap:wrap;">
            <div style="background:#f0f9ff;padding:16px 24px;border-radius:12px;border-left:4px solid #3b82f6;text-align:left;min-width:200px;">
                <b>🎖️ Student Rankings</b><br><small style="color:#64748b;">University, College & Class rank</small>
            </div>
            <div style="background:#f0fdf4;padding:16px 24px;border-radius:12px;border-left:4px solid #10b981;text-align:left;min-width:200px;">
                <b>🏫 College Rankings</b><br><small style="color:#64748b;">Compare BEU colleges by CGPA</small>
            </div>
            <div style="background:#fdf4ff;padding:16px 24px;border-radius:12px;border-left:4px solid #8b5cf6;text-align:left;min-width:200px;">
                <b>🌿 Branch Rankings</b><br><small style="color:#64748b;">CSE vs ME vs CE vs EE …</small>
            </div>
            <div style="background:#fff7ed;padding:16px 24px;border-radius:12px;border-left:4px solid #f59e0b;text-align:left;min-width:200px;">
                <b>📤 Export Data</b><br><small style="color:#64748b;">CSV & Excel with all rankings</small>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

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
