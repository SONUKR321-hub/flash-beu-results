# 🎓 BEU Insights Master - Streamlit Cloud Deployment Guide

## Quick Deploy to Streamlit Cloud

Follow these steps to deploy your BEU Insights Master application:

### 1️⃣ Push Code to GitHub

First, ensure all your code is committed and pushed to a GitHub repository:

```bash
# Add all changes
git add .

# Commit changes
git commit -m "Add Streamlit Cloud deployment configuration"

# Push to GitHub
git push origin main
```

### 2️⃣ Deploy on Streamlit Cloud

1. **Go to Streamlit Cloud**: Visit [share.streamlit.io](https://share.streamlit.io)

2. **Sign in with GitHub**: Use your GitHub account to log in

3. **New App**: Click "New app" button

4. **Configure deployment**:
   - Repository: Select your `beu_result_master` repository
   - Branch: `main` (or your default branch)
   - Main file path: `app.py`
   
5. **Click "Deploy"**

### 3️⃣ Configure API Key (Important!)

After deployment, you need to add the Gemini API key:

1. In Streamlit Cloud dashboard, go to your app
2. Click **⚙️ Settings** → **Secrets**
3. Add this content:

```toml
GEMINI_API_KEY = "AIzaSyCeU5Nb77TfHqWD-pzuTamq3YYGAHaocj0"
```

4. Click **Save**
5. Your app will automatically restart with the API key

### 4️⃣ Access Your App

Your app will be live at: `https://[your-app-name].streamlit.app`

---

## 🔐 Security Note

The API key is now stored securely in Streamlit Cloud secrets and is NOT visible in your code or repository.

## ✅ What's Changed

- ✅ Created `.streamlit/config.toml` for production settings
- ✅ Updated `app.py` to use environment variables for API key
- ✅ Updated `.gitignore` to exclude secrets but include config
- ✅ Created this deployment guide

## 🆘 Troubleshooting

**App won't start?**
- Check that all dependencies in `requirements.txt` are installed
- Review the logs in Streamlit Cloud dashboard

**AI Chatbot not working?**
- Verify `GEMINI_API_KEY` is set in Streamlit Cloud secrets
- Check the exact secret name matches: `GEMINI_API_KEY`

**BEU API not fetching results?**
- This is a backend issue - verify the BEU website is accessible
- Try different date ranges in the auto-probe
