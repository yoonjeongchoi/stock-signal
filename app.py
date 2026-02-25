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
# We define custom CSS for horizontal menu and overall styling
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: #f2f4f6; }
    
    /* Make the menu buttons look like tabs */
    div.stButton > button:first-child {
        width: 100%;
        border-radius: 0;
        border: none;
        background-color: transparent;
        border-bottom: 2px solid transparent;
        font-weight: bold;
    }
    div.stButton > button:hover {
        border-bottom: 2px solid #007bff;
        color: #007bff;
    }
    
    /* Admin Login Box Styling */
    .admin-login-box {
        padding: 10px;
        background-color: white;
        border-radius: 8px;
        border: 1px solid #ddd;
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
            st.warning("세션이 만료되었습니다. 다시 로그인 해 주세요.")

# --- Views ---
def render_user_view():
    st.subheader("📊 오늘의 시그널")
    
    # Controls
    col_date, col_market, col_info = st.columns([1.5, 2, 4])

    with col_date:
        kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        default_date = kst_now.date()
        selected_date = st.date_input("날짜 선택", default_date)
        date_str = selected_date.strftime("%Y-%m-%d")

    with col_market:
        selected_market = st.selectbox("시장", ["🇰🇷 국내 주식", "🇺🇸 미국 주식"])

    market_prefix = "us_" if selected_market == "🇺🇸 미국 주식" else ""
    data = load_data(f"{market_prefix}{date_str}")
    
    last_updated = data.get("last_updated", "N/A") if data else "데이터 없음"
    
    with col_info:
        if data:
            st.write("") # padding
            st.caption(f"⏱ 마지막 업데이트: {last_updated}")
            
    st.markdown("---")

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

def render_admin_view():
    st.subheader("⚙️ 관리자 화면")
    st.markdown("크롤링 데이터 생성 트래거 및 JSON 타겟 스키마(KR/US 시장)를 직접 관리할 수 있습니다.")
    
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


def render_header_nav():
    # 1. Title and Login Logic
    col_head1, col_head2 = st.columns([7, 3])
    with col_head1:
        st.title("📈 시그널")
        st.caption("토스증권 AI가 핵심 시그널을 찾았어요")
    
    with col_head2:
        st.write("") # Padding
        st.write("") # Padding
        if not st.session_state["admin_logged_in"]:
            with st.expander("🔑 관리자 로그인"):
                pwd_input = st.text_input("Password", type="password", key="login_pwd")
                if st.button("로그인"):
                    if pwd_input == ADMIN_PASSWORD:
                        st.session_state["admin_logged_in"] = True
                        st.session_state["login_time"] = datetime.datetime.now()
                        st.experimental_rerun()
                    else:
                        st.error("비밀번호가 틀렸습니다.")
        else:
            login_time = st.session_state["login_time"]
            expire_time = login_time + datetime.timedelta(minutes=30)
            
            st.markdown(f"<div style='text-align: right;'><span style='color: #888; font-size: 0.8rem;'>세션 만료: {expire_time.strftime('%H:%M:%S')}</span></div>", unsafe_allow_html=True)
            
            # Un-nested button layout
            if st.button("로그아웃", key="logout_btn"):
                st.session_state["admin_logged_in"] = False
                st.session_state["current_view"] = "주식 시그널" # Reset to default view
                st.experimental_rerun()

    # 2. Horizontal Navigation Menu
    menu_options = ["주식 시그널", "관련 주식 조회/검색"]
    if st.session_state["admin_logged_in"]:
        menu_options.append("관리자 화면")
        
    num_cols = len(menu_options)
    # Give columns some gap if possible to simulate horizontal flex
    cols = st.columns(num_cols)
    
    for i, option in enumerate(menu_options):
        with cols[i]:
            # Highlight current menu selection by making it look active
            current_opt = st.session_state["current_view"]
            label = f"🟢 {option}" if current_opt == option else f"{option}"
            if st.button(label, key=f"nav_{option}"):
                st.session_state["current_view"] = option
                st.experimental_rerun()

    st.markdown("---")

# --- Main Flow ---
def main():
    if "current_view" not in st.session_state:
        st.session_state["current_view"] = "주식 시그널"
    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"] = False

    check_auth()
    render_header_nav()

    # View Router
    view = st.session_state.get("current_view", "주식 시그널")
    
    if view == "주식 시그널":
        render_user_view()
    elif view == "관련 주식 조회/검색":
        render_search_view()
    elif view == "관리자 화면" and st.session_state["admin_logged_in"]:
        render_admin_view()
    else:
        st.session_state["current_view"] = "주식 시그널"
        st.experimental_rerun()
        
    # Auto-refresh logic (ONLY if we are in the main User view)
    if view == "주식 시그널":
        import streamlit.components.v1 as components
        components.html(
            """
            <script>
            setTimeout(function(){
                window.parent.location.reload();
            }, 1200000);
            </script>
            """,
            height=0
        )

if __name__ == "__main__":
    main()
