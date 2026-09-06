import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timezone, timedelta
import re
from http.server import BaseHTTPRequestHandler # Vercel 송출용 모듈 추가

# --- 1. 디시인사이드 갤러리 크롤링 ---
def get_dc_best_posts():
    url = "https://gall.dcinside.com/board/lists/?id=bjwstreet&exception_mode=recommend"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = soup.select('.us-post')
        
        results = []
        for post in posts[:25]:
            title_element = post.select_one('.gall_tit a')
            if title_element and not title_element.text.startswith('공지'):
                title = title_element.text.strip()
                link = "https://gall.dcinside.com" + title_element['href']
                
                upvotes = post.select_one('.gall_recommend').text.strip()
                views = post.select_one('.gall_count').text.strip()
                date = post.select_one('.gall_date').text.strip()
                reply_el = post.select_one('.reply_num')
                comments = reply_el.text.strip() if reply_el else "[0]"
                
                results.append({
                    'title': title, 'link': link, 
                    'upvotes': upvotes, 'views': views, 
                    'comments': comments, 'date': date
                })
        return results
    except Exception as e:
        return [{'title': '갤러리 로딩 실패', 'link': '#', 'upvotes': '-', 'views': '-', 'comments': '-', 'date': '-'}]

# --- 2. 구글 뉴스 RSS ---
def get_latest_news():
    rss_url = "https://news.google.com/rss/search?q=백종원+OR+더본코리아+when:1d&hl=ko&gl=KR&ceid=KR:ko"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(rss_url, headers=headers, timeout=5)
        feed = feedparser.parse(res.content)
        
        results = []
        for entry in feed.entries[:8]:
            date_str = entry.published[5:16] if hasattr(entry, 'published') else ''
            results.append({'title': entry.title, 'link': entry.link, 'date': date_str})
        return results
    except Exception as e:
        return [{'title': '뉴스 로딩 실패', 'link': '#', 'date': '-'}]

# --- 3. 네이버 금융 더본코리아 주가 (API 직접 호출) ---
def get_stock_info(ticker_code="475560"):
    api_url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{ticker_code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(api_url, headers=headers, timeout=5)
        data = res.json()
        item = data['result']['areas'][0]['datas'][0]
        
        price = f"{item['nv']:,}"
        cv = item['cv']
        cr = item['cr']
        rf = str(item['rf'])
        
        if rf in ['1', '2']:
            change_str = f"<span style='color:#ff5252; font-weight:bold;'>▲ {cv:,} (+{cr}%)</span>"
        elif rf in ['4', '5']:
            change_str = f"<span style='color:#42a5f5; font-weight:bold;'>▼ {cv:,} (-{cr}%)</span>"
        else:
            change_str = f"<span style='color:#e0e0e0; font-weight:bold;'>- {cv:,} (0.00%)</span>"
            
        cache_buster = int(datetime.now().timestamp())
        chart_url = f"https://ssl.pstatic.net/imgfinance/chart/item/area/day/{ticker_code}.png?sidcode={cache_buster}"
            
        return {'price': price, 'change_str': change_str, 'chart_url': chart_url}
    except Exception as e:
        return {'price': '오류', 'change_str': '-', 'chart_url': ''}

# --- 4. 유튜브 RSS ---
youtube_channels = {
    "백종원 본채널": ("https://www.youtube.com/@paik_jongwon", "UCyn-K7rZLXjGl7VXGweIlcA"),
    "김재환의 오재나": ("https://www.youtube.com/@studio_OZN", ""),
    "TBK": ("https://www.youtube.com/@TBK_theborn", ""),
    "더본 테이스티": ("https://www.youtube.com/@theborn_tasty", ""),
    "더본 NOW": ("https://www.youtube.com/@theborn_now", "")
}

def get_channel_id(handle_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(handle_url, headers=headers, timeout=5)
        patterns = [r'"channelId":"(UC[\w-]{22})"', r'https://www.youtube.com/channel/(UC[\w-]{22})', r'channel_id=(UC[\w-]{22})']
        for p in patterns:
            match = re.search(p, res.text)
            if match: return match.group(1)
    except: pass
    return None

def get_youtube_updates():
    results = {}
    for name, (handle_url, known_id) in youtube_channels.items():
        channel_id = known_id if known_id else get_channel_id(handle_url)
        if not channel_id:
            results[name] = [{'title': '채널 ID 추출 실패', 'link': '#', 'thumb': '', 'date': '', 'views': ''}]
            continue
            
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            res = requests.get(rss_url, headers=headers, timeout=5)
            feed = feedparser.parse(res.content)
            
            videos = []
            for entry in feed.entries[:3]:
                title = entry.title
                link = entry.link
                date = entry.published[:10] if hasattr(entry, 'published') else ''
                
                thumb = ''
                if hasattr(entry, 'media_thumbnail') and len(entry.media_thumbnail) > 0:
                    thumb = entry.media_thumbnail[0]['url']
                
                views = '비공개'
                if hasattr(entry, 'media_statistics'):
                    views = entry.media_statistics.get('views', '비공개')
                    try: views = f"{int(views):,}"
                    except: pass
                
                videos.append({'title': title, 'link': link, 'thumb': thumb, 'date': date, 'views': views})
            
            if not videos:
                results[name] = [{'title': '업로드된 영상이 없거나 서버에서 일시 차단되었습니다.', 'link': '#', 'thumb': '', 'date': '', 'views': ''}]
            else:
                results[name] = videos
        except:
            results[name] = [{'title': 'RSS 연결 실패', 'link': '#', 'thumb': '', 'date': '', 'views': ''}]
    return results

# --- 5. HTML 대시보드 문자열 생성 (저장 안 함, 브라우저로 쏴주기만 함) ---
def generate_html_string():
    dc_posts = get_dc_best_posts()
    news = get_latest_news()
    stock = get_stock_info()
    youtube_data = get_youtube_updates()
    
    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M:%S")
    
    dc_html = ""
    for p in dc_posts:
        dc_html += f"""
        <li>
            <div class="dc-meta">{p['date']} | 조회 {p['views']} | <span style="color:#ff5252">추천 {p['upvotes']}</span></div>
            <a href='{p['link']}' target='_blank'> {p['title']} <span style="color:#4fc3f7">{p['comments']}</span></a>
        </li>
        """
        
    yt_html = ""
    for name, videos in youtube_data.items():
        yt_html += f"<div class='channel-name'>[{name}]</div>"
        for v in videos:
            if v['title'] == '업로드된 영상이 없거나 서버에서 일시 차단되었습니다.':
                yt_html += f"<div class='yt-item'><div class='yt-info'><span style='color:#888;'>{v['title']}</span></div></div>"
                continue
                
            yt_html += f"""
            <div class="yt-item">
                <img src="{v['thumb']}" alt="thumb" onerror="this.style.display='none'">
                <div class="yt-info">
                    <a href="{v['link']}" target="_blank">{v['title']}</a>
                    <div class="yt-meta">{v['date']} | 조회수 {v['views']}회</div>
                </div>
            </div>
            """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="referrer" content="no-referrer">
        <title>Theborn & Paik Tracker PRO</title>
        <style>
            body {{ background-color: #121212; color: #e0e0e0; font-family: 'Malgun Gothic', sans-serif; margin: 0; padding: 20px; }}
            
            .header-container {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 15px; margin-bottom: 30px; display: flex; flex-direction: column; align-items: center; gap: 15px; }}
            .logo-wrapper {{ display: flex; gap: 20px; justify-content: center; align-items: center; background: #fff; padding: 10px 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.5); }}
            .logo-wrapper img {{ height: 45px; object-fit: contain; }}
            h1 {{ color: #ff5252; margin: 0; }}
            .update-time {{ font-size: 0.95em; color: #aaa; margin-top: -5px; font-weight: bold; }}

            .container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 1600px; margin: 0 auto; }}
            .card {{ background: #1e1e1e; padding: 25px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); overflow: hidden; }}
            h2 {{ color: #4fc3f7; font-size: 1.3em; border-bottom: 1px solid #333; padding-bottom: 10px; margin-top: 0; }}
            a {{ color: #e0e0e0; text-decoration: none; transition: 0.2s; }}
            a:hover {{ color: #ff5252; text-decoration: underline; }}
            
            .stock-price {{ font-size: 3.5em; color: #fff; font-weight: bold; margin: 10px 0; }}
            .chart-img {{ width: 100%; max-width: 100%; border-radius: 8px; margin-top: 15px; filter: invert(0.9) hue-rotate(180deg); }}
            
            ul {{ list-style-type: none; padding: 0; margin: 0; }}
            li {{ padding: 12px 0; border-bottom: 1px solid #2a2a2a; }}
            li:last-child {{ border-bottom: none; }}
            
            .dc-meta {{ font-size: 0.85em; color: #888; margin-bottom: 4px; }}
            
            .channel-name {{ color: #a5d6a7; font-weight: bold; font-size: 1.2em; margin: 30px 0 15px 0; padding-bottom: 5px; border-bottom: 1px dashed #333; }}
            .channel-name:first-child {{ margin-top: 0; }}
            .yt-item {{ display: flex; gap: 18px; margin-bottom: 20px; align-items: flex-start; }}
            .yt-item img {{ width: 160px; height: 90px; object-fit: cover; border-radius: 8px; flex-shrink: 0; border: 1px solid #333; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }}
            .yt-info {{ display: flex; flex-direction: column; justify-content: center; }}
            .yt-info a {{ font-size: 1.05em; font-weight: bold; margin-bottom: 8px; display: block; word-break: keep-all; line-height: 1.4; }}
            .yt-meta {{ font-size: 0.9em; color: #999; }}
        </style>
    </head>
    <body>
        <div class="header-container">
            <div class="logo-wrapper">
                <img src="https://clogo.saramin.co.kr/company/logo/201904/01/pp9q4h_a2oy-2rxibo_logo.png" alt="더본코리아">
                <img src="https://paikdabang.com/wp-content/themes/paikdabang/assets/images/logo.png" alt="빽다방">
                <img src="https://start.theborn.co.kr/images/brand/hongkong/common/logo.png" alt="홍콩반점">
            </div>
            <h1>더본코리아 빽모니터링</h1>
            <div class="update-time">마지막 업데이트: {current_time} (접속 즉시 최신화)</div>
        </div>
        
        <div class="container">
            <div class="card">
                <h2>📉 더본코리아 현재 주가 및 차트</h2>
                <div class="stock-price">{stock['price']} 원</div>
                <div style="font-size: 1.3em;">전일대비: {stock['change_str']}</div>
                <img src="{stock['chart_url']}" class="chart-img" alt="주가 차트">
            </div>

            <div class="card">
                <h2>📰 실시간 뉴스 동향 (더본 자본 양념 팍팍)</h2>
                <ul>
                    {''.join([f"<li><div class='dc-meta'>{n['date']}</div><a href='{n['link']}' target='_blank'>▶ {n['title']}</a></li>" for n in news])}
                </ul>
            </div>

            <div class="card" style="grid-row: span 2;">
                <h2>🦅 골목식당 갤러리 개념글 (최신순 25개 파묘 현황)</h2>
                <ul>
                    {dc_html}
                </ul>
            </div>

            <div class="card" style="grid-row: span 2;">
                <h2>📺 더본코리아 관련 유튜브 동향</h2>
                {yt_html}
            </div>
        </div>
    </body>
    </html>
    """
    return html

# --- Vercel 실시간 웹 송출용 핸들러 ---
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        try:
            # 브라우저에 접속하는 즉시 크롤링해서 HTML을 쏴줌
            html_content = generate_html_string()
            self.wfile.write(html_content.encode('utf-8'))
        except Exception as e:
            error_msg = f"<html><body><h1>로딩 중 에러 발생</h1><p>{e}</p></body></html>"
            self.wfile.write(error_msg.encode('utf-8'))
