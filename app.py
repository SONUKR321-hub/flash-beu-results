
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from backend.api_client import BEUApiClient
from backend.data_processing import process_results_to_dataframe, analyze_batch_performance
from backend.constants import BRANCH_CODES, COLLEGE_CODES, SEMESTERS, SEMESTER_MAPPING

# Page Config
st.set_page_config(
    page_title="BEU Insights Master",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load CSS
def load_css():
    with open(os.path.join(os.path.dirname(__file__), 'src/frontend/styles.css')) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css()

# Session State Initialization
if 'results_df' not in st.session_state:
    st.session_state.results_df = None
if 'batch_stats' not in st.session_state:
    st.session_state.batch_stats = None

# Sidebar Configuration
with st.sidebar:
    st.title("🎓 Config Panel")
    
    st.markdown("### Batch Details")
    batch_year = st.number_input("Batch Year (e.g. 24 for 2024)", min_value=15, max_value=30, value=24)
    
    semester_num = st.selectbox(
        "Semester", 
        options=list(SEMESTER_MAPPING.keys()),
        format_func=lambda x: f"{x} ({SEMESTERS[SEMESTER_MAPPING[x]]})",
        index=0  # Default to 1st semester
    )
    semester_roman = SEMESTER_MAPPING[semester_num]
    
    # Auto-detect defaults (hidden logic)
    # Smart default for Exam Held logic is now handled in the fetch_with_auto_probe function
    
    st.markdown("### Institution")
    college_code = st.selectbox(
        "College", 
        options=list(COLLEGE_CODES.keys()),
        format_func=lambda x: f"{x} - {COLLEGE_CODES[x]}",
        index=list(COLLEGE_CODES.keys()).index("107")  # Default to MIT Muzaffarpur
    )
    
    branch_code = st.selectbox(
        "Branch", 
        options=list(BRANCH_CODES.keys()),
        format_func=lambda x: f"{x} - {BRANCH_CODES[x]}",
        index=list(BRANCH_CODES.keys()).index("101")  # Default to Civil Engineering
    )
    
    st.markdown("### Range")
    col1, col2 = st.columns(2)
    with col1:
        start_reg = st.number_input("Start", value=1, min_value=1)
    with col2:
        end_reg = st.number_input("End", value=10, min_value=1)
        
    include_lateral = st.checkbox("Include LE Students?", value=False)
    
    st.markdown("---")
    st.markdown("### ⚙️ Advanced Settings")
    
    # Auto-refresh toggle
    enable_auto_refresh = st.checkbox("🔄 Auto-Refresh Results", value=False)
    if enable_auto_refresh:
        refresh_interval = st.number_input("Refresh Interval (minutes)", min_value=1, max_value=30, value=5)
    
    




    if st.button("🚀 Fetch Results", use_container_width=True):
        client = BEUApiClient()
        
        # Helper for auto-probing
        def fetch_with_auto_probe(start, end, branch, college, batch, sem, lateral):
            # Priority list of likely exam dates
            # Most recent/likely first
            dates = [
                "July/2025", "May/2025", "Dec/2024", "Sep/2024", "Aug/2024", 
                "July/2024", "May/2024", "Dec/2023"
            ]
            
            progress_text = "Searching for correct exam session..."
            my_bar = st.progress(0, text=progress_text)
            
            for idx, date in enumerate(dates):
                st.toast(f"Trying session: {date}...", icon="🔍")
                
                # Robust Probe: Check first 5 students, not just one.
                # If student 001 is missing but 002 exists, we should still catch it.
                probe_end = start + 4
                probe_results = client.fetch_batch_results(
                    start, probe_end, branch, college, batch, sem, date, lateral, workers=5
                )
                
                if probe_results:
                    st.toast(f"Found data in {date}!", icon="✅")
                    my_bar.progress(100, text=f"Data found in {date}! Fetching full batch...")
                    # Found the correct date! Now fetch everyone requested
                    return client.fetch_batch_results(
                        start, end, branch, college, batch, sem, date, lateral
                    )
                
                my_bar.progress(int((idx + 1) / len(dates) * 100), text=f"Checking {date}...")
                
            return []

        with st.spinner(f"Auto-detecting results for {COLLEGE_CODES[college_code]}..."):
            # Use auto-probe instead of fixed date
            raw_results = fetch_with_auto_probe(
                start_reg, end_reg, branch_code, college_code, 
                batch_year, semester_roman, include_lateral
            )
            
            if raw_results:
                df = process_results_to_dataframe(raw_results)
                st.session_state.results_df = df
                st.session_state.batch_stats = analyze_batch_performance(df)
                st.success(f"Successfully fetched {len(df)} records!")
            else:
                st.error("No results found in any recent exam session.")
                st.info("The system tried: July/2025, May/2025, Dec/2024, Sep/2024, Aug/2024, July/2024, May/2024, Dec/2023.")
                
                st.warning("⚠️ **Troubleshooting Tips:**")
                st.markdown("""
                1. **Results might not be published yet:** If you are in **Batch 2024 (1st Sem)**, your results are likely **not available** on the BEU portal yet.
                2. **Wrong Batch Year:** Did you mean **Batch 2023**? Try changing the Batch Year in the sidebar.
                3. **Wrong Branch:** Ensure you selected **155 - CSE (IoT)** for Gopalganj, NOT 105.
                """)
                
                # Smart Check: Proactively check if Batch 23 works for this query
                if batch_year == 24:
                    st.info("🕵️‍♂️ **Checking if results exist for Batch 23 instead...**")
                    check_23 = client.fetch_batch_results(start_reg, start_reg, branch_code, college_code, 23, "I", "Dec/2023", include_lateral, workers=1)
                    if check_23:
                        st.success("✅ **Found results for Batch 2023!** Please change 'Batch Year' to **23** in the sidebar.")


# Main Dashboard
st.markdown("# 🎓 BEU Insights Master")
st.markdown("<div style='text-align:center; color:#000000; font-size:1.2rem; margin-top:0.5rem; font-weight:600;'>(Designed &amp; Built by <b>Master Developer Kumar Sonu from MIT</b>)</div>", unsafe_allow_html=True)
st.markdown("""
<div style='height:200px; background: linear-gradient(135deg, #ff6b6b, #f7d794, #4ade80); border-radius:12px; margin:1rem 0; box-shadow: 0 4px 12px rgba(0,0,0,0.3);'></div>
""", unsafe_allow_html=True)

st.markdown(f"**{COLLEGE_CODES.get(college_code, 'Unknown College')}** | Batch 20{batch_year}")

if st.session_state.results_df is not None:
    df = st.session_state.results_df
    stats = st.session_state.batch_stats
    
    # Overview Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Students", stats['total_students'])
    m2.metric("Pass Rate", f"{stats['pass_percentage']:.1f}%")
    m3.metric("Avg SGPA", f"{stats['avg_sgpa']:.2f}")
    m4.metric("Avg CGPA", f"{stats['avg_cgpa']:.2f}")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Analytics", "🏆 Leaderboard", "📝 Detailed Data", "📤 Export"])
    
    with tab1:
        c1, c2 = st.columns([2, 1])
        with c1:
            # SGPA Distribution
            fig_sgpa = px.histogram(
                df, x="SGPA", nbins=20, 
                title="SGPA Distribution", 
                color_discrete_sequence=['#2563eb'],
                template="plotly_white"
            )
            st.plotly_chart(fig_sgpa, use_container_width=True)
            
        with c2:
            # Pass/Fail Pie
            status_counts = df["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig_pie = px.pie(
                status_counts, values="Count", names="Status", 
                title="Pass vs Fail",
                color_discrete_sequence=px.colors.qualitative.Set2,
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
        # Scatter Plot SGPA vs CGPA
        fig_scatter = px.scatter(
            df, x="CGPA", y="SGPA", color="Status",
            hover_data=["Student Name", "Registration No"],
            title="Correlation: SGPA vs CGPA",
            template="plotly_white"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with tab2:
        st.markdown("### 🌟 Toppers")
        toppers = stats.get('toppers', [])
        
        cols = st.columns(3)
        for i, topper in enumerate(toppers):
            with cols[i]:
                st.markdown(f"""
                <div style="background: white; padding: 20px; border-radius: 10px; border: 1px solid #ffd700; text-align: center;">
                    <h1 style="color: #d97706;">#{i+1}</h1>
                    <h3>{topper['Student Name']}</h3>
                    <p style="font-size: 1.2rem; font-weight: bold;">SGPA: {topper['SGPA']}</p>
                    <p style="color: gray;">{topper['Registration No']}</p>
                </div>
                """, unsafe_allow_html=True)
                
        st.markdown("---")
        st.markdown("### Subject Wise High Scores")
        # Logic for subject wise toppers can go here
        
    with tab3:
        # Filters
        st.markdown("#### Filter Data")
        f1, f2 = st.columns(2)
        with f1:
            status_filter = st.multiselect("Filter by Status", options=df["Status"].unique(), default=df["Status"].unique())
        with f2:
            sort_by = st.selectbox("Sort By", ["Registration No", "SGPA", "CGPA", "Student Name"])
            
        filtered_df = df[df["Status"].isin(status_filter)]
        if sort_by == "SGPA":
            filtered_df = filtered_df.sort_values(by="SGPA", ascending=False)
        elif sort_by == "CGPA":
            filtered_df = filtered_df.sort_values(by="CGPA", ascending=False)
        elif sort_by == "Student Name":
            filtered_df = filtered_df.sort_values(by="Student Name")
            
        st.dataframe(filtered_df, use_container_width=True, height=600)
        
    with tab4:
        st.markdown("### Download Report")
        
        # CSV Export
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download CSV",
            csv,
            "results.csv",
            "text/csv",
            key='download-csv'
        )
        
        # Excel Export (Requires openpyxl)
        # We can implement Excel export buffer here


else:
    st.info("👈 Please configure the search parameters in the sidebar and click Fetch.")


# Auto-Refresh Logic
if enable_auto_refresh and st.session_state.results_df is not None:
    import time
    
    # Initialize last refresh time
    if 'last_refresh_time' not in st.session_state:
        st.session_state.last_refresh_time = time.time()
    
    # Check if it's time to refresh
    time_elapsed = time.time() - st.session_state.last_refresh_time
    time_until_refresh = (refresh_interval * 60) - time_elapsed
    
    if time_until_refresh <= 0:
        st.session_state.last_refresh_time = time.time()
        st.toast("🔄 Auto-refreshing results...", icon="🔄")
        time.sleep(1)
        st.rerun()
    else:
        # Show countdown
        minutes_left = int(time_until_refresh // 60)
        seconds_left = int(time_until_refresh % 60)
        st.sidebar.info(f"⏱️ Next refresh in: {minutes_left}m {seconds_left}s")
        time.sleep(1)
        st.rerun()

# Floating Chat Widget (Bottom Right)
# Initialize chat history (always)
if 'risso_messages' not in st.session_state:
    st.session_state.risso_messages = []
    st.session_state.risso_messages.append({
        "role": "assistant", 
        "content": "🎓 Hi! I'm Risso, your BEU Results Assistant. How can I help you today?"
    })

# Main Layout: Floating Chat Widget
with st.container():
    # Use custom CSS to float the button/widget if possible, else use st.popover as a fixed element
    st.markdown("""
        <style>
        .stPopover {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
        }
        </style>
    """, unsafe_allow_html=True)
    
    chat_popover = st.popover("💬 Ask Risso AI", use_container_width=False)
    
    with chat_popover:
        st.markdown("### 🤖 Risso Chatbot")
        st.caption("Your AI assistant for BEU results")
        
        # Hardcoded API key
        gemini_api_key = "AIzaSyCeU5Nb77TfHqWD-pzuTamq3YYGAHaocj0"
        
        # Display chat history in the popover
        for msg in st.session_state.risso_messages:
            if msg["role"] == "user":
                st.markdown(f"<div style='text-align: right; padding: 5px; border-radius: 10px; margin: 5px; color: #333;'><b>You:</b> {msg['content']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin: 5px; color: #333;'>🤖 <b>Risso:</b> {msg['content']}</div>", unsafe_allow_html=True)
        
        # Suggested questions (only if no messages beyond welcome)
        if len(st.session_state.risso_messages) <= 1:
            st.markdown("<p style='font-size: 0.8rem; color: #666;'>Try asking:</p>", unsafe_allow_html=True)
            suggestions = [
                "What's the class average?",
                "Who are the top students?",
                "How many passed?"
            ]
            
            for suggestion in suggestions:
                if st.button(suggestion, key=f"suggest_{suggestion}", use_container_width=True):
                    st.session_state.risso_messages.append({"role": "user", "content": suggestion})
                    
                    if st.session_state.results_df is not None:
                        df = st.session_state.results_df
                        stats = st.session_state.batch_stats
                        
                        # Full student data for Risso to search through
                        student_data = df[['Student Name', 'SGPA', 'Status']].to_string(index=False)
                        
                        context = f"""You are Risso, a friendly and intelligent AI assistant for BEU students.
Current Results Data:
- Total Students: {stats['total_students']}
- Pass Rate: {stats['pass_percentage']:.1f}%
- Avg SGPA: {stats['avg_sgpa']:.2f}

FULL STUDENT LIST:
{student_data}

Batch: {COLLEGE_CODES.get(college_code, 'Unknown')} | Batch 20{batch_year} | {semester_num}

Question: {suggestion}

Provide a helpful, encouraging answer. If the question is about a specific student, LOOK for them in the FULL STUDENT LIST above and provide their specific SGPA and status."""

                        try:
                            import google.generativeai as genai
                            genai.configure(api_key=gemini_api_key)
                            model = genai.GenerativeModel('models/gemini-flash-latest')
                            response = model.generate_content(context)
                            if response.text:
                                st.session_state.risso_messages.append({"role": "assistant", "content": response.text})
                            else:
                                st.session_state.risso_messages.append({"role": "assistant", "content": "I'm having trouble generating an answer right now. Please try again."})
                        except Exception as e:
                            st.session_state.risso_messages.append({"role": "assistant", "content": f"Connection issue: {str(e)}"})
                    else:
                        st.session_state.risso_messages.append({"role": "assistant", "content": "Fetch the results first, then I'll answer that! 😊"})
                    st.rerun()
        
        # Chat input
        user_input = st.text_input("Type here...", key="risso_input_floating", placeholder="Ask Risso anything...")
        
        col_send, col_clear = st.columns([4, 1])
        with col_send:
            if st.button("Send ➤", key="send_risso_floating", use_container_width=True) and user_input:
                st.session_state.risso_messages.append({"role": "user", "content": user_input})
                
                if st.session_state.results_df is not None:
                    df = st.session_state.results_df
                    stats = st.session_state.batch_stats
                    
                    # Full student data for Risso to search through
                    student_data = df[['Student Name', 'SGPA', 'Status']].to_string(index=False)
                    
                    context = f"""You are Risso, a friendly and intelligent AI assistant for BEU students.
Current Results Data:
- Total Students: {stats['total_students']}
- Pass Rate: {stats['pass_percentage']:.1f}%
- Avg SGPA: {stats['avg_sgpa']:.2f}

FULL STUDENT LIST:
{student_data}

Batch: {COLLEGE_CODES.get(college_code, 'Unknown')} | Batch 20{batch_year} | {semester_num}

Question: {user_input}

Answer using the data provided. If someone asks for a specific student's result, check the FULL STUDENT LIST. Be very friendly and supportive."""

                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=gemini_api_key)
                        model = genai.GenerativeModel('models/gemini-flash-latest')
                        response = model.generate_content(context)
                        if response.text:
                            st.session_state.risso_messages.append({"role": "assistant", "content": response.text})
                        else:
                            st.session_state.risso_messages.append({"role": "assistant", "content": "I received an empty response. Please try again."})
                    except Exception as e:
                        st.session_state.risso_messages.append({"role": "assistant", "content": f"Connection issue: {str(e)}. Please check your internet or API key."})
                else:
                    st.session_state.risso_messages.append({"role": "assistant", "content": "Please fetch the results first! 🎓"})
                st.rerun()
                
        with col_clear:
            if st.button("🗑️", key="clear_risso_floating", use_container_width=True):
                st.session_state.risso_messages = []
                st.rerun()
