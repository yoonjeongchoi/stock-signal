import os
import json
import datetime
from datetime import timedelta
import dotenv

import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
import traceback

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("google.generativeai module not found or broken. AI summaries will be mocked.")
except Exception as e:
    GENAI_AVAILABLE = False
    print(f"Error loading google.generativeai: {e}")

# Load environment variables (e.g., GEMINI_API_KEY)
dotenv.load_dotenv()

# Constants
DATA_DIR = "data"

# Standard list of major stocks to monitor (KOSPI 50 approx)
MAJOR_STOCKS = [
    {"symbol": "005930", "name": "삼성전자"},
    {"symbol": "000660", "name": "SK하이닉스"},
    {"symbol": "373220", "name": "LG에너지솔루션"},
    {"symbol": "207940", "name": "삼성바이오로직스"},
    {"symbol": "005380", "name": "현대차"},
    {"symbol": "000270", "name": "기아"},
    {"symbol": "068270", "name": "셀트리온"},
    {"symbol": "005490", "name": "POSCO홀딩스"},
    {"symbol": "035420", "name": "NAVER"},
    {"symbol": "035720", "name": "카카오"},
    {"symbol": "051910", "name": "LG화학"},
    {"symbol": "105560", "name": "KB금융"},
    {"symbol": "055550", "name": "신한지주"},
    {"symbol": "003550", "name": "LG"},
    {"symbol": "032830", "name": "삼성생명"},
    {"symbol": "000810", "name": "삼성화재"},
    {"symbol": "012330", "name": "현대모비스"},
    {"symbol": "066570", "name": "LG전자"},
    {"symbol": "003670", "name": "포스코퓨처엠"},
    {"symbol": "086520", "name": "에코프로"},
    {"symbol": "247540", "name": "에코프로비엠"},
    {"symbol": "323410", "name": "카카오뱅크"},
    {"symbol": "377300", "name": "카카오페이"},
    {"symbol": "042700", "name": "한미반도체"},
    {"symbol": "007660", "name": "이수페타시스"},
    {"symbol": "010140", "name": "삼성중공업"},
    {"symbol": "028260", "name": "삼성물산"},
    {"symbol": "009150", "name": "삼성전기"},
    {"symbol": "011200", "name": "HMM"},
    {"symbol": "015760", "name": "한국전력"},
    {"symbol": "034730", "name": "SK"},
    {"symbol": "017670", "name": "SK텔레콤"},
    {"symbol": "011170", "name": "롯데케미칼"},
    {"symbol": "036570", "name": "엔씨소프트"},
    {"symbol": "259960", "name": "크래프톤"},
    {"symbol": "251270", "name": "넷마블"},
    {"symbol": "011780", "name": "금호석유"},
    {"symbol": "005830", "name": "DB손해보험"},
    {"symbol": "001450", "name": "현대해상"},
    {"symbol": "138040", "name": "메리츠금융지주"},
    {"symbol": "096770", "name": "SK이노베이션"},
    {"symbol": "010950", "name": "S-Oil"},
    {"symbol": "329180", "name": "HD현대중공업"},
    {"symbol": "042660", "name": "한화오션"},
    {"symbol": "012450", "name": "한화에어로스페이스"},
    {"symbol": "079550", "name": "LIG넥스원"},
    {"symbol": "034020", "name": "두산에너빌리티"},
    {"symbol": "018260", "name": "삼성SDS"},
]

US_MAJOR_STOCKS = [
    {"symbol": "AAPL", "name": "애플"},
    {"symbol": "MSFT", "name": "마이크로소프트"},
    {"symbol": "NVDA", "name": "엔비디아"},
    {"symbol": "GOOGL", "name": "알파벳"},
    {"symbol": "AMZN", "name": "아마존"},
    {"symbol": "META", "name": "메타"},
    {"symbol": "TSLA", "name": "테슬라"},
    {"symbol": "BRK-B", "name": "버크셔해서웨이"},
    {"symbol": "LLY", "name": "일라이릴리"},
    {"symbol": "TSM", "name": "TSMC"},
    {"symbol": "AVGO", "name": "브로드컴"},
    {"symbol": "JPM", "name": "JPMorgan"},
    {"symbol": "V", "name": "비자"},
    {"symbol": "UNH", "name": "유나이티드헬스"},
    {"symbol": "XOM", "name": "엑슨모빌"},
    {"symbol": "MA", "name": "마스터카드"},
    {"symbol": "JNJ", "name": "존슨앤존슨"},
    {"symbol": "PG", "name": "P&G"},
    {"symbol": "HD", "name": "홈디포"},
    {"symbol": "MRK", "name": "머크"},
    {"symbol": "COST", "name": "코스트코"},
    {"symbol": "AMD", "name": "AMD"},
    {"symbol": "CVX", "name": "셰브론"},
    {"symbol": "KO", "name": "코카콜라"},
    {"symbol": "PEP", "name": "펩시코"},
    {"symbol": "CRM", "name": "세일즈포스"},
    {"symbol": "NFLX", "name": "넷플릭스"},
    {"symbol": "WMT", "name": "월마트"},
    {"symbol": "BAC", "name": "뱅크오브아메리카"},
    {"symbol": "MCD", "name": "맥도날드"},
    {"symbol": "CSCO", "name": "시스코"},
    {"symbol": "INTC", "name": "인텔"},
    {"symbol": "ORCL", "name": "오라클"},
    {"symbol": "DIS", "name": "디즈니"},
    {"symbol": "PFE", "name": "화이자"},
]

def get_investor_data(symbol, date_str):
    """
    Fetch daily net purchases (개인, 외국인, 기관) using pykrx.
    If today, and pykrx is empty, use Daum Finance API for real-time provisional data.
    """
    # Try importing pykrx inside to avoid breaking if not installed
    try:
        from pykrx import stock
        import pandas as pd
        
        # date_str format is YYYY-MM-DD, pykrx needs YYYYMMDD
        krx_date = date_str.replace("-", "")
        
        df = stock.get_market_net_purchases_of_equities_by_ticker(krx_date, krx_date, "KOSPI", "개인")
        df_inst = stock.get_market_net_purchases_of_equities_by_ticker(krx_date, krx_date, "KOSPI", "기관합계")
        df_foreign = stock.get_market_net_purchases_of_equities_by_ticker(krx_date, krx_date, "KOSPI", "외국인")
        
        individual = df.loc[symbol]['순매수거래대금'] if not df.empty and symbol in df.index else None
        institution = df_inst.loc[symbol]['순매수거래대금'] if not df_inst.empty and symbol in df_inst.index else None
        foreign = df_foreign.loc[symbol]['순매수거래대금'] if not df_foreign.empty and symbol in df_foreign.index else None
        
        if individual is not None or institution is not None or foreign is not None:
            return {
                "개인": f"{individual:,}원" if individual is not None else "데이터 없음",
                "기관": f"{institution:,}원" if institution is not None else "데이터 없음",
                "외국인": f"{foreign:,}원" if foreign is not None else "데이터 없음",
                "is_realtime": False
            }
    except Exception as e:
        print(f"PyKrx error: {e}")
        
    # Real-time fallback (Daum Finance)
    try:
        url = f"https://finance.daum.net/api/investor/days?symbolCode=A{symbol}&page=1&perPage=1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': f'https://finance.daum.net/quotes/A{symbol}#influential_investors'
        }
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            if data and 'data' in data and len(data['data']) > 0:
                item = data['data'][0]
                # Daum API provides volume for provisional intraday
                inst_vol = item.get('institutionStraightPurchaseVolume')
                for_vol = item.get('foreignStraightPurchaseVolume')
                return {
                    "개인": "장중 미집계",
                    "기관": f"{inst_vol:,}주 (잠정)" if inst_vol is not None else "데이터 없음",
                    "외국인": f"{for_vol:,}주 (잠정)" if for_vol is not None else "데이터 없음",
                    "is_realtime": True
                }
    except Exception as e:
        print(f"Daum API fallback error: {e}")
        
    return None

def get_us_analyst_ratings(symbol):
    """
    Fetch Analyst Recommendations using yfinance for US stocks.
    Returns a dict with 'strongBuy', 'buy', 'hold', 'sell', 'strongSell' counts or None.
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        rec = ticker.recommendations_summary
        
        if rec is not None and not rec.empty:
            # rec usually has periods like '0m' (current), '-1m', etc.
            # We want the '0m' row
            current = rec[rec['period'] == '0m']
            if not current.empty:
                return {
                    "strongBuy": int(current.iloc[0].get('strongBuy', 0)),
                    "buy": int(current.iloc[0].get('buy', 0)),
                    "hold": int(current.iloc[0].get('hold', 0)),
                    "sell": int(current.iloc[0].get('sell', 0)),
                    "strongSell": int(current.iloc[0].get('strongSell', 0))
                }
    except Exception as e:
        print(f"Error fetching US analyst ratings for {symbol}: {e}")
    
    return None

def get_stock_change(symbol, date_str):
    """
    Fetch actual stock change rate for a given symbol and date.
    """
    try:
        end_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        start_date = end_date - timedelta(days=10) # Enough buffer for weekends
        
        df = fdr.DataReader(symbol, start_date.strftime("%Y-%m-%d"), date_str)
        if len(df) >= 2:
            prev_close = df['Close'].iloc[-2]
            today_close = df['Close'].iloc[-1]
            change_pct = ((today_close - prev_close) / prev_close) * 100
            return change_pct
    except Exception as e:
        pass
    
    return 0.0

def get_top_movers(date_str, top_n=10, market="KR"):
    """
    Find top movers from MAJOR_STOCKS or US_MAJOR_STOCKS for a given date.
    Sorts by absolute change percentage.
    """
    print(f"Finding top movers for {date_str} among {market} major stocks...")
    movers = []
    stocks_list = US_MAJOR_STOCKS if market == "US" else MAJOR_STOCKS
    
    for stock in stocks_list:
        change = get_stock_change(stock['symbol'], date_str)
        if abs(change) > 0.01: # Ignore tiny changes
            movers.append({
                "symbol": stock['symbol'],
                "name": stock['name'],
                "change": change,
                "change_rate": f"{'+' if change >= 0 else ''}{change:.1f}%",
                "market": market
            })
    
    # Sort by absolute change value descending
    movers.sort(key=lambda x: abs(x['change']), reverse=True)
    return movers[:top_n]

def scrape_article_content(url):
    """
    Fetch and extract the main text content from a Naver news article.
    """
    if "article_id=" in url and "office_id=" in url:
        import re
        article_id = re.search(r'article_id=(\d+)', url)
        office_id = re.search(r'office_id=(\d+)', url)
        if article_id and office_id:
            url = f"https://n.news.naver.com/mnews/article/{office_id.group(1)}/{article_id.group(1)}"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Naver Finance is euc-kr, but n.news.naver.com is utf-8
        if "n.news.naver.com" in url:
            response.encoding = 'utf-8'
        else:
            response.encoding = 'euc-kr'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Naver News main content area
        # Try multiple selectors for different Naver news layouts
        content = soup.select_one('#dic_area')
        if not content:
            content = soup.select_one('#newsct_article')
        if not content:
            content = soup.select_one('#articleBodyContents')
        if not content:
            content = soup.select_one('.article_view')
            
        if content:
            # Remove scripts and styles
            for script_or_style in content(['script', 'style', 'span', 'a']):
                script_or_style.decompose()
            return content.get_text(strip=True, separator='\n')[:2000] # Limit to 2000 chars
    except Exception as e:
        print(f"Error scraping article content: {e}")
    return ""

def is_relevant_article(title, stock_name):
    """
    Check if the article title is likely relevant to the stock.
    """
    import re
    
    # 1. Broad Market Downranking
    market_terms = ["코스피", "코스닥", "지수", "시황", "마감", "뉴욕증시", "블루칩", "글로벌 증시", "아시아 증시"]
    market_count = sum(1 for term in market_terms if term in title)
    
    # 2. Strict Subject Check (Primary focus on this stock)
    subject_patterns = [
        rf"\[.*{re.escape(stock_name)}.*\]", # [삼성전자]
        rf"{re.escape(stock_name)}\s*[:]",      # 삼성전자 :
        rf"^{re.escape(stock_name)}"          # 삼성전자 (start of title)
    ]
    is_main_subject = any(re.search(p, title) for p in subject_patterns)

    # 3. Decision Logic
    # Reject if it's a broad market wrap-up and the stock isn't the headline subject
    if market_count >= 2 and not is_main_subject:
        return False

    # Standard check: must contain the stock name
    return stock_name in title

def scrape_naver_news(symbol, name, target_date_str, max_articles=20):
    """
    Scrape news for a given stock. Performs a 2-day lookback if target date news is not found.
    """
    print(f"Scraping news for {name} ({symbol})...")
    
    # Try current date, then day-1, then day-2
    target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
    lookback_days = [target_date, target_date - timedelta(days=1), target_date - timedelta(days=2)]
    
    articles = []
    seen_titles = set()
    seen_hours = set()
    
    for current_date in lookback_days:
        date_clean = current_date.strftime("%Y.%m.%d")
        
        # hour -> list of articles in that hour
        hour_buckets = {}
        # articles without hour info (rare on Naver but possible)
        no_hour_articles = []
        
        found_older_date = False
        for page in range(1, 16):
            url = f"https://finance.naver.com/item/news_news.naver?code={symbol}&page={page}&sm=title_entity_id.basic&clusterId="
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': f'https://finance.naver.com/item/news.naver?code={symbol}'
                }
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                response.encoding = 'euc-kr'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.select('table.type5 tbody tr')
                if not rows: break
                
                for row in rows:
                    tds = row.select('td')
                    if len(tds) < 2: continue
                    
                    title_td = row.select_one('td.title')
                    a_tag = title_td.select_one('a') if title_td else row.select_one('a')
                    if not a_tag: continue
                        
                    title = a_tag.get_text(strip=True)
                    href = a_tag.get('href', '')
                    if not title or title in seen_titles: continue
                    
                    date_td = row.select_one('td.date')
                    article_date_full = date_td.get_text(strip=True) if date_td else ""
                    date_parts = article_date_full.split(" ")
                    article_date_only = date_parts[0]
                    article_hour = date_parts[1].split(":")[0] if len(date_parts) > 1 else ""
                    
                    if article_date_only == date_clean:
                        full_url = f"https://finance.naver.com{href}" if href.startswith('/') else href
                        info_td = row.select_one('td.info')
                        source = info_td.get_text(strip=True) if info_td else ""
                        
                        import re
                        has_name = False
                        if len(name) <= 2:
                            # Strict match for short names (e.g. SK, LG)
                            # Match if name is followed by space, punctuation, or start/end of string
                            # Avoid matching subsidiaries like "SK온", "SK하이닉스"
                            pattern = rf"(?:^|[^가-힣a-zA-Z0-9]){re.escape(name)}(?:$|[^가-힣a-zA-Z0-9])"
                            if re.search(pattern, title):
                                has_name = True
                        else:
                            has_name = name in title

                        article_data = {
                            "title": title, 
                            "url": full_url, 
                            "date": article_date_full, 
                            "source": source,
                            "has_name": has_name
                        }
                        
                        if article_hour:
                            if article_hour not in hour_buckets:
                                hour_buckets[article_hour] = []
                            hour_buckets[article_hour].append(article_data)
                        else:
                            no_hour_articles.append(article_data)
                        
                        seen_titles.add(title)
                    elif article_date_only < date_clean and "." in article_date_only:
                        found_older_date = True
                        break
                
                if found_older_date: break
                        
            except Exception as e:
                print(f"Error scraping Naver news page {page}: {e}")
                break
        
        # Process collected articles for the current_date
        deduplicated = []
        for hour in sorted(hour_buckets.keys(), reverse=True):
            bucket = hour_buckets[hour]
            # Preference in this hour: 1. Contains name, 2. Most recent
            matches = [a for a in bucket if a['has_name']]
            if matches:
                deduplicated.append(matches[0]) # Most recent name match
            else:
                deduplicated.append(bucket[0]) # Most recent overall
        
        # Add no-hour articles (briefly deduplicated by title already)
        deduplicated.extend(no_hour_articles)
        
        if deduplicated:
            # Final selection: prioritize company name matches globally for the date
            with_name = [a for a in deduplicated if a['has_name']]
            without_name = [a for a in deduplicated if not a['has_name']]
            
            # Already sorted by recent within buckets, but let's be sure
            with_name.sort(key=lambda x: x['date'], reverse=True)
            without_name.sort(key=lambda x: x['date'], reverse=True)
            
            articles = (with_name + without_name)[:3]
            break

    if not articles:
        # Generic professional fallback
        articles = [{"title": f"{name}, 시장 흐름 및 관련 테마 분석", "url": f"https://finance.naver.com/item/news.naver?code={symbol}", "date": target_date_str.replace("-", ".") + " 09:00", "source": "증권정보"}]
    
    return articles

def scrape_us_news(symbol, name, target_date_str, max_articles=5):
    """
    Scrape English news headlines and links from Yahoo Finance RSS.
    """
    print(f"Scraping US news for {name} ({symbol})...")
    import xml.etree.ElementTree as ET
    
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    articles = []
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        root = ET.fromstring(res.text)
        for item in root.findall('./channel/item')[:max_articles]:
            title_el = item.find('title')
            link_el = item.find('link')
            pub_date_el = item.find('pubDate')
            
            title = title_el.text if title_el is not None else ""
            link = link_el.text if link_el is not None else ""
            pub_date = pub_date_el.text if pub_date_el is not None else ""
            
            if title and link:
                articles.append({
                    "title": title,
                    "url": link,
                    "date": pub_date,
                    "source": "Yahoo Finance",
                    "has_name": True # Assume RSS feeds are highly targeted
                })
    except Exception as e:
        print(f"Error scraping US news for {symbol}: {e}")
        
    if not articles:
        articles = [{"title": f"{name} Market Analysis", "url": f"https://finance.yahoo.com/quote/{symbol}", "date": target_date_str, "source": "Yahoo Finance", "has_name": True}]
        
    return articles

def select_impactful_article(stock_name, articles, change_val):
    """
    Use Gemini to select the index of the most impactful article from the list.
    Strictly prioritizes company-specific events over broad market news.
    """
    direction = "상승" if change_val >= 0 else "하락"
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key != "your_api_key_here" and GENAI_AVAILABLE:
        try:
            genai.configure(api_key=api_key, transport='rest')
            model = genai.GenerativeModel('gemini-flash-latest')
            
            prompt = (
                f"{stock_name}의 주가가 오늘 {direction}했습니다. 다음 뉴스 헤드라인 중 "
                f"이 변동에 가장 큰 원인이 되었을 것으로 판단되는 기사의 번호(0부터 시작)만 하나 골라주세요.\n"
                f"**핵심 지침:**\n"
                f"1. **회사 특정적 뉴스 우선**: '실적', '수주', '인수/합병', '신제품', '신고가 경신' 등 {stock_name} 회사 자체의 소식을 최우선으로 선택하세요.\n"
                f"2. **시장/지수 전체 뉴스 배제**: '코스피 상승', '시황 마감', '지수 5000 돌파' 등 시장 전체 흐름을 다루는 뉴스는 {stock_name} 전용 뉴스가 있다면 무조건 제외하세요.\n"
                f"3. 만약 회사와 관련된 뉴스가 하나도 없다면 'none'이라고 답해주세요.\n\n"
                + "\n".join([f"{i}: {a['title']}" for i, a in enumerate(articles)]) +
                "\n\n응답은 반드시 숫자 하나 또는 'none'만 해주세요."
            )
            
            # Using ThreadPoolExecutor without 'with' to avoid blocking on timeout
            from concurrent.futures import ThreadPoolExecutor, TimeoutError
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(model.generate_content, prompt)
            response = future.result(timeout=10)
                
            if response and response.text:
                import re
                if 'none' in response.text.lower():
                    return -1
                match = re.search(r'\d+', response.text)
                if match:
                    idx = int(match.group())
                    if 0 <= idx < len(articles):
                        return idx
        except Exception as e:
            print(f"Error selecting article: {e}")
            
    # Fallback: Rule-based best guess (Keywords)
    # Downrank market keywords, Uprank company keywords
    company_keywords = ["신고가", "최다주주", "실적", "수주", "영업이익", "흑자", "배당", "인수", "합병", "공시", "특징주"]
    market_keywords = ["코스피", "지수", "시황", "마감", "뉴욕증시"]
    
    scored_articles = []
    for i, article in enumerate(articles):
        score = 0
        title = article['title']
        if any(kw in title for kw in company_keywords): score += 10
        if any(kw in title for kw in market_keywords): score -= 5
        if title.startswith(stock_name) or f"[{stock_name}]" in title: score += 5
        scored_articles.append((score, i))
    
    scored_articles.sort(reverse=True)
    return scored_articles[0][1] if scored_articles else 0

def generate_summary(stock_name, articles, change_val, best_idx=0, investor_data=None, analyst_data=None, market="KR"):
    """
    Generate a 2-3 line summary of why the stock moved, based on news articles.
    If market == "KR", we include investor_data.
    If market == "US", we include analyst_data (recommendation summary).
    Returns a string for KR, or a dict for US.
    """
    direction = "상승" if change_val >= 0 else "하락"
    
    # Try Gemini API if available
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key != "your_api_key_here" and GENAI_AVAILABLE:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-flash-latest')
            
            # Re-order articles to put the "best" one first for Gemini
            reordered = list(articles)
            if 0 <= best_idx < len(articles):
                best = reordered.pop(best_idx)
                reordered.insert(0, best)

            if market == "US":
                prompt = (
                    f"전문 금융 분석가로서 미국 주식 {stock_name}의 주가 {direction} 핵심 원인을 2~3줄로 한국어로 요약하세요.\n"
                    f"딱딱하고 기계적인 어투 대신, 블로그나 리포트에서 볼 법한 읽기 편한 문맥을 사용하세요.\n"
                    f"영어 뉴스 기사들 (첫 번째 기사가 가장 중요함):\n\n"
                )
            else:
                prompt = (
                    f"전문 금융 분석가로서 주가 {direction}의 핵심 원인을 명확하고 구체적이며 자연스럽게 2~3줄로 요약하세요.\n"
                    f"딱딱하고 기계적인 어투('--보이며', '--마감했습니다') 대신, 블로그나 리포트에서 볼 법한 전문적이면서도 읽기 편한 문맥을 사용하세요.\n"
                    f"뉴스 기사들 (첫 번째 기사가 가장 중요함):\n\n"
                )
            
            for i, article in enumerate(reordered[:3]):
                title = article.get("title", "")
                content = article.get("content", "")
                prompt += f"기사 {i+1}: {title}\n내용: {content[:1000]}\n\n"
                
            if market == "KR" and investor_data:
                time_ctx = "장중 실시간(크롤링 시점)" if investor_data.get('is_realtime') else "장 마감(종가)"
                prompt += f"**오늘 수급 데이터 ({time_ctx} 기준 순매수/순매도):**\n"
                prompt += f"- 개인: {investor_data['개인']}\n"
                prompt += f"- 외국인: {investor_data['외국인']}\n"
                prompt += f"- 기관: {investor_data['기관']}\n\n"
                
            if market == "US" and analyst_data:
                prompt += f"**참고용 월가 애널리스트 투자의견 (최근 1개월 기준):**\n"
                prompt += f"- 강력 매수(Strong Buy): {analyst_data.get('strongBuy', 0)}명\n"
                prompt += f"- 매수(Buy): {analyst_data.get('buy', 0)}명\n"
                prompt += f"- 유지(Hold): {analyst_data.get('hold', 0)}명\n"
                prompt += f"- 매도(Sell): {analyst_data.get('sell', 0)}명\n"
                prompt += f"- 강력 매도(Strong Sell): {analyst_data.get('strongSell', 0)}명\n\n"
                
            if market == "US":
                prompt += (
                    f"**작성 규칙:**\n"
                    f"1. **기사 제목 번역 의무화**: 기사 원문 제목을 그대로 쓰지 말고, 반드시 한국어로 매끄럽게 번역하세요.\n"
                    f"2. **자연스러운 번역 요약**: 번역된 제목과 함께 전체 기사 내용을 인과관계가 드러나도록 한국어로 자연스럽게 요약 설명하세요. ('어떤 이유로 주가가 올랐다/내렸다' 형식)\n"
                    f"3. **월가 투자의견 반영(선택)**: 제공된 월가 투자의견 수치가 유의미하다면 괄호나 자연스러운 문맥으로 요약 끝에 덧붙여도 좋습니다. (예: 월가 대부분이 매수를 권고하고 있습니다 등)\n"
                    f"4. **정형화된 문구 금지**: 기계적인 문장으로 시작하지 마세요.\n"
                    f"5. **회사 특정적 요인**: {stock_name}의 사업이나 실적, 글로벌 경제 요인에 집중하세요.\n"
                    f"6. **출력 형식**: 반드시 아래 JSON 형식으로만 답변하세요. 다른 설명은 붙이지 마세요.\n"
                    f"{{\"translated_title\": \"번역된 매끄러운 한국어 기사 제목\", \"summary\": \"작성 규칙에 맞춘 한국어 요약문\"}}"
                )
            else:
                prompt += (
                    f"**작성 규칙:**\n"
                    f"1. **자연스러운 흐름**: 기사 내용과 수급 데이터(매수/매도 주체)를 자연스럽게 엮어서 인과관계를 설명하세요. 수치가 다소 부족하더라도 전체적인 흐름에 맞게 자연스럽게 요약하세요.\n"
                    f"2. **수급 흐름 명시 필수**: 요약문 작성 시 '{time_ctx} 기준'임을 반드시 언급하고, 개인/외국인/기관 중 주요 매수/매도 주체의 흐름을 포함하세요.\n"
                    f"3. **정형화된 문구 금지**: '주가가 강세를 보이며 상승 마감했습니다' 같은 뻔한 문장으로 시작하지 마세요.\n"
                    f"4. **구체적 사실 중심**: 기사에 나온 수치(매출액, 계약 규모 등)와 수급 주체를 활용하세요.\n"
                    f"5. **회사 특정적 요인**: {stock_name}의 사업이나 공시 내용에 집중하세요."
                )
            
            from concurrent.futures import ThreadPoolExecutor, TimeoutError
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(model.generate_content, prompt)
            response = future.result(timeout=10)
                
            if response and response.text:
                if market == "US":
                    # Attempt to parse json
                    try:
                        import json
                        import re
                        # Clean up markdown code blocks if any
                        json_str = re.sub(r'```(?:json)?', '', response.text).strip()
                        parsed = json.loads(json_str)
                        return parsed # Return dict for US
                    except Exception as e:
                        print(f"Failed to parse Gemini JSON: {e}, text: {response.text}")
                        return response.text.strip() # fallback
                else:
                    return response.text.strip()
        except TimeoutError:
            print(f"Gemini API timed out for {stock_name}")
        except Exception as e:
            print(f"Gemini API execution skipped or failed: {e}")
    
    # Enhanced logical fallback (Clean & Varied)
    news_titles = [a["title"] for a in articles if "title" in a]
    has_valid_news = (news_titles and 0 <= best_idx < len(news_titles))
    main_news = news_titles[best_idx] if has_valid_news else "시장 수급 변화"
    
    if change_val >= 0:
        templates = [
            f"{stock_name}은(는) {main_news} 소식이 전해지며 매수세가 강화되었습니다.",
            f"오늘 {stock_name} 주가는 {main_news} 등이 호재로 작용하며 긍정적인 흐름을 보였습니다.",
            f"{stock_name}의 상승세는 {main_news}에 따른 업황 기대감이 반영된 결과로 풀이됩니다."
        ]
    else:
        templates = [
            f"{stock_name}은(는) {main_news} 여파로 인해 매도 압력이 높아지며 약세를 보였습니다.",
            f"{stock_name} 주가는 {main_news} 등에 따른 투자 심리 위축으로 하락 마감했습니다.",
            f"오늘 {stock_name}의 하락은 {main_news}와 관련된 불확실성이 시장에 반영된 영향이 큽니다."
        ]
    
    import random
    fallback_text = random.choice(templates)
    
    if market == "KR" and investor_data:
        time_ctx = "장중 실시간" if investor_data.get('is_realtime') else "장 마감"
        fallback_text += f" ({time_ctx} 수급: 개인 {investor_data['개인']}, 외국인 {investor_data['외국인']}, 기관 {investor_data['기관']})"
        
    if market == "US":
        return {"translated_title": main_news, "summary": fallback_text}
    
    return fallback_text

def generate_short_reason(stock_name, articles, change_val, best_idx=0, translated_title=None):
    if translated_title:
        return f"{translated_title[:30]}..."
    
    direction = "상승" if change_val >= 0 else "하락"
    idx = best_idx if (articles and 0 <= best_idx < len(articles)) else 0
    if articles and "title" in articles[idx]:
        return f"{articles[idx]['title'][:30]}..."
    return f"시장 수급 및 업황 변화에 따른 {direction}"

def get_related_stocks(symbol, name, date_str, theme=None, market="KR"):
    """
    Tiered approach to find related stocks:
    1. Strategic/Industry Peers (Predefined mapping)
    2. Parent/Group Affiliate (name prefix)
    3. Theme-based Fallback (Stocks in the same sector)
    """
    related_candidates = []
    seen_symbols = {symbol}
    
    # Select the correct stock list based on market
    stocks_list = US_MAJOR_STOCKS if market == "US" else MAJOR_STOCKS
    
    # --- Tier 1: Strategic Peer Mapping (Highest Priority for Context) ---
    kr_peer_map = {
        # Semiconductors
        "005930": ["000660", "042700", "041510", "009150", "007660"],
        "000660": ["005930", "042700", "041510", "009150", "007660"],
        "042700": ["005930", "000660", "007660"],
        "007660": ["005930", "000660", "042700"],
        # Battery / EV
        "373220": ["051910", "003670", "086520", "247540", "005490"],
        "086520": ["247540", "373220", "003670", "051910"],
        "247540": ["086520", "373220", "003670", "051910"],
        "003670": ["005490", "086520", "247540", "373220"],
        # Auto
        "005380": ["000270", "012330", "005930"],
        "000270": ["005380", "012330", "005930"],
        "012330": ["005380", "000270"],
        # Finance / Banking
        "105560": ["055550", "323410", "377300"],
        "055550": ["105560", "323410", "377300"],
        "323410": ["035720", "105560", "055550"],
        # Insurance
        "032830": ["000810", "005830", "001450", "138040"], # 삼성생명 -> 보험사들
        "000810": ["032830", "005830", "001450", "138040"], # 삼성화재 -> 보험사들
        "005830": ["000810", "032830", "001450", "138040"], # DB손보 -> 보험사들
        "001450": ["000810", "032830", "005830", "138040"], # 현대해상 -> 보험사들
        # Gaming
        "036570": ["259960", "251270", "035420"], # 엔씨 -> 크래프톤, 넷마블
        "259960": ["036570", "251270", "035420"], # 크래프톤 -> 엔씨, 넷마블
        # Chemicals
        "011170": ["051910", "011780", "005490"], # 롯데케미칼 -> 화학주
    }
    
    us_peer_map = {
        "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
        "MSFT": ["AAPL", "GOOGL", "AMZN", "META", "ORCL"],
        "GOOGL": ["MSFT", "AAPL", "META", "AMZN"],
        "AMZN": ["MSFT", "GOOGL", "AAPL", "WMT", "NFLX"],
        "META": ["GOOGL", "AAPL", "SNAP", "PINS"],
        "NFLX": ["DIS", "AAPL", "AMZN", "GOOGL"],
        "DIS": ["NFLX", "AAPL", "AMZN"],
        "ORCL": ["MSFT", "CRM", "CSCO", "INTC"],
        "CRM": ["ORCL", "MSFT", "GOOGL"],
        "CSCO": ["ORCL", "MSFT", "INTC", "AVGO"],
        "NVDA": ["AMD", "TSM", "AVGO", "INTC"],
        "AMD": ["NVDA", "INTC", "TSM"],
        "TSM": ["NVDA", "AMD", "ASML", "INTC"],
        "AVGO": ["NVDA", "QCOM", "TXN", "CSCO"],
        "INTC": ["AMD", "NVDA", "TSM", "CSCO"],
        "TSLA": ["RIVN", "LCID", "F", "GM"],
        "LLY": ["NVO", "JNJ", "PFE", "MRK"],
        "JNJ": ["PFE", "MRK", "LLY"],
        "PFE": ["JNJ", "MRK", "LLY"],
        "MRK": ["JNJ", "PFE", "LLY"],
        "JPM": ["BAC", "WFC", "C", "GS", "MS"],
        "BAC": ["JPM", "WFC", "C"],
        "V": ["MA", "AXP", "PYPL"],
        "MA": ["V", "AXP", "PYPL"],
        "WMT": ["TGT", "COST", "AMZN", "HD"],
        "COST": ["WMT", "TGT", "HD"],
        "HD": ["WMT", "COST"],
        "KO": ["PEP", "MCD"],
        "PEP": ["KO", "MCD"],
        "MCD": ["KO", "PEP"],
        "UNH": ["JNJ", "PFE", "LLY"]
    }
    
    peer_map = us_peer_map if market == "US" else kr_peer_map
    
    if symbol in peer_map:
        for p_code in peer_map[symbol]:
            if p_code not in seen_symbols:
                # Find the stock info from the correct predefined list
                peer_info = next((s for s in stocks_list if s['symbol'] == p_code), None)
                if peer_info:
                    related_candidates.append(peer_info)
                    seen_symbols.add(p_code)
                    
    # --- Tier 2: Conglomerate Group (Prefix Match) (KR Market Only really) ---
    if market == "KR":
        prefix = name[:2]
        if len(prefix) >= 2:
            for s in stocks_list:
                if s['symbol'] not in seen_symbols and s['name'].startswith(prefix):
                    related_candidates.append(s)
                    seen_symbols.add(s['symbol'])
    
    # --- Tier 3: Theme-based Fallback (If still empty or fewer than 3) ---
    if theme and len(related_candidates) < 3:
        clean_theme = theme.replace("#", "")
        # Common theme keywords to stock mappings (Cross-market support)
        theme_map = {
            "반도체": ["005930", "000660", "042700", "007660", "009150"] if market == "KR" else ["NVDA", "AMD", "TSM", "AVGO", "INTC", "QCOM", "TXN", "MU"],
            "AI반도체": ["NVDA", "AMD", "TSM", "AVGO"],
            "빅테크": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX"],
            "전기차": ["TSLA", "RIVN", "LCID"],
            "바이오": ["LLY", "NVO"],
            "헬스케어": ["UNH", "JNJ", "PFE", "ABBV"],
            "결제": ["V", "MA", "PYPL", "AXP"],
            "이차전지": ["373220", "051910", "003670", "086520", "247540"],
            "금융": ["105560", "055550", "032830", "000810", "138040"] if market == "KR" else ["JPM", "BAC", "WFC", "C", "GS", "MS"],
            "정유": ["010950", "096770"] if market == "KR" else ["XOM", "CVX", "COP"],
            "에너지": ["015760", "034020"],
            "조선": ["010140", "329180", "042660"],
            "방산": ["012450", "079550"] if market == "KR" else ["LMT", "RTX", "NOC", "GD"],
            "지주사": ["000660", "034730", "003550", "028260"],
            "게임": ["036570", "259960", "251270"],
            "화학": ["051910", "011170", "011780"],
            "자동차": ["005380", "000270", "012330"] if market == "KR" else ["TSLA", "F", "GM"],
        }
        if clean_theme in theme_map:
            for t_code in theme_map[clean_theme]:
                if t_code not in seen_symbols:
                    t_info = next((s for s in stocks_list if s['symbol'] == t_code), None)
                    if t_info:
                        related_candidates.append(t_info)
                        seen_symbols.add(t_code)

    # Final cleanup: limit to 5 related stocks and fetch change rates
    final_related = []
    for rc in related_candidates[:5]:
        final_related.append({
            "name": rc['name'],
            "change_rate": f"{get_stock_change(rc['symbol'], date_str):+.1f}%"
        })
    return final_related

def get_last_trading_day(target_date_str=None):
    if target_date_str is None:
        target_date = datetime.datetime.now()
    else:
        target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
    
    start_date = target_date - timedelta(days=7)
    try:
        df = fdr.DataReader('KS11', start_date.strftime("%Y-%m-%d"), target_date.strftime("%Y-%m-%d"))
        if not df.empty: return df.index[-1].strftime("%Y-%m-%d")
    except: pass
    
    while target_date.weekday() > 4: target_date -= timedelta(days=1)
    return target_date.strftime("%Y-%m-%d")

def generate_daily_json(date_str=None, market="KR"):
    if date_str is None: date_str = get_last_trading_day()
    print(f"Generating data for {date_str} ({market} market)...")
    
    prefix = "us_" if market == "US" else ""
    output_file = os.path.join(DATA_DIR, f"{prefix}{date_str}.json")
    
    # Load existing articles to accumulate them throughout the day
    existing_data = {}
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Error loading existing JSON: {e}")
            
    existing_signals = {s['main_stock']['symbol']: s for s in existing_data.get('signals', [])}
    
    # 1. Get real movers
    movers = get_top_movers(date_str, market=market)
    
    signals = []
    for idx, stock in enumerate(movers):
        symbol = stock['symbol']
        name = stock['name']
        change_val = stock['change']
        
        # 2. News Headlines
        if market == "US":
            new_articles = scrape_us_news(symbol, name, date_str)
        else:
            new_articles = scrape_naver_news(symbol, name, date_str)
            
        # Merge new articles with existing ones (avoiding duplicates)
        articles = []
        seen_urls = set()
        for a in new_articles:
            if a['url'] not in seen_urls:
                articles.append(a)
                seen_urls.add(a['url'])
                
        if symbol in existing_signals:
            for a in existing_signals[symbol].get('news_articles', []):
                if a['url'] not in seen_urls:
                    articles.append(a)
                    seen_urls.add(a['url'])
        
        # 3. Select and Scrape Impactful News
        best_idx = select_impactful_article(name, articles, change_val)
        if articles and best_idx != -1 and 0 <= best_idx < len(articles):
            target_article = articles.pop(best_idx)
            print(f"Selected impactful news: {target_article['title']}")
            if market == "KR": # We only scrape deep content for KR right now
                # Check if we already scraped content to avoid redundant calls
                if 'content' not in target_article or not target_article['content']:
                    target_article['content'] = scrape_article_content(target_article['url'])
            # Put the best article at the top of the list so UI uses it easily
            articles.insert(0, target_article)
            best_idx = 0 # Update index since we moved it
        else:
            print(f"No sufficiently impactful/relevant news found for {name}.")
        
        # 5. Determine Theme
        industry_names = {
            "005930": "반도체", "000660": "반도체", "042700": "반도체", "007660": "반도체",
            "373220": "이차전지", "051910": "이차전지", "003670": "이차전지", "086520": "이차전지", "247540": "이차전지",
            "032830": "금융", "000810": "금융", "005830": "금융", "001450": "금융", "105560": "금융", "055550": "금융",
            "138040": "금융",
            "036570": "게임", "259960": "게임", "251270": "게임",
            "011170": "화학",
            "005380": "자동차", "000270": "자동차", "012330": "자동차",
            "AAPL": "빅테크", "MSFT": "빅테크", "NVDA": "AI반도체", "GOOGL": "빅테크", "AMZN": "빅테크",
            "TSLA": "전기차", "META": "빅테크", "TSM": "반도체", "AVGO": "반도체", "AMD": "반도체",
            "LLY": "바이오", "UNH": "헬스케어", "JPM": "금융", "V": "결제"
        }
        theme_name = industry_names.get(symbol, "글로벌시황" if market == "US" else "실적/수급")
        theme = f"#{theme_name}"
        
        # 4. Related (Pass theme & market for fallback)
        related = get_related_stocks(symbol, name, date_str, theme=theme, market=market)
        
        # 5. Fetch Additional Data
        investor_data = None
        analyst_data = None
        
        if market == "KR":
            try:
                investor_data = get_investor_data(symbol, date_str)
            except Exception as e:
                print(f"Error fetching investor data: {e}")
        elif market == "US":
            try:
                analyst_data = get_us_analyst_ratings(symbol)
            except Exception as e:
                print(f"Error fetching analyst ratings: {e}")
            
        # 6. Generate Summary
        summary = generate_summary(name, articles, change_val, best_idx, investor_data=investor_data, analyst_data=analyst_data, market=market)
        
        translated_title = None
        if isinstance(summary, dict):
            translated_title = summary.get("translated_title")
            summary = summary.get("summary", "")
        
        # 7. Generate Short Reason
        short_reason = generate_short_reason(name, articles, change_val, best_idx, translated_title=translated_title)
        
        news_url = f"https://finance.yahoo.com/quote/{symbol}" if market == "US" else f"https://finance.naver.com/item/news.naver?code={symbol}"
        
        signal_data = {
            "id": f"sig_{date_str.replace('-','')}_{market}_{idx+1:03d}",
            "theme": f"#{theme}",
            "short_reason": short_reason,
            "summary": summary,
            "main_stock": {
                "name": name, "symbol": symbol, "change_rate": stock['change_rate'],
                "news_url": news_url
            },
            "news_articles": articles,
            "related_stocks": related,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if analyst_data:
            signal_data["analyst_data"] = analyst_data
            
        signals.append(signal_data)

    output_data = {"last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "signals": signals}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Toss Signal Crawler")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--market", type=str, choices=["KR", "US"], default="KR", help="Market to crawl (KR or US)")
    args = parser.parse_args()
    
    target_day = args.date if args.date else get_last_trading_day()
    generate_daily_json(target_day, market=args.market)
