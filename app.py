import streamlit as st
import json
import os
import datetime
import crawler
import pandas as pd
import FinanceDataReader as fdr
from dotenv import load_dotenv

load_dotenv()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DATA_DIR = "data"
STOCK_METADATA_FILE = os.path.join(DATA_DIR, "stock_metadata.json")

# --- Configuration & Setup ---
st.set_page_config(
    page_title="시그널 - 실시간 핫이슈",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Minimal CSS ---
# Integrated professional CSS for sticky header, modals, and card layouts
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Global Background */
    .stApp { background-color: #f7f9fb !important; }

    /* Hide default streamlit header */
    [data-testid="stHeader"] {
        display: none;
    }
    
    /* Unified Sticky Header */
    .unified-sticky-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background-color: white;
        z-index: 1000;
        border-bottom: 1px solid #e5e7eb;
    }
    
    .top-bar {
        height: 45px;
        padding: 0 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid #f3f4f6;
    }
    
    .nav-bar {
        height: 38px;
        padding: 0 20px;
        display: flex;
        align-items: center;
    }

    /* Modal / Alert Overlay */
    .overlay-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-color: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(8px);
        z-index: 9999;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    .modal-box {
        background-color: white;
        padding: 40px;
        border-radius: 20px;
        width: 90%;
        max-width: 420px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
        text-align: center;
        animation: fadeIn 0.3s ease-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* Card Styling */
    .content-card {
        background-color: white;
        padding: 30px;
        border-radius: 20px;
        border: 1px solid #eef2f6;
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.05);
        margin-bottom: 30px;
        transition: transform 0.2s ease;
    }
    .content-card:hover {
        box-shadow: 0 12px 20px rgba(0, 0, 0, 0.08);
    }
    
    /* Fixed header spacer - dynamic height via session state is hard in pure CSS, 
       so we use a default or handle it in the script */
    .fixed-header-spacer {
        height: 85px; /* Default for non-signal views */
    }
    .fixed-header-spacer-signal {
        height: 185px; /* Taller for signal view with controls */
    }
    
    .sticky-controls-row {
        padding: 10px 25px;
        background-color: white;
        border-bottom: 1px solid #e5e7eb;
    }
    
    /* Button Styling */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 600 !important;
    }
    
    /* Nav Tab Styling - Streamlit button overrides */
    .nav-bar div[data-testid="stVerticalBlock"] > div {
        margin-top: -10px;
    }
    .nav-btn > div > button {
        border: none !important;
        background-color: transparent !important;
        border-radius: 0 !important;
        border-bottom: 3px solid transparent !important;
        color: #6b7280 !important;
        height: 38px !important;
        font-size: 0.9rem !important;
        padding: 0 12px !important;
        transition: all 0.2s ease !important;
    }
    .nav-btn-active > div > button {
        border-bottom: 3px solid #0070f3 !important;
        color: #0070f3 !important;
        background-color: rgba(0, 112, 243, 0.05) !important;
    }
    .nav-btn > div > button:hover {
        color: #111 !important;
        background-color: #f9fafb !important;
    }

    /* Tag Styling */
    .signal-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 5px;
        margin-bottom: 5px;
    }
    .tag-industry {
        background-color: #f1f5f9;
        color: #475569;
        border: 1px solid #e2e8f0;
    }
    .tag-type {
        background-color: #fff7ed;
        color: #c2410c;
        border: 1px solid #fed7aa;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Loading Functions ---
def load_data(date_str):
    file_path = os.path.join(DATA_DIR, f"{date_str}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def format_rate(rate_str):
    """Return emoji + rate text"""
    if not rate_str:
        return "0.0%"
    if rate_str.startswith("+"):
        return f"🔴 {rate_str}"
    elif rate_str.startswith("-"):
        return f"🔵 {rate_str}"
    return rate_str

@st.cache(ttl=600, show_spinner=False)
def load_stock_metadata():
    if os.path.exists(STOCK_METADATA_FILE):
        with open(STOCK_METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"KR": {}, "US": {}}

def save_stock_metadata(data):
    os.makedirs(os.path.dirname(STOCK_METADATA_FILE), exist_ok=True)
    with open(STOCK_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def fetch_index_stocks(index_name):
    try:
        df = fdr.StockListing(index_name)
        return df
    except Exception as e:
        st.error(f"Error fetching {index_name}: {e}")
        return pd.DataFrame()

# --- Auth Logic ---
def check_auth():
    now = datetime.datetime.now()
    if st.session_state.get("admin_logged_in"):
        login_time = st.session_state.get("login_time")
        if login_time and (now - login_time).total_seconds() > 1800: # 30 mins
            st.session_state["admin_logged_in"] = False
            st.session_state["current_view"] = "주식 시그널"
            st.session_state["alert_message"] = "세션이 만료되었습니다. 다시 로그인 해 주세요."
            st.session_state["show_alert"] = True

# --- UI Components ---

def render_overlay_modals():
    """Render centered modals for alerts and login"""
    # 1. Generic Alert Modal
    if st.session_state.get("show_alert"):
        st.markdown(f"""
            <div class="overlay-container">
                <div class="modal-box">
                    <div style="font-size: 3rem; margin-bottom: 10px;">💡</div>
                    <h3 style="color: #111; margin-bottom: 15px;">알림</h3>
                    <p style="margin: 0 0 30px 0; font-size: 1.1rem; color: #444; line-height: 1.5;">{st.session_state['alert_message']}</p>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        _, col_btn, _ = st.columns([1.2, 1, 1.2])
        with col_btn:
            if st.button("확인", key="close_alert_btn"):
                st.session_state["show_alert"] = False
                st.experimental_rerun()

    # 2. Login Modal
    if st.session_state.get("show_login_modal"):
        st.markdown("""
            <div class="overlay-container">
                <div class="modal-box">
                    <div style="font-size: 3rem; margin-bottom: 10px;">🔑</div>
                    <h3 style="color: #111; margin-bottom: 5px;">관리자 로그인</h3>
                    <p style="color: #666; margin-bottom: 25px;">서비스 관리를 위해 비밀번호를 입력해주세요.</p>
                </div>
            </div>
        """, unsafe_allow_html=True)
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            pwd_input = st.text_input("비밀번호", type="password", key="modal_login_pwd")
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                if st.button("로그인"):
                    if pwd_input == ADMIN_PASSWORD:
                        st.session_state["admin_logged_in"] = True
                        st.session_state["login_time"] = datetime.datetime.now()
                        st.session_state["show_login_modal"] = False
                        st.session_state["alert_message"] = "로그인되었습니다."
                        st.session_state["show_alert"] = True
                        st.experimental_rerun()
                    else:
                        st.error("비밀번호 불일치")
            with col_l2:
                if st.button("취소"):
                    st.session_state["show_login_modal"] = False
                    st.experimental_rerun()

# --- Views ---
def render_user_view(data, date_str, selected_market):
    # Data check (Controls are now in the header)
    if not data:
        st.info(f"{date_str}의 시그널 데이터가 아직 없습니다.")
        return

    signals = data.get("signals", [])
    if not signals:
        st.warning("수집된 시그널 정보가 없습니다.")
        return

    # --- Render each signal as a horizontal row (Copy-pasted from original app.py) ---
    for signal in signals:
        theme = signal.get("theme", "")
        short_reason = signal.get("short_reason", "")
        summary = signal.get("summary", "")
        main_stock = signal.get("main_stock", {})
        related_stocks = signal.get("related_stocks", [])
        news_articles = signal.get("news_articles", [])
        analyst_data = signal.get("analyst_data", None)

        m_name = main_stock.get("name", "알 수 없음")
        m_rate = main_stock.get("change_rate", "0.0%")
        m_symbol = main_stock.get("symbol", "")
        m_url = main_stock.get("news_url", "#")
        signal_type = signal.get("signal_type", "이슈")

        # Custom CSS for card-like styling
        st.markdown("""
            <style>
            .stExpander {
                border: 1px solid #f0f2f6;
                border-radius: 12px;
                margin-bottom: 10px;
                background-color: white;
            }
            .time-tag {
                float: right;
                color: #888;
                font-size: 0.8rem;
            }
            .reason-text {
                color: #555;
                font-size: 0.95rem;
                margin-top: -10px;
                margin-bottom: 15px;
            }
            .translated-title {
                font-weight: bold;
                font-size: 1.05rem;
                color: #1f2937;
                margin-top: 10px;
                margin-bottom: 8px;
            }
            </style>
        """, unsafe_allow_html=True)

        # Determine time_ago tag natively in KST
        sig_ts_str = signal.get("timestamp")
        if sig_ts_str:
            try:
                sig_ts = datetime.datetime.strptime(sig_ts_str, "%Y-%m-%d %H:%M:%S")
                # Now that all JSON uses KST explicitly, we compare with KST now
                now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
                diff = now - sig_ts
                hours = diff.total_seconds() // 3600
                minutes = diff.total_seconds() // 60
                
                if selected_market == "🇰🇷 국내 주식":
                    is_market_open = now.weekday() < 5 and (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 30))
                    is_sig_after_close = sig_ts.hour > 15 or (sig_ts.hour == 15 and sig_ts.minute >= 30)
                else: # US Stock market hours approx 23:30 to 06:00 KST
                    is_market_open = now.weekday() < 5 and (now.hour >= 23 or now.hour < 6)
                    is_sig_after_close = sig_ts.hour >= 6 and sig_ts.hour < 15
                
                if not is_market_open or date_str != now.strftime("%Y-%m-%d"):
                    if sig_ts.date() != now.date():
                        time_ago = sig_ts.strftime("%m.%d 종가 기준")
                    elif is_sig_after_close:
                        time_ago = "당일 종가 기준"
                    else:
                        time_ago = sig_ts.strftime("%H:%M 기준")
                else:
                    if minutes < 60:
                        time_ago = "방금 전" if minutes < 5 else f"{int(minutes)}분 전"
                    elif hours < 24:
                        time_ago = f"{int(hours)}시간 전"
                    else:
                        time_ago = sig_ts.strftime("%H:%M 기준")
            except Exception as e:
                time_ago = "업데이트 완료"
        else:
            time_ago = "업데이트 완료"

        # Layout: Left = main stock card, Middle = arrow, Right = related stocks
        col_main, col_arrow, col_related = st.columns([3, 1, 4])

        with col_main:
            expander_label = f"{m_name} : {format_rate(m_rate)}"
            
            with st.expander(expander_label, expanded=False):
                st.markdown(f"<span class='time-tag'>{time_ago}</span>", unsafe_allow_html=True)
                
                # Render Tags (Industry & Signal Type)
                tag_html = ""
                if theme:
                    tag_html += f"<span class='signal-tag tag-industry'>{theme}</span>"
                if signal_type:
                    tag_html += f"<span class='signal-tag tag-type'>{signal_type}</span>"
                
                if tag_html:
                    st.markdown(tag_html, unsafe_allow_html=True)

                st.markdown(f"### <a href='{m_url}' target='_blank' style='text-decoration: none; color: inherit;'>{m_name}</a>", unsafe_allow_html=True)
                
                # Display the AI-generated short reason as a sub-headline
                st.markdown(f"<div class='reason-text'>{short_reason}</div>", unsafe_allow_html=True)
                
                # AI Summary Section
                question = "왜 내렸을까? 📉" if m_rate.startswith("-") else "왜 올랐을까? 🤖"
                st.markdown(f"**{question}**")
                # Summary is now consistently formatted string from backend 
                st.write(str(summary))

                st.markdown("---")
                
                # News articles list - Dynamic Limit based on market
                st.markdown("**📰 뉴스·정보**")
                if news_articles:
                    limit = 5 if selected_market == "🇺🇸 미국 주식" else 3
                    for article in news_articles[:limit]: 
                        title = article.get("title", "")
                        url = article.get("url", "#")
                        date_str_article = article.get("date", "")
                        source = article.get("source", "")
                        # Raw date format directly from crawler
                        clean_date = date_str_article
                        
                        # Fix for existing unparsed strings
                        if "+0000" in clean_date or "GMT" in clean_date:
                            try:
                                import email.utils
                                dt = email.utils.parsedate_to_datetime(clean_date)
                                dt_kst = dt.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
                                clean_date = dt_kst.strftime("%m.%d %H:%M")
                            except Exception:
                                pass
                        source_text = f" ({source})" if source else ""
                        # Simplify markdown rendering so it doesn't break
                        st.markdown(f"• [{title}]({url})")
                        if clean_date or source_text:
                            st.markdown(f"<span style='color:#999;font-size:0.8rem; margin-left: 15px;'>{clean_date}{source_text}</span>", unsafe_allow_html=True)
                else:
                    st.write("관련 뉴스가 없습니다.")

        with col_arrow:
            st.markdown("<br><br><h2 style='text-align:center; color:#ccc;'>→</h2>", unsafe_allow_html=True)

        with col_related:
            # Related stocks displayed as compact list with some styling
            if related_stocks:
                for rs in related_stocks:
                    r_name = rs.get("name", "")
                    r_rate = rs.get("change_rate", "0.0%")
                    st.markdown(f"• **{r_name}** {format_rate(r_rate)}")

        st.markdown("---")


def render_search_view():
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.subheader("🔍 관련 주식 조회/검색")
    
    st.markdown("#### 시장 지수 구성종목 조회")
    st.markdown("FinanceDataReader를 이용하여 전세계 시장 지수의 편입 종목 리스트를 조회합니다.")
    
    idx_option = st.selectbox("조회할 지수 선택", ["S&P500", "NASDAQ", "KOSPI", "KOSDAQ"])
    if st.button(f"{idx_option} 종목 가져오기"):
        with st.spinner(f"Fetching {idx_option} data..."):
            df = fetch_index_stocks(idx_option)
            if not df.empty:
                st.success(f"총 {len(df)}개의 종목을 불러왔습니다.")
                st.dataframe(df)
            else:
                st.warning("데이터를 불러오지 못했습니다.")
    st.markdown('</div>', unsafe_allow_html=True)

def render_admin_view():
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.subheader("⚙️ 관리자 화면")
    st.markdown("크롤링 데이터 생성 트래거 및 JSON 타겟 스키마(KR/US 시장)를 직접 관리할 수 있습니다.")
    
    if st.button("🔄 종목 스키마 수동 업데이트 (Reload Metadata)"):
        import streamlit.legacy_caching
        streamlit.legacy_caching.clear_cache()
        st.success("메타데이터 캐시가 초기화되었습니다. 최신 정보를 불러옵니다.")
        st.experimental_rerun()
    
    # 1. Crawler trigger
    st.markdown("### 1. 시그널 데이터 생성 (수동 크롤링)")
    col_date, col_market, col_button = st.columns([2, 2, 4])
    with col_date:
        kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        date_str = st.date_input("생성 기준 일자", kst_now.date()).strftime("%Y-%m-%d")
    with col_market:
        admin_market = st.selectbox("크롤링 시장", ["KR", "US"])
    with col_button:
        st.write("") # Padding
        if st.button("🚀 데이터 강제 생성 (1~2분 소요)"):
            with st.spinner(f"{date_str}의 {admin_market} 시장 데이터를 수집하고 생성 중입니다..."):
                try:
                    success = crawler.generate_daily_json(date_str, market=admin_market)
                    if success:
                        st.success(f"{date_str} {admin_market} 데이터 생성 완료!")
                    else:
                        st.error("데이터 생성 실패.")
                except Exception as e:
                    st.error(f"오류: {e}")
                    
    st.markdown("---")
    
    # 2. JSON configuration
    st.markdown("### 2. 타겟 종목 스키마 관리")
    st.markdown("Streamlit 0.89 환경에서는 텍스트(JSON)로 직접 편집합니다.")
    
    data = load_stock_metadata()
    market_select = st.selectbox("관리할 시장 선택", ["KR Market", "US Market"])
    
    if market_select == "KR Market":
        kr_data = data.get("KR", {})
        kr_json_str = json.dumps(kr_data, ensure_ascii=False, indent=4)
        edited_kr_json = st.text_area("KR 종목 JSON 데이터", value=kr_json_str, height=400)
        if st.button("변경사항 저장 (KR)", key="kr_save"):
            try:
                data['KR'] = json.loads(edited_kr_json)
                save_stock_metadata(data)
                st.success("한국 종목 데이터가 저장되었습니다! (crawler.py에 즉시 반영됨)")
            except Exception as e:
                st.error(f"데이터 저장 실패: 올바른 JSON 포맷인지 확인해 주세요. ({e})")
                
    elif market_select == "US Market":
        us_data = data.get("US", {})
        us_json_str = json.dumps(us_data, ensure_ascii=False, indent=4)
        edited_us_json = st.text_area("US 종목 JSON 데이터", value=us_json_str, height=400)
        if st.button("변경사항 저장 (US)", key="us_save"):
            try:
                data['US'] = json.loads(edited_us_json)
                save_stock_metadata(data)
                st.success("미국 종목 데이터가 저장되었습니다! (crawler.py에 즉시 반영됨)")
            except Exception as e:
                st.error(f"데이터 저장 실패: 올바른 JSON 포맷인지 확인해 주세요. ({e})")
    st.markdown('</div>', unsafe_allow_html=True)


def render_header_nav():
    """Render consolidated sticky header and navigation"""
    # 1. Unified Sticky Header Wrapper
    st.markdown('<div class="unified-sticky-header">', unsafe_allow_html=True)
    
    # 1a. Top Bar (Logo & Auth)
    st.markdown("""
        <div class="top-bar">
            <div style="display: flex; align-items: baseline; gap: 10px;">
                <h2 style="margin:0; font-size: 1.25rem; color: #111; letter-spacing: -0.5px;">📈 시그널</h2>
                <span style="color: #6b7280; font-size: 0.8rem; font-weight: 500;">AI 주식 분석</span>
            </div>
            <div id="auth-section"></div>
        </div>
    """, unsafe_allow_html=True)
    
    # Position Auth Buttons
    auth_container = st.container()
    with auth_container:
        _, col_auth = st.columns([8.2, 1.8])
        with col_auth:
            st.markdown("<div style='margin-top: -38px;'></div>", unsafe_allow_html=True)
            if not st.session_state["admin_logged_in"]:
                if st.button("🔑 로그인", key="header_login_btn"):
                    st.session_state["show_login_modal"] = True
                    st.experimental_rerun()
            else:
                if st.button("👤 로그아웃", key="header_logout_btn"):
                    st.session_state["admin_logged_in"] = False
                    st.session_state["current_view"] = "주식 시그널"
                    st.session_state["alert_message"] = "로그아웃되었습니다."
                    st.session_state["show_alert"] = True
                    st.experimental_rerun()

    # 1b. Navigation Bar
    st.markdown('<div class="nav-bar">', unsafe_allow_html=True)
    menu_options = ["주식 시그널", "관련 주식 조회/검색"]
    if st.session_state["admin_logged_in"]:
        menu_options.append("관리자 화면")
        
    cols = st.columns(len(menu_options) + 5)
    current_opt = st.session_state["current_view"]
    
    for i, option in enumerate(menu_options):
        with cols[i]:
            is_active = (current_opt == option)
            btn_class = "nav-btn-active" if is_active else "nav-btn"
            st.markdown(f'<div class="{btn_class}">', unsafe_allow_html=True)
            if st.button(option, key=f"nav_{option}"):
                st.session_state["current_view"] = option
                st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True) # close nav-bar

    # 1c. Signal View Specific Controls (Sticky)
    data_to_return = None
    date_str_to_return = None
    market_to_return = "🇰🇷 국내 주식" # Default
    
    if current_opt == "주식 시그널":
        st.markdown('<div class="sticky-controls-row">', unsafe_allow_html=True)
        # Add a bit of top margin to position controls "slightly above middle" of the sticky block
        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
        st.subheader("📊 오늘의 시그널")
        
        col_date, col_market, col_info = st.columns([1.5, 2, 3.5])
        with col_date:
            kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
            default_date = kst_now.date()
            selected_date = st.date_input("날짜 선택", default_date)
            date_str_to_return = selected_date.strftime("%Y-%m-%d")

        with col_market:
            market_to_return = st.selectbox("시장", ["🇰🇷 국내 주식", "🇺🇸 미국 주식"])

        market_prefix = "us_" if market_to_return == "🇺🇸 미국 주식" else ""
        data_to_return = load_data(f"{market_prefix}{date_str_to_return}")
        last_updated = data_to_return.get("last_updated", "N/A") if data_to_return else "데이터 없음"
        
        with col_info:
            if data_to_return:
                st.write("") # padding
                st.caption(f"⏱ 마지막 업데이트: {last_updated}")
        
        st.markdown('</div>', unsafe_allow_html=True) # close sticky-controls-row

    st.markdown('</div>', unsafe_allow_html=True) # close unified-sticky-header
    return data_to_return, date_str_to_return, market_to_return

# --- Main Flow ---
def main():
    if "current_view" not in st.session_state:
        st.session_state["current_view"] = "주식 시그널"
    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"] = False
    if "show_alert" not in st.session_state:
        st.session_state["show_alert"] = False
    if "alert_message" not in st.session_state:
        st.session_state["alert_message"] = ""
    if "show_login_modal" not in st.session_state:
        st.session_state["show_login_modal"] = False

    check_auth()
    render_overlay_modals()
    
    view = st.session_state.get("current_view", "주식 시그널")
    
    # Render header and get data if needed
    data, date_str, market = render_header_nav()
    
    # Padding for sticky header
    spacer_class = "fixed-header-spacer-signal" if view == "주식 시그널" else "fixed-header-spacer"
    st.markdown(f"<div class='{spacer_class}'></div>", unsafe_allow_html=True)

    # View Router
    view = st.session_state.get("current_view", "주식 시그널")
    
    if view == "주식 시그널":
        render_user_view(data, date_str, market)
    elif view == "관련 주식 조회/검색":
        render_search_view()
    elif view == "관리자 화면" and st.session_state["admin_logged_in"]:
        render_admin_view()
    else:
        st.session_state["current_view"] = "주식 시그널"
        st.experimental_rerun()
        
    # Auto-refresh & Focus Top logic
    if view == "주식 시그널":
        import streamlit.components.v1 as components
        components.html(
            """
            <script>
            // Force scroll to top on load
            window.parent.scrollTo(0, 0);
            
            // Auto-refresh every 20 minutes
            setTimeout(function(){
                window.parent.location.reload();
            }, 1200000);
            </script>
            """,
            height=0
        )

if __name__ == "__main__":
    main()
