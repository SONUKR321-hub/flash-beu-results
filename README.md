
# 🎓 BEU Insights Master

A premium, high-performance result analyzer for Bihar Engineering University (BEU). 
Built with modern technologies to provide real-time insights, analytics, and AI-powered result assistance.

## ✨ Features

-   **⚡ Ultra-Fast API Fetching**: Directly communicates with BEU servers for rapid data retrieval.
-   **🤖 AI Assistant**: Ask questions about results using Google Gemini AI (e.g., "What's my SGPA?", "Who are the toppers?")
-   **🔄 Auto-Refresh**: Automatically checks for new results at configurable intervals
-   **📊 Batch Analytics**: Visualization of Pass/Fail rates, SGPA distribution, and more.
-   **🏆 Topper Leaderboard**: Automatically identifies and highlights the top performers.
-   **📥 Data Export**: Download results in CSV format for offline usage.
-   **🎨 Premium UI**: A clean, responsive, mobile-friendly dashboard interface.

## 🚀 Getting Started

### Prerequisites

Ensure you have Python 3.8+ installed.

### Installation

1.  Navigate to the project directory:
    ```bash
    cd "e:/beu my/beu_result_master"
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Running the App

Run the application using Streamlit:
```bash
streamlit run app.py
```

## 🛠️ Configuration

Use the sidebar to select:
-   **Batch Year**: The admission year (e.g., 24 for 2024).
-   **College & Branch**: Select from the comprehensive list of BEU institutions.
-   **Range**: Define the roll number range to fetch.

### Advanced Features

#### 🤖 AI Assistant
1. Get a free Gemini API key from: https://makersuite.google.com/app/apikey
2. Enter the API key in the sidebar under "AI Assistant"
3. Go to the "AI Assistant" tab after fetching results
4. Ask questions like:
   - "What's the class average SGPA?"
   - "Who are the top 5 students?"
   - "How many students passed?"
   - "What's my performance compared to the class?"

#### 🔄 Auto-Refresh
1. Enable "Auto-Refresh Results" in the sidebar
2. Set refresh interval (1-30 minutes)
3. The app will automatically check for new results and notify you

## 📝 Credits

**Designed & Built by Master Developer Kumar Sonu from MIT**

Based on the official BEU Results API.
