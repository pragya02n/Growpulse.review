import streamlit as st
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import streamlit.components.v1 as components

# Import the existing pipeline logic
from src.growpulse.pipeline import PipelineConfig, run_pipeline
from src.growpulse.phase4.delivery import render_pulse_html

# Page configuration
st.set_page_config(
    page_title="Groww Weekly Pulse",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS to hide Streamlit header and footer for a cleaner look
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 0rem; padding-bottom: 0rem; padding-left: 0rem; padding-right: 0rem;}
    </style>
    """, unsafe_allow_html=True)

def main():
    # Load environment variables
    load_dotenv()
    
    # Configuration
    groq_api_key = os.getenv("GROQ_API_KEY")
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not groq_api_key:
        st.error("Missing GROQ_API_KEY. Please set it in your environment variables.")
        return

    # Sidebar for controls (optional, since we have them in HTML)
    with st.sidebar:
        st.title("Settings")
        weeks = st.slider("Lookback Window (Weeks)", 1, 52, 12)
        use_sheets = st.toggle("Use Google Sheets", value=True)
        
        if st.button("Regenerate Pulse"):
            st.cache_data.clear()

    # Run Pipeline
    @st.cache_data(show_spinner="Analyzing Reviews with AI...")
    def get_dashboard_data():
        cfg = PipelineConfig(
            csv_path=Path("Data/reviews.csv"),
            use_sheets=use_sheets,
            spreadsheet_id=spreadsheet_id,
            credentials_path=credentials_path,
            time_window_weeks=weeks,
            groq_api_key=groq_api_key,
            calendar_id=os.getenv("GOOGLE_CALENDAR_ID")
        )
        
        now = datetime.utcnow()
        result = run_pipeline(cfg=cfg, now=now)
        
        # Metadata for HTML rendering
        from src.growpulse.phase4.delivery import PulseRunMetadata
        meta = PulseRunMetadata(
            week_range_label=f"Insights for {now.strftime('%Y-%m-%d')}",
            total_reviews=712, # Hardcoded as per user requirement
            time_window_weeks=8,
            generated_at_iso=now.isoformat()
        )
        
        return render_pulse_html(result.pulse, meta)

    try:
        html_content = get_dashboard_data()
        
        # Render the HTML dashboard
        # We use a large height to ensure the dashboard is visible
        components.html(html_content, height=2800, scrolling=True)
        
    except Exception as e:
        st.error(f"Error running pipeline: {e}")
        st.info("Ensure your .env file or Streamlit Secrets are correctly configured.")

if __name__ == "__main__":
    main()
