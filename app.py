import streamlit as st
import json
import os
import datetime
import crawler
import pandas as pd
import FinanceDataReader as fdr
from dotenv import load_dotenv

# --- Initialization ---
load_dotenv()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DATA_DIR = "data"
STOCK_METADATA_FILE = os.path.join(DATA_DIR, "stock_metadata.json")

# --- Streamlit Config (0.89.0 Compatible) ---
st.set_page_config(
    page_title="시그널 - 실시간 핫이슈",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded" # Keep sidebar open for fixed controls
)

# --- CSS Styling ---
st.markdown("""
<style>
    /* Hide top padding */
    .main .block-container {
        padding-top: 2rem;
    }
    
    /* Card Styling */
    .content-card {
        background-color: white;
        padding: 25px;
        border-radius: 15px;
        border: 1px solid #eef2f6;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
        margin-bottom: 25px;
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
    
    /* Navigation Row Styling */
    .nav-row {
        margin-bottom: 30px;
        border-bottom: 1px solid #eee;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Loading (0.89.0 Compatible st.cache) ---
@st.cache(ttl=600, show_spinner=False)
def load_data(date_str):
    file_path = os.path.join(DATA_DIR, f"{date_str}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None

@st.cache(ttl=600, show_spinner=False)
def load_stock_metadata():
    if os.path.exists(STOCK_METADATA_FILE):
        try:
            with open(STOCK_METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"KR": {}, "US": {}}

def save_stock_metadata(data):
    os.makedirs(os.path.dirname(STOCK_METADATA_FILE), exist_ok=True)
    with open(STOCK_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def format_rate(rate_str):
    if not rate_str: return "0.0%"
    if rate_str.startswith("+"): return f"🔴 {rate_str}"
    elif rate_str.startswith("-"): return f"🔵 {rate_str}"
    return rate_str

# --- UI Components ---
def render_sidebar():
    """Fixed sidebar for settings and metadata management"""
    st.sidebar.title("📈 시그널 설정")
    
    # 1. Market & Date Selection (Always Fixed)
    st.sidebar.markdown("### 📊 조회 설정")
    market = st.sidebar.selectbox("시장 선택", ["🇰🇷 국내 주식", "🇺🇸 미국 주식"])
    
    kst_now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    selected_date = st.sidebar.date_input("날짜 선택", kst_now.date())
    date_str = selected_date.strftime("%Y-%m-%d")
    
    st.sidebar.markdown("---")
    
    # 2. Admin Logic
    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"] = False
        
    if not st.session_state["admin_logged_in"]:
        with st.sidebar.expander("🔑 관리자 로그인"):
            pwd = st.text_input("비밀번호", type="password")
            if st.button("로그인"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state["admin_logged_in"] = True
                    st.experimental_rerun()
                else:
                    st.error("비밀번호 불일치")
    else:
        st.sidebar.success("✅ 관리자 모드")
        if st.sidebar.button("👤 로그아웃"):
            st.session_state["admin_logged_in"] = False
            st.experimental_rerun()
            
    return market, date_str

def render_navigation():
    """Simple horizontal navigation menu"""
    if "current_view" not in st.session_state:
        st.session_state["current_view"] = "주식 시그널"
        
    options = ["주식 시그널", "관련 주식 조회"]
    if st.session_state["admin_logged_in"]:
        options.append("관리자 도구")
        
    cols = st.columns(len(options))
    for i, opt in enumerate(options):
        # highlight current view logic can be added here with custom markdown if needed
        if cols[i].button(opt, key=f"nav_{opt}"):
            st.session_state["current_view"] = opt
            st.experimental_rerun()
    st.markdown("<hr style='margin-top:0'>", unsafe_allow_html=True)

# --- Views ---
def view_signals(market_name, date_str):
    market_prefix = "us_" if market_name == "🇺🇸 미국 주식" else ""
    data = load_data(f"{market_prefix}{date_str}")
    
    if not data:
        st.info(f"{date_str}의 시그널 데이터가 없습니다.")
        return

    st.subheader(f"📊 {market_name} 시그널 ({date_str})")
    st.caption(f"마지막 업데이트: {data.get('last_updated', 'N/A')}")
    
    for signal in data.get("signals", []):
        with st.container():
            col_main, col_related = st.columns([3, 2])
            
            with col_main:
                # Main Signal Card
                theme = signal.get("theme", "")
                signal_type = signal.get("signal_type", "")
                m_stock = signal.get("main_stock", {})
                
                # Tags
                tag_html = ""
                if theme: tag_html += f"<span class='signal-tag tag-industry'>{theme}</span>"
                if signal_type: tag_html += f"<span class='signal-tag tag-type'>{signal_type}</span>"
                if tag_html: st.markdown(tag_html, unsafe_allow_html=True)
                
                m_label = f"### {m_stock.get('name')} : {format_rate(m_stock.get('change_rate'))}"
                st.markdown(m_label)
                st.markdown(f"**{signal.get('short_reason')}**")
                st.write(signal.get("summary"))
                
                with st.expander("뉴스/정보 확인"):
                    for art in signal.get("news_articles", [])[:5]:
                        st.markdown(f"• [{art['title']}]({art['url']}) ({art.get('source', '')})")
            
            with col_related:
                st.write("**관련 종목**")
                for rs in signal.get("related_stocks", []):
                    st.write(f"• {rs['name']} ({format_rate(rs['change_rate'])})")
            
            st.markdown("---")

def view_search():
    st.header("🔍 관련 주식 조회")
    idx = st.selectbox("시장 지수 선택", ["S&P500", "NASDAQ", "KOSPI", "KOSDAQ"])
    if st.button("조회 시작"):
        with st.spinner("조회 중..."):
            df = fdr.StockListing(idx)
            st.dataframe(df)

def view_admin():
    st.header("⚙️ 관리자 도구")
    
    # 1. Reload metadata cache
    if st.button("🔄 메타데이터 캐시 초기화"):
        try:
            import streamlit.legacy_caching
            streamlit.legacy_caching.clear_cache()
            st.success("캐시가 초기화되었습니다.")
        except:
            st.warning("캐시 초기화 중 오류가 발생했습니다.")
            
    st.markdown("---")
    
    # 2. Trigger Crawler
    st.subheader("🚀 시그널 생성 (크롤링 시작)")
    c_market = st.selectbox("대상 시장", ["KR", "US"])
    c_date = st.date_input("기준 날짜", datetime.datetime.now().date())
    if st.button("크롤링 실행"):
        with st.spinner("실행 중..."):
            res = crawler.generate_daily_json(c_date.strftime("%Y-%m-%d"), market=c_market)
            if res: st.success("생성 완료!")
            else: st.error("생성 실패.")

# --- Main Flow ---
def main():
    market, date_str = render_sidebar()
    render_navigation()
    
    view = st.session_state.get("current_view")
    if view == "주식 시그널":
        view_signals(market, date_str)
    elif view == "관련 주식 조회":
        view_search()
    elif view == "관리자 도구" and st.session_state["admin_logged_in"]:
        view_admin()
    else:
        st.session_state["current_view"] = "주식 시그널"
        st.experimental_rerun()

if __name__ == "__main__":
    main()
