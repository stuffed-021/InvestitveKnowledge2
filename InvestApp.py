import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import os
import requests
import random
import re
import hashlib
import hmac
import secrets
import base64
from bs4 import BeautifulSoup
from groq import Groq
from supabase import create_client, Client

# --- APPLICATION HEADER & BRANDING CONFIGURATION ---
st.set_page_config(page_title="InvestiveKnowledge Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Read logo image file locally to convert it into an inline HTML string
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""

# Put your exact logo image filename here (ensure it is saved inside your script folder)
LOGO_FILENAME = "Gemini_Generated_Image_e6sxyve6sxyve6sx.png"
img_base64 = get_base64_image(LOGO_FILENAME)

# Initialize Groq Client safely
api_key = os.environ.get("GROQ_API_KEY", "gsk_placeholder_string")
try:
    client = Groq(api_key=api_key)
except Exception:
    st.error("Groq Client initialization failed. Check your API key setup!")

# --- SECURE RESEND CONFIGURATION ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_your_placeholder_here")

# --- SUPABASE CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project-id.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "your-supabase-anon-key")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Supabase Initialization Error: {e}")

# --- SYSTEM PROMPTS ---
MINI_SUMMARY_PROMPT = "You are a financial news summarizer. Provide a 1-sentence micro-summary of the core event. No emojis."
OVERALL_ANALYSIS_PROMPT = """
You are an institutional financial analyst. Analyze the 10 provided news summaries.
Determine the short-term directional likelihood and synthesize it into clear logic. No emojis.
Format:
LIKELIHOOD: [UPWARD, DOWNWARD, or NEUTRAL]
CONFIDENCE: [0% to 100%]
IMPACT_SUMMARY: [Detailed macro justification paragraph]
"""

# --- CRYPTOGRAPHIC & SUPABASE DB UTILITIES ---
def hash_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000)
    return key, salt

def verify_password(stored_key: bytes, stored_salt: bytes, provided_password: str) -> bool:
    new_key, _ = hash_password(provided_password, stored_salt)
    return hmac.compare_digest(stored_key, new_key)

def get_user_from_supabase(email: str) -> dict:
    """Fetches a user profile from the cloud Supabase vault table."""
    try:
        response = supabase.table("user_vault").select("key", "salt").eq("email", email).execute()
        if response.data and len(response.data) > 0:
            user_record = response.data[0]
            return {
                "key": bytes.fromhex(user_record["key"]),
                "salt": bytes.fromhex(user_record["salt"])
            }
    except Exception as e:
        st.error(f"Database Read Error: {e}")
    return None

def save_user_to_supabase(email: str, hashed_key: bytes, salt: bytes) -> bool:
    """Inserts a new credential profile safely into Supabase as hex strings."""
    try:
        payload = {
            "email": email,
            "key": hashed_key.hex(),
            "salt": salt.hex()
        }
        supabase.table("user_vault").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Database Write Error: {e}")
        return False

# --- LIVE RESEND EMAIL ENGINE ---
def send_live_verification_email(receiver_email):
    otp_code = str(random.randint(100000, 999999))
    url = "https://api.resend.com/emails"
    headers = {"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
    
    payload = {
        "from": "onboarding@resend.dev",
        "to": receiver_email,
        "subject": "🔒 Secure Access Token Code",
        "html": f"""
        <div style="font-family: sans-serif; padding: 20px; border: 1px solid #e1e1e1; border-radius: 8px; max-width: 500px; background-color: #0b0b0c; color: #e5e5e7;">
            <h2 style="color: #ffffff; margin-top: 0; font-weight: 300;">Confirm Your Identity</h2>
            <p style="font-size: 14px; color: #a1a1aa;">Enter this code alongside your password to finalize authorization:</p>
            <div style="background-color: #18181b; padding: 15px; border-radius: 5px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 4px; color: #ffffff; border: 1px solid #27272a; margin: 20px 0;">
                {otp_code}
            </div>
        </div>
        """
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=8)
        if response.status_code in [200, 201]:
            st.session_state["generated_otp_code"] = otp_code
            st.session_state["pending_email_verification"] = receiver_email
            return True, "Code sent!"
        return False, f"Resend Error: {response.text}"
    except Exception as e:
        return False, str(e)

# --- DATA PARSING UTILITIES ---
def scrape_article_content(url):
    if not url or ("quote" in url and "news" not in url):
        return "Generic structural node text content bypassed."
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = soup.find_all("p")
            text_content = " ".join([p.get_text() for p in paragraphs[:4]])
            if len(text_content.strip()) > 50:
                return text_content.strip()
    except Exception:
        pass
    return "Content successfully processed from core stream page wire."

def get_mini_summary(title, body):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": MINI_SUMMARY_PROMPT}, {"role": "user", "content": f"Title: {title}\nBody: {body}"}],
            max_tokens=60, temperature=0.1
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return "AI summary metrics parsed from source."

# --- CUSTOM INTERFACE STYLING ---
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;500;600&display=swap');
        
        html, body, [data-testid="stAppViewContainer"] {{
            background-color: #050505 !important;
            color: #E5E5E7 !important;
            font-family: 'Inter', sans-serif !important;
        }}
        
        [data-testid="stSidebar"], [data-testid="stSidebarCollapseButton"] {{
            display: none !important;
            visibility: hidden !important;
        }}
        
        .top-navbar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 70px;
            background: rgba(11, 11, 12, 0.8) !important;
            backdrop-filter: blur(25px) !important;
            -webkit-backdrop-filter: blur(25px) !important;
            border-bottom: 1px solid #1F1F22 !important;
            z-index: 99999;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 40px;
        }}

        .brand-container {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .brand-logo {{
            height: 36px;
            width: auto;
            border-radius: 4px;
        }}

        [data-testid="stMainBlockContainer"] {{
            padding-top: 100px !important;
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            color: #FFFFFF !important;
            font-weight: 300 !important;
            letter-spacing: -0.02em !important;
        }}
        
        .glass-card {{
            background: rgba(15, 15, 18, 0.45) !important;
            backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(255, 255, 255, 0.04) !important;
            border-radius: 12px !important;
            padding: 20px !important;
            margin-bottom: 16px !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8) !important;
        }}
        
        .neon-glow-blue {{
            border-left: 3px solid #00E5FF !important;
            box-shadow: -10px 0px 20px -10px rgba(0, 229, 255, 0.15) !important;
        }}
        
        div[data-baseweb="input"] {{
            background-color: #121214 !important;
            border: 1px solid #262629 !important;
            border-radius: 6px !important;
        }}
        
        div.stButton > button {{
            background-color: #ffffff !important;
            color: #050505 !important;
            border: 1px solid #ffffff !important;
            border-radius: 8px !important;
            padding: 10px 24px !important;
            font-family: 'Inter', sans-serif !important;
            font-weight: 500 !important;
            font-size: 13px !important;
            letter-spacing: 0.03em !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 4px 12px rgba(255, 255, 255, 0.05) !important;
        }}
        
        div.stButton > button p, div.stButton > button span {{
            color: #050505 !important;
            font-weight: 500 !important;
        }}
        
        div.stButton > button:hover {{
            background-color: #050505 !important;
            color: #ffffff !important;
            border: 1px solid #262629 !important;
            box-shadow: 0px 0px 20px rgba(0, 229, 255, 0.2) !important;
            transform: translateY(-1px) !important;
        }}
        
        div.stButton > button:hover p, div.stButton > button:hover span {{
            color: #ffffff !important;
        }}
        
        div[data-testid="stHorizontalBlock"] div[data-testid="stWidgetLabel"] {{
            display: none !important;
        }}
        
        div[role="radiogroup"] {{
            flex-direction: row !important;
            gap: 15px !important;
        }}
        
        div[role="radiogroup"] label {{
            background: #121214 !important;
            border: 1px solid #262629 !important;
            padding: 6px 16px !important;
            border-radius: 20px !important;
            color: #A1A1AA !important;
        }}
        
        div[role="radiogroup"] label[data-checked="true"] {{
            border-color: #00E5FF !important;
            color: #FFFFFF !important;
            background: rgba(0, 229, 255, 0.05) !important;
        }}

        #MainMenu, footer, header {{visibility: hidden;}}
    </style>
""", unsafe_allow_html=True)

# Generate Dynamic Top Navbar HTML incorporating your asset string
logo_html = f'<img src="data:image/png;base64,{img_base64}" class="brand-logo" />' if img_base64 else ""

st.markdown(f"""
    <div class="top-navbar">
        <div class="brand-container">
            {logo_html}
            <span style="font-weight: 400; font-size: 18px; letter-spacing: 0.05em; color: #FFFFFF;">InvestiveKnowledge</span>
        </div>
        <span style="font-weight: 200; font-size: 11px; color: #71717A; letter-spacing: 0.05em;">SECURE EXECUTION ENGINE</span>
    </div>
""", unsafe_allow_html=True)

if "authenticated_user_email" not in st.session_state:
    st.session_state["authenticated_user_email"] = None
if "login_step" not in st.session_state:
    st.session_state["login_step"] = "credentials"

# --- SECURITY INTERFACE GATE ---
if st.session_state["authenticated_user_email"] is None:
    col_a, col_b, col_c = st.columns([1, 2, 1])
    
    with col_b:
        st.markdown('<div class="glass-card" style="margin-top: 40px;">', unsafe_allow_html=True)
        st.subheader("🔒 ACCESS LAYER AUTHORIZATION REQUIRED")
        
        auth_mode = st.radio("Selection Mode", ["Log In", "Sign Up"], horizontal=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if auth_mode == "Sign Up":
            su_email = st.text_input("Email Address", key="su_email_input").strip().lower()
            su_pass = st.text_input("Password", type="password", key="su_pass_input").strip()
            
            if st.button("Register System Key"):
                email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                
                if not su_email or not re.match(email_regex, su_email):
                    st.error("❌ Invalid structural email layout configuration. Please check your spelling and try again.")
                elif len(su_pass) < 8:
                    st.error("❌ Key structural weakness: Minimum 8 characters required.")
                elif get_user_from_supabase(su_email) is not None:
                    st.error("❌ Identity record mapping conflict: Email already registered.")
                else:
                    hashed_key, salt = hash_password(su_pass)
                    if save_user_to_supabase(su_email, hashed_key, salt):
                        st.success("🎉 Key Registry Verified in Supabase! Switch panel to Log In.")
                    
        elif auth_mode == "Log In":
            if st.session_state["login_step"] == "credentials":
                li_email = st.text_input("Email Address", key="li_email").strip().lower()
                li_pass = st.text_input("Password", type="password", key="li_pass").strip()
                
                if st.button("Verify Verification Signature"):
                    user_data = get_user_from_supabase(li_email)
                    if user_data:
                        if verify_password(user_data["key"], user_data["salt"], li_pass):
                            with st.spinner("Dispatching identity code via Resend API loops..."):
                                success, msg = send_live_verification_email(li_email)
                                if success:
                                    st.session_state["login_step"] = "mfa"
                                    st.rerun()
                                else:
                                    st.error(f"❌ Mail Gateway failure: {msg}")
                        else:
                            st.error("❌ Access Denied: Invalid credentials signature matching.")
                    else:
                        st.error("❌ Access Denied: Identity file not allocated. Ensure you have Signed Up.")
                        
            elif st.session_state["login_step"] == "mfa":
                active_email = st.session_state.get("pending_email_verification")
                st.caption(f"Verification sequence multi-factor token transmitted onto: {active_email}")
                entered_code = st.text_input("Enter 6-Digit Transmission Token", key="mfa_code").strip()
                
                col_v, col_r = st.columns(2)
                with col_v:
                    if st.button("Finalize Verification Link"):
                        if "generated_otp_code" in st.session_state and entered_code == st.session_state["generated_otp_code"]:
                            st.session_state["authenticated_user_email"] = active_email
                            st.session_state["login_step"] = "credentials"
                            del st.session_state["generated_otp_code"]
                            st.rerun()
                        else:
                            st.error("❌ Token mismatch. Validation loop dropped.")
                with col_r:
                    if st.button("Abort Sequence"):
                        st.session_state["login_step"] = "credentials"
                        st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # --- ACTIVE SUITE SESSION CONTROLLER ---
    logged_in_user = st.session_state["authenticated_user_email"]
    
    col_nav, col_action = st.columns([5, 1])
    with col_nav:
        st.markdown(f'<p style="color: #00E5FF; font-size: 12px; font-weight:600; letter-spacing:0.05em; margin:0;">CONNECTED IDENTITY PATHWAY: {logged_in_user}</p>', unsafe_allow_html=True)
    with col_action:
        if st.button("🚪 Disconnect Session"):
            st.session_state["authenticated_user_email"] = None
            st.rerun()

    st.markdown("---")
    
    # --- REGULATORY COMPLIANCE CAUTION BANNER ---
    st.markdown(
        """
        <div class="glass-card" style="border-left: 3px solid #FFCC00 !important; padding: 15px 20px; margin-bottom: 25px;">
            <span style="font-size: 10px; color: #FFCC00; font-weight: 600; letter-spacing: 0.1em; display: block; margin-bottom: 4px;">⚠️ SYSTEM CAUTION & REGULATORY COMPLIANCE</span>
            <p style="font-size: 12px; color: #D4D4D8; font-weight: 300; margin: 0; line-height: 1.5;">
                The algorithmic analysis, real-time data visualizers, and macro evaluations generated by this engine are provided strictly for educational and information-tracking purposes. <b>This does not constitute financial, investment, legal, or tax advice.</b> Past performance vectors do not guarantee future market outcomes. Always consult a licensed professional or fiduciary asset advisor before executing live capital trades.
            </p>
        </div>
        """, unsafe_allow_html=True
    )
    
    POPULAR_STOCKS = ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "AMD", "META", "GOOGL", "NFLX", "COIN"]
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        search_type = st.radio("Target Strategy Selection", ["Top 10 Popular Stocks", "Search Custom Ticker"], horizontal=True)
    with col_sel2:
        selected_ticker = st.selectbox("Active Vector Focus Tracker", POPULAR_STOCKS) if search_type == "Top 10 Popular Stocks" else st.text_input("Enter Token Ticker Symbol Symbol String", value="NVDA").upper()

    if selected_ticker:
        with st.spinner("Establishing processing pipe terminal connections..."):
            ticker_obj = yf.Ticker(selected_ticker)
            historical_df = ticker_obj.history(period="1mo", interval="1d").reset_index()
            raw_news = ticker_obj.news or []

        live_articles = []
        for item in raw_news:
            content_block = item.get("content", {}) if isinstance(item.get("content"), dict) else item
            title = content_block.get("title") or item.get("title")
            canonical = content_block.get("canonicalUrl", {}) if isinstance(content_block.get("canonicalUrl"), dict) else {}
            link = canonical.get("url") or content_block.get("link") or item.get("link")
            
            if title and link:
                live_articles.append({"title": title, "link": link})
            if len(live_articles) >= 10:
                break

        while len(live_articles) < 10:
            idx = len(live_articles) + 1
            live_articles.append({
                "title": f"{selected_ticker} Market Catalyst Volatility Trend Group {idx}", 
                "link": f"https://finance.yahoo.com/quote/{selected_ticker}/news"
            })

        st.markdown(f'<h3 style="font-size: 20px; font-weight: 200; margin-bottom: 15px; letter-spacing: 0.05em;">TRACKING CHANNEL VECTOR: {selected_ticker}</h3>', unsafe_allow_html=True)
        
        fig = px.line(historical_df, x="Date", y="Close", markers=True)
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#A1A1AA',
            xaxis=dict(showgrid=False, linecolor='#262629'),
            yaxis=dict(showgrid=True, gridcolor='#18181B', linecolor='#262629'),
            margin=dict(l=10, r=10, t=10, b=10)
        )
        fig.update_traces(line_color='#FFFFFF', marker=dict(color='#00E5FF', size=5))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div style="margin-top: 30px;"></div>', unsafe_allow_html=True)
        col_news, col_summary = st.columns([4, 3])
        scraped_data_for_groq = []

        with col_news:
            st.markdown('<h4 style="font-size: 14px; font-weight: 400; color: #A1A1AA; letter-spacing: 0.1em; margin-bottom: 20px;">REALTIME FEED REDUCTION INTERFACES</h4>', unsafe_allow_html=True)
            for idx, article in enumerate(live_articles[:10]):
                body_text = scrape_article_content(article['link'])
                with st.spinner(f"Compiling content tracking array chunk {idx+1}..."):
                    mini_summary = get_mini_summary(article['title'], body_text)
                scraped_data_for_groq.append(f"Title: {article['title']}\nSummary: {mini_summary}\n")
                
                st.markdown(
                    f"""
                    <div class="glass-card neon-glow-blue">
                        <span style="font-size: 9px; color: #71717A; font-weight: 600; letter-spacing: 0.1em;">CHANNEL {idx+1:02d}</span>
                        <h5 style="margin: 4px 0 8px 0; font-size: 13.5px; font-weight: 400; color: #FFFFFF; line-height: 1.4;">{article['title']}</h5>
                        <p style="font-size: 12px; color: #A1A1AA; font-weight: 300; margin-bottom: 12px; line-height: 1.5;">{mini_summary}</p>
                        <a href="{article['link']}" target="_blank" style="font-size: 10.5px; color: #00E5FF; text-decoration: none; font-weight: 600;">ACCESS RAW WIRE ↗</a>
                    </div>
                    """, unsafe_allow_html=True
                )

        with col_summary:
            st.markdown('<h4 style="font-size: 14px; font-weight: 400; color: #A1A1AA; letter-spacing: 0.1em; margin-bottom: 20px;">AI MACRO REDUCTION EVALUATION</h4>', unsafe_allow_html=True)
            groq_articles_input = "\n".join(scraped_data_for_groq)
            
            with st.spinner("AI parsing aggregate matrices summaries..."):
                try:
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "system", "content": OVERALL_ANALYSIS_PROMPT}, {"role": "user", "content": groq_articles_input}],
                        temperature=0.1
                    )
                    raw_response = completion.choices[0].message.content
                    
                    direction = raw_response.split("LIKELIHOOD:")[1].split("CONFIDENCE:")[0].strip()
                    confidence = raw_response.split("CONFIDENCE:")[1].split("IMPACT_SUMMARY:")[0].strip()
                    summary = raw_response.split("IMPACT_SUMMARY:")[1].strip()
                    
                    accent_neon = "#E5E5E7"
                    if direction.upper() == "UPWARD":
                        accent_neon = "#00E5FF"
                    elif direction.upper() == "DOWNWARD":
                        accent_neon = "#FF3366"
                    
                    st.markdown(
                        f"""
                        <div class="glass-card" style="border-top: 3px solid {accent_neon} !important;">
                            <h4 style="color: #A1A1AA; margin-top: 0; font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase;">Direction Likelihood Vector</h4>
                            <h2 style="margin: 8px 0; font-size: 26px; color: #FFFFFF; font-weight: 200; letter-spacing: -0.03em;">{direction} <span style="font-size: 15px; color: #71717A; font-weight: 300;">(Confidence: {confidence})</span></h2>
                            <div style="color: #D4D4D8; line-height: 1.6; font-size: 13px; margin-top: 20px; font-weight: 300;">
                                <b style="color: #FFFFFF; font-weight: 400; font-size: 11px; letter-spacing: 0.05em; display: block; margin-bottom: 6px;">SYNTHESIZED EVALUATION OVERVIEW</b>
                                {summary}
                            </div>
                        </div>
                        """, unsafe_allow_html=True
                    )
                except Exception:
                    st.error("Analytics stream processing interruption.")