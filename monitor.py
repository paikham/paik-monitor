import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import re
import json

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}
YT_COOKIES = {
    'SOCS': 'CAISHAgBEhJnd3NfMjAyNDA4MTAtMF9SQzIaAmtvIAEaBgiAo_CmBg',
    'CONSENT': 'YES+cb.20240101-17-p0.ko+FX+999'
}

# --- 1. 디시인사이드 골목식당 갤러리 개념글 크롤링 ---
def get_dc_best_posts():
    url = "https://gall.dcinside.com/board/lists/?id=bjwstreet&exception_mode=recommend"
    headers = {**COMMON_HEADERS, 'Referer': 'https://gall.dcinside.com/'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = soup.select('.us-post')
        
        results = []
        for post in posts[:30]:
            title_element = post.select_one('.gall_tit a:not(.icon_pic_n)')
            if not title_element:
                title_element = post.select_one('.gall_tit a')
            if title_element and not title_element.text.startswith('공지'):
                title = title_element.text.strip()
                href = title_element.get('href', '')
                link = "https://gall.dcinside.com" + href if href.startswith('/') else href
                
                upvotes = post.select_one('.gall_recommend').text.strip() if post.select_one('.gall_recommend') else '0'
                views = post.select_one('.gall_count').text.strip() if post.select_one('.gall_count') else '0'
                date = post.select_one('.gall_date').text.strip() if post.select_one('.gall_date') else '-'
                reply_el = post.select_one('.reply_num')
                comments = reply_el.text.strip() if reply_el else "[0]"
                
                results.append({
                    'title': title, 'link': link, 
                    'upvotes': upvotes, 'views': views, 
                    'comments': comments, 'date': date
                })
        return results if results else [{'title': '개념글 목록이 비어있습니다.', 'link': '#', 'upvotes': '-', 'views': '-', 'comments': '-', 'date': '-'}]
    except Exception as e:
        return [{'title': f'갤러리 로딩 실패: {str(e)[:25]}', 'link': '#', 'upvotes': '-', 'views': '-', 'comments': '-', 'date': '-'}]

# --- 2. 네이버 종목토론방 (모바일 JSON API 1순위 + HTML 파싱 2순위) ---
def get_naver_jongtobang(ticker_code="475560"):
    results = []
    # 1차 시도: 네이버 모바일 증권 공식 JSON API (인코딩/태그 깨짐 없음)
    mobile_api = f"https://m.stock.naver.com/api/discuss/localStock/{ticker_code}?rsno=0&size=20"
    try:
        res = requests.get(mobile_api, headers=COMMON_HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data if isinstance(data, list) else data.get('result', data.get('items', []))
            if isinstance(items, list):
                for item in items[:20]:
                    title = item.get('title', '').strip()
                    if not title:
                        continue
                    nid = item.get('discussionId') or item.get('nid', '')
                    link = f"https://finance.naver.com/item/board_read.naver?code={ticker_code}&nid={nid}" if nid else f"https://finance.naver.com/item/board.naver?code={ticker_code}"
                    date_raw = item.get('date', item.get('writtenAt', ''))
                    date = date_raw[5:16].replace('-', '.') if len(date_raw) >= 16 else date_raw
                    views = f"{int(item.get('readCount', 0)):,}"
                    good = str(item.get('goodCount', 0))
                    bad = str(item.get('badCount', 0))
                    cmt_cnt = item.get('commentCount', 0)
                    comments = f"[{cmt_cnt}]" if cmt_cnt else ""
                    results.append({
                        'title': title, 'link': link, 'comments': comments,
                        'date': date, 'views': views, 'good': good, 'bad': bad
                    })
    except Exception:
        pass

    if results:
        return results

    # 2차 폴백: PC 웹페이지 크롤링 (tbody 제거하여 100% 매칭)
    url = f"https://finance.naver.com/item/board.naver?code={ticker_code}"
    headers = {**COMMON_HEADERS, 'Referer': 'https://finance.naver.com/'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content.decode('euc-kr', 'replace'), 'html.parser')
        rows = soup.select('table.type2 tr')
        for row in rows:
            title_el = row.select_one('td.title a')
            if not title_el:
                continue
            title = title_el.get('title', '').strip() or title_el.text.strip()
            link = "https://finance.naver.com" + title_el['href']
            cmt_el = row.select_one('td.title span.tah')
            comments = cmt_el.text.strip() if cmt_el else ""
            
            tds = row.select('td')
            date = tds[0].text.strip() if len(tds) > 0 else '-'
            views = tds[3].text.strip() if len(tds) > 3 else '0'
            good = tds[4].text.strip() if len(tds) > 4 else '0'
            bad = tds[5].text.strip() if len(tds) > 5 else '0'
            
            results.append({
                'title': title, 'link': link, 'comments': comments,
                'date': date, 'views': views, 'good': good, 'bad': bad
            })
            if len(results) >= 20:
                break
        return results if results else [{'title': '종토방 게시글이 없습니다.', 'link': '#', 'comments': '', 'date': '-', 'views': '-', 'good': '0', 'bad': '0'}]
    except Exception:
        return [{'title': '종토방 로딩 실패', 'link': '#', 'comments': '', 'date': '-', 'views': '-', 'good': '0', 'bad': '0'}]

# --- 3. 뉴스 크롤링 & 보도자료 복붙(클러스터링) 정밀 판독기 ---
SPAM_KEYWORDS = [
    '카지노', '토토', '바카라', '첫충', '슬롯', '파워볼', '홀덤', '배팅', '먹튀',
    '오늘의식탁', '똑똑한유통', '유통가 투데이', '푸드 투데이', '브리핑', '단신'
]
RISK_KEYWORDS = [
    '논란', '고소', '점주', '폐업', '공정위', '국감', '부진', '하락', '소송', '위반',
    '사과', '갈등', '불만', '신고', '적발', '폭락', '리스크', '정솔', '지혁', '염지',
    '엉터리', '허점', '실수', '횡령', '혐의', '보완수사', '수사', '과징금', '과태료',
    '허풍', '시험대', '위생', '비판', '외면', '철수', '갑질', '허위', '과장', '급락',
    '반토막', '우지커피', '눈물', '손절', '차단', '발각', '기만', '파묘'
]
PR_KEYWORDS = [
    '대박', '웨이팅', '출시', '할인', '후원', '기부', '성황', '인기', '호평', '매출',
    '소유진', '내조', '응원', '쏜다', '쐈다', '러브콜', '열풍', '돌파', '오픈', '공략',
    '시연회', '프로모션', '제공', '500원', '당근페이', '이벤트', '행보', '특가', '상생',
    '협약', 'MOU', '선보', '강화', '확대', '진출', '개최', '성료', '나눔'
]
STOP_WORDS = {'더본코리아', '더본', '백종원', '백종원의', '대표', '빽다방', '홍콩반점', '프랜차이즈', '외식', '진행', '운영', '출시'}

def extract_tokens(title):
    clean_t = title.rsplit(' - ', 1)[0]
    words = re.findall(r'[가-힣A-Za-z0-9]{2,}', clean_t)
    return {w for w in words if w not in STOP_WORDS}

def classify_single_news(title):
    for rk in RISK_KEYWORDS:
        if rk in title:
            return 'RISK', '🚨 쟁점·리스크'
    for pk in PR_KEYWORDS:
        if pk in title:
            return 'PR', '🎺 자본언플·홍보'
    return 'GEN', '📰 일반동향'

def get_latest_news():
    raw_list = []
    seen_urls = set()

    # 3-1. 네이버 뉴스 최신순 수집
    naver_query = quote("더본코리아 OR 백종원")
    naver_url = f"https://search.naver.com/search.naver?where=news&query={naver_query}&sort=1"
    try:
        res = requests.get(naver_url, headers=COMMON_HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        for item in soup.select('.news_area'):
            title_el = item.select_one('.news_tit')
            if not title_el:
                continue
            title = title_el.get('title') or title_el.text.strip()
            if any(sp in title for sp in SPAM_KEYWORDS):
                continue
            if '백종원' not in title and '더본' not in title and '빽다방' not in title and '소유진' not in title and '홍콩반점' not in title:
                continue
            link = title_el['href']
            if link in seen_urls:
                continue
            seen_urls.add(link)

            press_el = item.select_one('.info.press')
            press = press_el.text.replace('언론사 선정', '').strip() if press_el else '언론사'
            info_spans = item.select('span.info')
            date_str = info_spans[-1].text.strip() if info_spans else '최신'
            raw_list.append({'pure_title': title, 'press': press, 'link': link, 'date': date_str})
    except Exception:
        pass

    # 3-2. 구글 뉴스 RSS 수집 (최근 3일)
    q_encoded = quote("백종원 OR 더본코리아 when:3d")
    rss_url = f"https://news.google.com/rss/search?q={q_encoded}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(rss_url, headers=COMMON_HEADERS, timeout=10)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:35]:
            full_t = entry.title
            if any(sp in full_t for sp in SPAM_KEYWORDS):
                continue
            parts = full_t.rsplit(' - ', 1)
            pure_t = parts[0].strip()
            press = parts[1].strip() if len(parts) > 1 else '뉴스'
            if '백종원' not in pure_t and '더본' not in pure_t and '빽다방' not in pure_t and '소유진' not in pure_t and '홍콩반점' not in pure_t:
                continue
            date_str = entry.published[5:16] if hasattr(entry, 'published') else ''
            raw_list.append({'pure_title': pure_t, 'press': press, 'link': entry.link, 'date': date_str})
    except Exception:
        pass

    if not raw_list:
        return [{'title': '뉴스 로딩 실패', 'link': '#', 'date': '-', 'cat_code': 'GEN', 'cat_label': '오류', 'dups': []}]

    # 3-3. 보도자료 복붙 클러스터링 (핵심 키워드가 2개 이상 겹치는 기사끼리 그룹화)
    clusters = []
    for item in raw_list:
        tokens = extract_tokens(item['pure_title'])
        matched_cluster = None
        for cl in clusters:
            # 기존 클러스터 대표 기사와 핵심 단어 2개 이상 일치 시 같은 보도자료/이슈로 묶음
            if len(tokens & cl['tokens']) >= 2:
                matched_cluster = cl
                break
        if matched_cluster:
            if item['press'] != matched_cluster['main']['press'] and item['press'] not in [d['press'] for d in matched_cluster['dups']]:
                matched_cluster['dups'].append(item)
                matched_cluster['tokens'] |= tokens
        else:
            clusters.append({'main': item, 'tokens': tokens, 'dups': []})

    # 3-4. 최종 분류 (복붙 기사가 1개라도 더 있으면 리스크가 아닌 한 '보도자료 복붙 언플'로 강제 지정)
    final_news = []
    for cl in clusters[:18]:
        main = cl['main']
        dups = cl['dups']
        cat_code, cat_label = classify_single_news(main['pure_title'])
        
        total_cnt = 1 + len(dups)
        if total_cnt >= 2 and cat_code != 'RISK':
            cat_code = 'PR'
            cat_label = f"🎺 보도자료 복붙 ({total_cnt}건 살포)"
        elif total_cnt >= 2 and cat_code == 'RISK':
            cat_label = f"🚨 쟁점 확산 ({total_cnt}건 보도)"

        final_news.append({
            'title': f"{main['pure_title']} - {main['press']}",
            'link': main['link'],
            'date': main['date'],
            'cat_code': cat_code,
            'cat_label': cat_label,
            'dups': dups
        })
    return final_news

# --- 4. 네이버 금융 주가 + 밸류에이션 + 전자공시 ---
def get_stock_and_disclosures(ticker_code="475560"):
    api_url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{ticker_code}"
    stock_info = {
        'price': '오류', 'raw_price': 13380, 'change_str': '-',
        'vol': '-', 'ipo_drop': '-', 'peak_drop': '-', 'margin_safety': 50,
        'chart_day': '', 'chart_c_day': '', 'chart_c_week': '', 'chart_c_month': '',
        'disclosures': []
    }
    try:
        res = requests.get(api_url, headers=COMMON_HEADERS, timeout=10)
        data = res.json()
        item = data['result']['areas'][0]['datas'][0]
        
        nv = int(item['nv'])
        stock_info['raw_price'] = nv
        stock_info['price'] = f"{nv:,}"
        stock_info['vol'] = f"{item.get('aq', 0):,}"
        
        cv = item['cv']
        cr = item['cr']
        rf = str(item['rf'])
        
        if rf in ['1', '2']:
            stock_info['change_str'] = f"<span style='color:#ff5252; font-weight:bold;'>▲ {cv:,} (+{cr}%)</span>"
        elif rf in ['4', '5']:
            stock_info['change_str'] = f"<span style='color:#42a5f5; font-weight:bold;'>▼ {cv:,} (-{cr}%)</span>"
        else:
            stock_info['change_str'] = f"<span style='color:#e0e0e0; font-weight:bold;'>- {cv:,} (0.00%)</span>"

        ipo_price = 34000
        peak_price = 64500
        margin_call_price = 6875
        
        stock_info['ipo_drop'] = f"{((nv - ipo_price) / ipo_price) * 100:.1f}%"
        stock_info['peak_drop'] = f"{((nv - peak_price) / peak_price) * 100:.1f}%"
        
        gauge = int(((nv - margin_call_price) / (ipo_price - margin_call_price)) * 100)
        stock_info['margin_safety'] = max(5, min(100, gauge))

        cb = int(datetime.now().timestamp())
        stock_info['chart_day'] = f"https://ssl.pstatic.net/imgfinance/chart/item/area/day/{ticker_code}.png?sidcode={cb}"
        stock_info['chart_c_day'] = f"https://ssl.pstatic.net/imgfinance/chart/item/candle/day/{ticker_code}.png?sidcode={cb}"
        stock_info['chart_c_week'] = f"https://ssl.pstatic.net/imgfinance/chart/item/candle/week/{ticker_code}.png?sidcode={cb}"
        stock_info['chart_c_month'] = f"https://ssl.pstatic.net/imgfinance/chart/item/candle/month/{ticker_code}.png?sidcode={cb}"
    except Exception:
        pass

    # 최근 전자공시 크롤링 (tbody 제거하여 정상 수집)
    try:
        notice_url = f"https://finance.naver.com/item/news_notice.naver?code={ticker_code}"
        n_res = requests.get(notice_url, headers=COMMON_HEADERS, timeout=10)
        n_soup = BeautifulSoup(n_res.content.decode('euc-kr', 'replace'), 'html.parser')
        disclosures = []
        for r in n_soup.select('table.type5 tr'):
            a_el = r.select_one('td.title a')
            if not a_el:
                continue
            d_title = a_el.text.strip()
            d_link = "https://finance.naver.com" + a_el['href']
            tds = r.select('td')
            d_info = tds[1].text.strip() if len(tds) > 1 else ''
            d_date = tds[2].text.strip() if len(tds) > 2 else ''
            disclosures.append({'title': d_title, 'link': d_link, 'info': d_info, 'date': d_date})
            if len(disclosures) >= 6:
                break
        stock_info['disclosures'] = disclosures
    except Exception:
        pass

    return stock_info

# --- 5. 유튜브 3중 방탄 수집 엔진 (직접 RSS -> 프록시 RSS -> HTML 파싱) ---
YOUTUBE_CHANNELS = [
    {
        "name": "김재환의 오재나", "group": "CRITIC",
        "handle": "https://www.youtube.com/@studio_OZN",
        "id": "", "sample_vid": "0Gsvn_I6z1w"
    },
    {
        "name": "탐코 : 탐욕의 코리아", "group": "CRITIC",
        "handle": "https://www.youtube.com/channel/UC1rn5BnUdP1OGI6vnxh0IbQ",
        "id": "UC1rn5BnUdP1OGI6vnxh0IbQ", "sample_vid": "NryKk-8AvPY"
    },
    {
        "name": "백종원 본채널", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@paik_jongwon",
        "id": "UCyn-K7rZLXjGl7VXGweIlcA", "sample_vid": "pON-SAEgYUY"
    },
    {
        "name": "TBK (글로벌소스)", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@TBK_theborn",
        "id": "UCbgdcVitzVvWdngVx3OYTmA", "sample_vid": "FfC_pNkyaT8"
    },
    {
        "name": "더본 테이스티", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@theborn_tasty",
        "id": "", "sample_vid": "GdNx1GQAG_A"
    },
    {
        "name": "더본 NOW", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@theborn_now",
        "id": "", "sample_vid": ""
    }
]

def resolve_channel_id(ch):
    if ch.get('id'):
        return ch['id']
    
    urls_to_try = [ch['handle']]
    if ch.get('sample_vid'):
        urls_to_try.insert(0, f"https://www.youtube.com/watch?v={ch['sample_vid']}")
    
    # 프록시 우회 URL도 추가
    for u in list(urls_to_try):
        urls_to_try.append(f"https://api.allorigins.win/raw?url={quote(u)}")

    patterns = [
        r'"channelId":"(UC[\w-]{22})"',
        r'"externalId":"(UC[\w-]{22})"',
        r'itemprop="channelId" content="(UC[\w-]{22})"',
        r'channel_id=(UC[\w-]{22})',
        r'/channel/(UC[\w-]{22})'
    ]
    for url in urls_to_try:
        try:
            res = requests.get(url, headers=COMMON_HEADERS, cookies=YT_COOKIES, timeout=8)
            if res.status_code == 200 and res.text:
                for p in patterns:
                    m = re.search(p, res.text)
                    if m:
                        return m.group(1)
        except Exception:
            continue
    return None

def parse_rss_entries(content):
    feed = feedparser.parse(content)
    videos = []
    for entry in feed.entries[:3]:
        title = entry.title
        link = entry.link
        date = entry.published[:10] if hasattr(entry, 'published') else ''
        vid = entry.get('yt_videoid', '')
        thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else ''
        if not thumb and hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            thumb = entry.media_thumbnail[0]['url']
        views = '집계중'
        if hasattr(entry, 'media_statistics'):
            raw_v = entry.media_statistics.get('views', '')
            try: views = f"{int(raw_v):,}"
            except Exception: views = raw_v or '집계중'
        videos.append({'title': title, 'link': link, 'thumb': thumb, 'date': date, 'views': views})
    return videos

def fetch_channel_videos(channel_id):
    if not channel_id:
        return []
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    # 1차: 직접 RSS 요청 (Googlebot-News 호환 헤더 포함)
    try:
        res = requests.get(rss_url, headers=COMMON_HEADERS, cookies=YT_COOKIES, timeout=8)
        if res.status_code == 200 and b'<entry>' in res.content:
            vids = parse_rss_entries(res.content)
            if vids:
                return vids
    except Exception:
        pass

    # 2차: GitHub Actions IP가 유튜브에 차단됐을 때 AllOrigins 프록시 경유
    try:
        proxy_url = f"https://api.allorigins.win/raw?url={quote(rss_url)}"
        res = requests.get(proxy_url, headers=COMMON_HEADERS, timeout=10)
        if res.status_code == 200 and b'<entry>' in res.content:
            vids = parse_rss_entries(res.content)
            if vids:
                return vids
    except Exception:
        pass

    # 3차: rss2json 공개 API 경유
    try:
        r2j_url = f"https://api.rss2json.com/v1/api.json?rss_url={quote(rss_url)}"
        res = requests.get(r2j_url, headers=COMMON_HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get('status') == 'ok':
                videos = []
                for item in data.get('items', [])[:3]:
                    link = item.get('link', '')
                    vid_m = re.search(r'[?&]v=([\w-]{11})', link)
                    vid = vid_m.group(1) if vid_m else ''
                    thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else item.get('thumbnail', '')
                    videos.append({
                        'title': item.get('title', ''),
                        'link': link,
                        'thumb': thumb,
                        'date': item.get('pubDate', '')[:10],
                        'views': '클릭확인'
                    })
                if videos:
                    return videos
    except Exception:
        pass

    return []

def get_youtube_updates():
    results = []
    for ch in YOUTUBE_CHANNELS:
        cid = resolve_channel_id(ch)
        videos = fetch_channel_videos(cid)
        results.append({
            'name': ch['name'],
            'group': ch['group'],
            'handle': ch['handle'],
            'videos': videos
        })
    return results

# --- 6. 실시간 파묘 & 민심 핫키워드 추출기 ---
TRACK_KEYWORDS = [
    '빽다방', '우지커피', '홍콩반점', '소금물', '염지제', '정솔', '지혁', '삼국축제',
    '예산', '오너리스크', '탐코', '오재나', '김재환', '골목셰프', '최강록', '국감',
    '불체자', '막창짬뽕', '주담대', '고소', '폐업', '소유진', '청두', '상하이', '250억',
    '당근페이', '태극기', '가마치', '제육', '밀전병', '재판', '창업설명회', '국밥집', '알바'
]

def extract_hot_keywords(dc_posts, jongto_posts, news_list):
    combined_text = " ".join(
        [p['title'] for p in dc_posts] +
        [j['title'] for j in jongto_posts] +
        [n['title'] for n in news_list]
    )
    counts = []
    for kw in TRACK_KEYWORDS:
        c = combined_text.count(kw)
        if c > 0:
            counts.append((kw, c))
    counts.sort(key=lambda x: x[1], reverse=True)
    return counts[:12]

# --- 7. HTML 대시보드 생성 ---
def generate_html_dashboard():
    print("🚀 더본코리아 빽모니터링 PRO (V2.1) 데이터 수집 시작...")
    dc_posts = get_dc_best_posts()
    jongto_posts = get_naver_jongtobang()
    news = get_latest_news()
    stock = get_stock_and_disclosures()
    youtube_data = get_youtube_updates()
    hot_keywords = extract_hot_keywords(dc_posts, jongto_posts, news)
    
    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M:%S")
    
    kw_html = ""
    if hot_keywords:
        for kw, cnt in hot_keywords:
            kw_html += f"<span class='kw-badge'>#{kw} <b>{cnt}</b></span>"
    else:
        kw_html = "<span class='kw-badge'>#오너리스크</span><span class='kw-badge'>#파묘진행중</span>"

    dc_html = ""
    for p in dc_posts:
        dc_html += f"""
        <li>
            <div class="meta-line">{p['date']} | 조회 {p['views']} | <span style="color:#ff5252; font-weight:bold;">추천 {p['upvotes']}</span></div>
            <a href="{p['link']}" target="_blank">{p['title']} <span style="color:#4fc3f7; font-weight:bold;">{p['comments']}</span></a>
        </li>
        """

    jt_html = ""
    for j in jongto_posts:
        jt_html += f"""
        <li>
            <div class="meta-line">{j['date']} | 조회 {j['views']} | <span style="color:#ff8a65;">공감 {j['good']}</span> · <span style="color:#90caf9;">비공감 {j['bad']}</span></div>
            <a href="{j['link']}" target="_blank">{j['title']} <span style="color:#ffd54f;">{j['comments']}</span></a>
        </li>
        """

    news_html = ""
    for n in news:
        badge_class = "badge-risk" if n['cat_code'] == 'RISK' else ("badge-pr" if n['cat_code'] == 'PR' else "badge-gen")
        dup_html = ""
        if n.get('dups'):
            dup_links = ", ".join([f"<a href='{d['link']}' target='_blank' style='color:#ffd54f; font-size:0.85em;'>{d['press']}</a>" for d in n['dups'][:8]])
            dup_html = f"<div style='margin-top:5px; padding:6px 10px; background:#12141a; border-left:3px solid #ffd54f; font-size:0.82em; color:#aaa;'>📢 동일 보도자료 복붙 언론사 ({len(n['dups'])}곳): {dup_links}</div>"
            
        news_html += f"""
        <li class="news-item" data-cat="{n['cat_code']}">
            <div class="meta-line"><span class="n-badge {badge_class}">{n['cat_label']}</span> {n['date']}</div>
            <a href="{n['link']}" target="_blank">▶ {n['title']}</a>
            {dup_html}
        </li>
        """

    disc_html = ""
    if stock['disclosures']:
        for d in stock['disclosures']:
            disc_html += f"""
            <li>
                <div class="meta-line">{d['date']} | {d['info']}</div>
                <a href="{d['link']}" target="_blank">📑 {d['title']}</a>
            </li>
            """
    else:
        disc_html = "<li><span style='color:#888;'>최근 공시 내역이 없습니다.</span></li>"

    yt_critic_html = ""
    yt_official_html = ""
    for ch in youtube_data:
        block = f"<div class='channel-name'><a href='{ch['handle']}' target='_blank'>[{ch['name']}] ↗</a></div>"
        if not ch['videos']:
            block += "<div class='yt-item'><div class='yt-info'><span style='color:#888;'>유튜브 서버 응답 지연 (상단 채널명 클릭 시 바로 이동)</span></div></div>"
        else:
            for v in ch['videos']:
                block += f"""
                <div class="yt-item">
                    <img src="{v['thumb']}" alt="thumb" onerror="this.style.display='none'">
                    <div class="yt-info">
                        <a href="{v['link']}" target="_blank">{v['title']}</a>
                        <div class="yt-meta">{v['date']} | 조회수 {v['views']}</div>
                    </div>
                </div>
                """
        if ch['group'] == 'CRITIC':
            yt_critic_html += block
        else:
            yt_official_html += block

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="no-referrer">
    <title>더본코리아 빽모니터링 PRO</title>
    <style>
        :root {{
            --bg-main: #0f1115;
            --bg-card: #181b22;
            --border-color: #2a2f3a;
            --accent-red: #ff5252;
            --accent-blue: #4fc3f7;
            --accent-gold: #ffd54f;
            --text-main: #e4e6eb;
            --text-muted: #8b949e;
        }}
        * {{ box-sizing: border-box; }}
        body {{ background-color: var(--bg-main); color: var(--text-main); font-family: 'Pretendard', 'Malgun Gothic', sans-serif; margin: 0; padding: 20px; }}
        
        .header-container {{ text-align: center; border-bottom: 1px solid var(--border-color); padding-bottom: 20px; margin-bottom: 20px; display: flex; flex-direction: column; align-items: center; gap: 12px; }}
        .logo-wrapper {{ display: flex; gap: 20px; justify-content: center; align-items: center; background: #fff; padding: 8px 22px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
        .logo-wrapper img {{ height: 40px; object-fit: contain; }}
        h1 {{ color: var(--accent-red); margin: 0; font-size: 1.9em; letter-spacing: -0.5px; }}
        .update-time {{ font-size: 0.9em; color: var(--text-muted); }}

        .radar-bar {{ max-width: 1700px; margin: 0 auto 20px auto; background: #14171f; border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 18px; display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }}
        .radar-title {{ color: var(--accent-gold); font-weight: bold; font-size: 0.95em; margin-right: 6px; }}
        .kw-badge {{ background: #232834; color: #d0d7de; padding: 5px 11px; border-radius: 20px; font-size: 0.85em; border: 1px solid #343b4a; }}
        .kw-badge b {{ color: var(--accent-red); margin-left: 3px; }}

        .container {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; max-width: 1700px; margin: 0 auto; }}
        @media (max-width: 1200px) {{ .container {{ grid-template-columns: 1fr 1fr; }} }}
        @media (max-width: 768px) {{ .container {{ grid-template-columns: 1fr; }} }}

        .card {{ background: var(--bg-card); padding: 22px; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: 0 6px 16px rgba(0,0,0,0.4); display: flex; flex-direction: column; }}
        h2 {{ color: var(--accent-blue); font-size: 1.2em; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin: 0 0 15px 0; display: flex; justify-content: space-between; align-items: center; }}
        a {{ color: var(--text-main); text-decoration: none; transition: 0.15s; line-height: 1.45; display: inline-block; }}
        a:hover {{ color: var(--accent-red); text-decoration: underline; }}

        .stock-top {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 10px; }}
        .stock-price {{ font-size: 2.8em; color: #fff; font-weight: 800; margin: 0; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 15px 0; }}
        .kpi-box {{ background: #12141a; border: 1px solid #262b36; padding: 10px; border-radius: 8px; text-align: center; }}
        .kpi-label {{ font-size: 0.75em; color: var(--text-muted); margin-bottom: 4px; }}
        .kpi-val {{ font-size: 0.95em; font-weight: bold; color: #ff8a80; }}

        .gauge-wrap {{ background: #12141a; padding: 10px 12px; border-radius: 8px; border: 1px solid #262b36; margin-bottom: 12px; }}
        .gauge-header {{ display: flex; justify-content: space-between; font-size: 0.8em; color: var(--text-muted); margin-bottom: 6px; }}
        .gauge-bar-bg {{ width: 100%; height: 8px; background: #2b303c; border-radius: 4px; overflow: hidden; }}
        .gauge-bar-fill {{ height: 100%; background: linear-gradient(90deg, #ff1744, #ff9100, #00e676); width: {stock['margin_safety']}%; }}

        .tab-group {{ display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }}
        .tab-btn {{ background: #232834; color: #aaa; border: 1px solid #343b4a; padding: 5px 10px; border-radius: 6px; cursor: pointer; font-size: 0.8em; font-weight: bold; }}
        .tab-btn.active {{ background: var(--accent-blue); color: #000; border-color: var(--accent-blue); }}

        .chart-img {{ width: 100%; border-radius: 8px; filter: invert(0.9) hue-rotate(180deg); border: 1px solid #333; }}

        .scroll-list {{ list-style: none; padding: 0; margin: 0; max-height: 620px; overflow-y: auto; padding-right: 5px; }}
        .scroll-list::-webkit-scrollbar {{ width: 6px; }}
        .scroll-list::-webkit-scrollbar-thumb {{ background: #343b4a; border-radius: 3px; }}
        .scroll-list li {{ padding: 11px 0; border-bottom: 1px solid #232730; }}
        .scroll-list li:last-child {{ border-bottom: none; }}
        .meta-line {{ font-size: 0.8em; color: var(--text-muted); margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }}

        .n-badge {{ padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: bold; }}
        .badge-risk {{ background: rgba(255, 82, 82, 0.2); color: #ff5252; border: 1px solid rgba(255, 82, 82, 0.4); }}
        .badge-pr {{ background: rgba(255, 213, 79, 0.15); color: #ffd54f; border: 1px solid rgba(255, 213, 79, 0.4); }}
        .badge-gen {{ background: rgba(79, 195, 247, 0.15); color: #4fc3f7; }}

        .channel-name {{ margin: 18px 0 10px 0; padding-bottom: 5px; border-bottom: 1px dashed #333; }}
        .channel-name:first-child {{ margin-top: 0; }}
        .channel-name a {{ color: #a5d6a7; font-weight: bold; font-size: 1.05em; }}
        .yt-item {{ display: flex; gap: 12px; margin-bottom: 14px; align-items: flex-start; }}
        .yt-item img {{ width: 130px; height: 74px; object-fit: cover; border-radius: 6px; flex-shrink: 0; border: 1px solid #333; }}
        .yt-info a {{ font-size: 0.95em; font-weight: bold; margin-bottom: 5px; word-break: keep-all; }}
        .yt-meta {{ font-size: 0.8em; color: var(--text-muted); }}
    </style>
</head>
<body>
    <div class="header-container">
        <div class="logo-wrapper">
            <img src="https://clogo.saramin.co.kr/company/logo/201904/01/pp9q4h_a2oy-2rxibo_logo.png" alt="더본코리아">
            <img src="https://paikdabang.com/wp-content/themes/paikdabang/assets/images/logo.png" alt="빽다방">
            <img src="https://start.theborn.co.kr/images/brand/hongkong/common/logo.png" alt="홍콩반점">
        </div>
        <h1>더본코리아 빽모니터링 PRO</h1>
        <div class="update-time">마지막 업데이트: {current_time} (KST 기준 실시간 수집)</div>
    </div>

    <div class="radar-bar">
        <span class="radar-title">🔥 실시간 파묘·민심 키워드 레이더:</span>
        {kw_html}
    </div>

    <div class="container">
        <div class="card">
            <h2>📉 더본코리아 주가 & 오너리스크 지표</h2>
            <div class="stock-top">
                <div class="stock-price">{stock['price']} 원</div>
                <div style="font-size: 1.15em;">{stock['change_str']}</div>
            </div>

            <div class="kpi-grid">
                <div class="kpi-box">
                    <div class="kpi-label">공모가(34,000원) 대비</div>
                    <div class="kpi-val">{stock['ipo_drop']}</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-label">최고가(64,500원) 대비</div>
                    <div class="kpi-val">{stock['peak_drop']}</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-label">당일 거래량</div>
                    <div class="kpi-val" style="color:#e0e0e0;">{stock['vol']}주</div>
                </div>
            </div>

            <div class="gauge-wrap">
                <div class="gauge-header">
                    <span>⚠️ 50억 주담대 마진콜(~6,875원)</span>
                    <span>현재 {stock['price']}원</span>
                    <span>공모가(34,000원)</span>
                </div>
                <div class="gauge-bar-bg">
                    <div class="gauge-bar-fill"></div>
                </div>
            </div>

            <div class="tab-group">
                <button class="tab-btn active" onclick="switchChart('{stock['chart_day']}', this)">실시간선</button>
                <button class="tab-btn" onclick="switchChart('{stock['chart_c_day']}', this)">일봉</button>
                <button class="tab-btn" onclick="switchChart('{stock['chart_c_week']}', this)">주봉</button>
                <button class="tab-btn" onclick="switchChart('{stock['chart_c_month']}', this)">월봉</button>
            </div>
            <img id="stockChartImg" src="{stock['chart_day']}" class="chart-img" alt="주가 차트">

            <h2 style="margin-top:22px; font-size:1.05em;">📑 최근 전자공시 (DART 연동)</h2>
            <ul class="scroll-list" style="max-height: 190px;">
                {disc_html}
            </ul>
        </div>

        <div class="card">
            <h2>📰 실시간 뉴스 (언플 클러스터링 & 리스크)</h2>
            <div class="tab-group">
                <button class="tab-btn active" onclick="filterNews('ALL', this)">전체보기</button>
                <button class="tab-btn" onclick="filterNews('RISK', this)">🚨 쟁점·리스크</button>
                <button class="tab-btn" onclick="filterNews('PR', this)">🎺 자본언플·복붙</button>
            </div>
            <ul class="scroll-list" id="newsList">
                {news_html}
            </ul>
        </div>

        <div class="card">
            <h2>📺 유튜브 트래픽 전쟁</h2>
            <div class="tab-group">
                <button class="tab-btn active" onclick="switchYtTab('CRITIC', this)">⚡ 참교육·비판 (오재나·탐코)</button>
                <button class="tab-btn" onclick="switchYtTab('OFFICIAL', this)">🛡️ 백종원·더본 공식채널</button>
            </div>
            <div id="ytCriticBox" class="scroll-list">
                {yt_critic_html}
            </div>
            <div id="ytOfficialBox" class="scroll-list" style="display:none;">
                {yt_official_html}
            </div>
        </div>

        <div class="card" style="grid-column: span 2;">
            <h2>🦅 골목식당 갤러리 개념글 (실시간 파묘 30선)</h2>
            <ul class="scroll-list" style="max-height: 550px; display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px;">
                {dc_html}
            </ul>
        </div>

        <div class="card">
            <h2>🤬 네이버 종토방 실시간 민심 (정솔 검열구역)</h2>
            <ul class="scroll-list" style="max-height: 550px;">
                {jt_html}
            </ul>
        </div>
    </div>

    <script>
        function switchChart(url, btn) {{
            document.getElementById('stockChartImg').src = url;
            btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }}
        function filterNews(cat, btn) {{
            btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('#newsList .news-item').forEach(li => {{
                if (cat === 'ALL' || li.getAttribute('data-cat') === cat) {{
                    li.style.display = 'block';
                }} else {{
                    li.style.display = 'none';
                }}
            }});
        }}
        function switchYtTab(group, btn) {{
            btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('ytCriticBox').style.display = (group === 'CRITIC') ? 'block' : 'none';
            document.getElementById('ytOfficialBox').style.display = (group === 'OFFICIAL') ? 'block' : 'none';
        }}
    </script>
</body>
</html>
"""
    with open("theborn_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("\n✅ 더본코리아 빽모니터링 PRO (V2.1) 업데이트 완료!")

if __name__ == "__main__":
    generate_html_dashboard()
