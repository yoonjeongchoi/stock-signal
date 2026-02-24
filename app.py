import streamlit as st
import json
import os
import datetime
import crawler

# --- Configuration & Setup ---
st.set_page_config(
    page_title="시그널 - 실시간 핫이슈",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Minimal CSS ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: #f2f4f6; }
</style>
""", unsafe_allow_html=True)

# --- Data Loading ---
DATA_DIR = "data"

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

# --- Main UI ---
def main():
    # Header
    st.title("📈 시그널")
    st.caption("토스증권 AI가 핵심 시그널을 찾았어요")

    # Controls
    col_date, col_market, col_info, col_refresh = st.columns([1.5, 2, 4, 2.5])

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
            
    with col_refresh:
        st.write("") # padding
        if st.button("🚀 시그널 데이터 생성하기"):
            with st.spinner(f"{date_str}의 공시와 뉴스를 분석하여 시그널을 생성 중입니다... (약 1~2분 소요)"):
                try:
                    market_arg = "US" if selected_market == "🇺🇸 미국 주식" else "KR"
                    success = crawler.generate_daily_json(date_str, market=market_arg)
                    if success:
                        st.success(f"{date_str} 데이터 생성 완료!")
                        st.rerun()
                    else:
                        st.error("데이터 생성에 실패했습니다.")
                except Exception as e:
                    st.error(f"오류 발생: {e}")

    st.markdown("---")

    if not data:
        st.info(f"{date_str}의 시그널 데이터가 아직 없습니다. 상단의 '시그널 데이터 생성하기' 버튼을 눌러주세요.")
        return

    signals = data.get("signals", [])
    if not signals:
        st.warning("수집된 시그널 정보가 없습니다.")
        return

    # --- Render each signal as a horizontal row ---
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

    # Auto-refresh page every 20 minutes (1,200,000 milliseconds)
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
