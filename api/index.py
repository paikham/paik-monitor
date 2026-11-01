import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
import re
import json

# ==============================================================================
# 🎯 [사용자 직접 관리 구역 1] 뉴스 분류 키워드 사전 (보내주신 최신 설정 반영 완료)
# 웹 화면의 [📋 파이썬 설정 복사] 버튼으로 언제든 세트로 복사해 덮어씌울 수 있습니다.
# ==============================================================================
NEWS_KEYWORDS = {
    "RISK": [
        "토막", "문닫", "논란", "고소", "점주", "폐업", "폐점", "공정위", "국감", "부진",
        "하락", "소송", "위반", "사과", "갈등", "불만", "신고", "적발", "폭락", "리스크",
        "정솔", "지혁", "염지", "허점", "실수", "횡령", "혐의", "보완수사", "수사", "과징금",
        "과태료", "허풍", "시험대", "위생", "비판", "외면", "철수", "갑질", "허위", "과장",
        "급락", "우지커피", "눈물", "손절", "차단", "발각", "기만", "파묘", "태극기", "오류",
        "지적", "휘청", "급감", "축소", "실태", "문 닫", "틀렸다", "감소", "타격", "적자"
    ],
    "PR": [
        "외식사업가", "송훈", "공짜", "100원", "통했다", "지휘", "대기", "대박", "웨이팅", "출시",
        "할인", "후원", "기부", "성황", "인기", "호평", "소유진", "내조", "응원", "쏜다",
        "쐈다", "러브콜", "열풍", "돌파", "오픈", "공략", "시연", "프로모션", "제공", "500원",
        "파격딜", "당근페이", "이벤트", "행보", "특가", "상생", "협약", "MOU", "선보", "강화",
        "확대", "진출", "개최", "성료", "나눔", "승부수", "성공", "뚫는다", "유통망", "블루오션",
        "세일즈", "외식왕", "근황", "파브리", "반전", "풍미", "러시", "완판"
    ],
    "SPAM": [
        "카지노", "토토", "바카라", "첫충", "슬롯", "파워볼", "홀덤", "배팅",
        "오늘의식탁", "똑똑한유통", "유통가 투데이", "푸드 투데이", "브리핑", "단신"
    ]
}

# ==============================================================================
# 🎯 [사용자 직접 관리 구역 2] 실시간 이슈 핵심 명사 (레이더) 설정 사전
# - BOOST: 복합명사/고유명사가 쪼개지지 않고 우선 추출되도록 지정하는 핵심 키워드
# - STOP : 레이더 랭킹에서 무조건 제외할 불용어 (웹에서 배지의 × 클릭 시 자동 추가됨)
# ==============================================================================
RADAR_KEYWORDS = {
    "BOOST": [
        "빽다방", "우지커피", "홍콩반점", "연돈볼카츠", "새마을식당", "골목셰프", "골목식당",
        "태극기", "당근페이", "주담대", "오너리스크", "정솔", "지혁", "소유진", "김재환",
        "오재나", "탐코", "상하이", "청두", "예산", "삼국축제", "가마치", "제육볶음",
        "밀전병", "창업설명회", "보완수사", "혐의없음", "국정감사", "공정위", "대패삼겹살",
        "원조쌈밥집", "유정수", "최강록", "정지선", "백반집", "국밥집", "한티역", "순감소"
    ],
    "STOP": [
        "근데", "아니", "진짜", "이거", "저거", "뭔가", "이제", "와서", "혹시", "니들",
        "알고", "어쩌라고", "백종원", "백종원이", "백종원의", "백종원씨", "더본", "더본코리아",
        "대표", "대표님", "갤주", "종팔이", "근황", "지금", "오늘", "오늘자", "최근", "현재",
        "그냥", "너무", "존나", "새끼", "씨발", "시발", "병신", "싯팔새끼", "이새끼", "사람",
        "솔직히", "진지하게", "경고", "속보", "다시보는", "명작", "이유", "한계", "명확한",
        "도와준", "비교", "진행상황", "유튭", "댓글", "민심", "왜이럼", "생각", "이렇게",
        "모습", "보이는", "하는", "있는", "없는", "같음", "있다", "없다", "되다", "하다",
        "이다", "같다", "보다", "오다", "가다", "주다", "알다", "모르다", "하면", "되면",
        "얘기", "정도", "때문", "부분", "문제", "사실", "현황", "진격", "학인된", "어제",
        "내일", "jpg", "jpeg", "png", "gif", "webp", "mp4", "dc", "app", "araboja",
        "aravoja", "feat", "hot", "유래", "음식", "사진", "영상", "최신", "방법", "하나",
        "리스트", "추천", "명언", "수급", "지랄", "레전드", "전문가", "인정하는", "증거자료"
    ]
}
# ==============================================================================

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

def decode_html(res):
    try:
        return res.content.decode('utf-8')
    except UnicodeDecodeError:
        return res.content.decode('cp949', 'replace')

# --- 1. 디시인사이드 골목식당 갤러리 개념글 (50선) ---
def get_dc_best_posts():
    url = "https://gall.dcinside.com/board/lists/?id=bjwstreet&exception_mode=recommend"
    headers = {**COMMON_HEADERS, 'Referer': 'https://gall.dcinside.com/'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(decode_html(response), 'html.parser')
        posts = soup.select('.us-post')
        
        results = []
        for post in posts[:50]:
            title_element = post.select_one('.gall_tit a:not(.icon_pic_n)') or post.select_one('.gall_tit a')
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
        return [{'title': f'갤러리 로딩 실패 ({str(e)[:15]})', 'link': '#', 'upvotes': '-', 'views': '-', 'comments': '-', 'date': '-'}]

# --- 2. 네이버 종토방 실시간 동적 수집 엔진 (하드코딩 더미 데이터 0%) ---
def extract_posts_from_any_json(data, ticker_code="475560"):
    """네이버 API의 다양한 JSON 응답 구조에서 게시글 리스트를 재귀적으로 추출합니다."""
    posts = []
    seen_ids = set()

    def walk(obj):
        if isinstance(obj, dict):
            title = obj.get('title') or obj.get('subject')
            has_meta = any(k in obj for k in (
                'discussionId', 'nid', 'articleId', 'postId', 'readCount',
                'viewCount', 'goodCount', 'recommendCount', 'sympathyCount',
                'writerNickname', 'nickname', 'contents', 'summary'
            ))
            if isinstance(title, str) and len(title.strip()) >= 2 and has_meta:
                nid = str(obj.get('discussionId') or obj.get('nid') or obj.get('articleId') or obj.get('postId') or obj.get('id') or title)
                if nid not in seen_ids:
                    seen_ids.add(nid)
                    desc = str(obj.get('contents') or obj.get('summary') or obj.get('body') or obj.get('content') or '')
                    desc = re.sub(r'<[^>]+>', ' ', desc).replace('\n', ' ').strip()[:100]
                    author = str(obj.get('writerNickname') or obj.get('nickname') or obj.get('writerId') or obj.get('author') or '주주')
                    date_raw = str(obj.get('date') or obj.get('writtenAt') or obj.get('regDate') or obj.get('createdAt') or '최신')
                    date = date_raw[5:16].replace('-', '.') if len(date_raw) >= 16 else date_raw[:10]
                    views = str(obj.get('readCount') or obj.get('viewCount') or obj.get('views') or '-')
                    good = str(obj.get('goodCount') or obj.get('recommendCount') or obj.get('sympathyCount') or obj.get('likeCount') or '0')
                    bad = str(obj.get('badCount') or obj.get('notRecommendCount') or obj.get('antipathyCount') or obj.get('dislikeCount') or '0')
                    cmt = obj.get('commentCount') or obj.get('replyCount') or 0
                    comments = f"[{cmt}]" if cmt else ""
                    link = f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discussion/{nid}" if nid.isdigit() else f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discussion"
                    posts.append({
                        'title': title.strip(), 'desc': desc, 'author': author,
                        'date': date, 'views': views, 'good': good, 'bad': bad,
                        'comments': comments, 'link': link
                    })
            else:
                for v in obj.values():
                    walk(v)
        elif isinstance(obj, list):
            for it in obj:
                walk(it)

    walk(data)
    return posts

def get_naver_jongtobang(ticker_code="475560"):
    posts = []
    req_headers = {
        **COMMON_HEADERS,
        'Referer': f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discussion",
        'Accept': 'application/json, text/plain, */*',
        'X-Requested-With': 'XMLHttpRequest'
    }

    # 1단계: 네이버 증권 & Npay 토론방 후보 API 직접 호출
    api_candidates = [
        f"https://m.stock.naver.com/front-api/discussion/list?discussionType=localStock&itemCode={ticker_code}&pageSize=20",
        f"https://m.stock.naver.com/front-api/v1/discussion/list?discussionType=localStock&itemCode={ticker_code}&pageSize=20",
        f"https://m.stock.naver.com/front-api/discussion/posts?discussionType=localStock&itemCode={ticker_code}&pageSize=20",
        f"https://m.stock.naver.com/api/discuss/localStock/{ticker_code}?rsno=0&size=20",
        f"https://m.stock.naver.com/api/discuss/localStock/{ticker_code}?size=20"
    ]
    for url in api_candidates:
        try:
            res = requests.get(url, headers=req_headers, timeout=3)
            if res.status_code == 200 and ('{' in res.text or '[' in res.text):
                extracted = extract_posts_from_any_json(res.json(), ticker_code)
                if extracted:
                    return extracted[:20]
        except Exception:
            continue

    # 2단계: Npay 토론방 페이지의 __NEXT_DATA__ 및 Next.js 웹팩 청크에서 API 경로 자동 역추적
    disc_page_url = f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discussion"
    try:
        res = requests.get(disc_page_url, headers=COMMON_HEADERS, timeout=3.5)
        if res.status_code == 200:
            html_text = decode_html(res)
            soup = BeautifulSoup(html_text, 'html.parser')

            # 2-1. __NEXT_DATA__ 내부 검색
            next_el = soup.select_one('script#__NEXT_DATA__')
            if next_el and next_el.string:
                extracted = extract_posts_from_any_json(json.loads(next_el.string), ticker_code)
                if extracted:
                    return extracted[:20]

            # 2-2. Next.js discussion 청크 JS 파일 스캔하여 실제 API 엔드포인트 추출
            chunk_urls = []
            for sc in soup.select('script[src*="/_next/static/chunks/"]'):
                src = sc.get('src', '')
                if any(k in src for k in ['discussion', '78616', '95622', '21178', '70953']):
                    chunk_urls.append(src if src.startswith('http') else "https://ssl.pstatic.net" + src)

            discovered_apis = set()
            for c_url in chunk_urls[:3]:
                try:
                    c_res = requests.get(c_url, headers=COMMON_HEADERS, timeout=2.5)
                    if c_res.status_code == 200:
                        for m in re.findall(r'["\'`](/(?:front-api|api)/[^"\'`\s]{4,90})["\'`]', c_res.text):
                            if any(w in m.lower() for w in ['discuss', 'post', 'board', 'comment']):
                                clean_p = re.sub(r'\$\{[^}]+\}', ticker_code, m)
                                discovered_apis.add("https://m.stock.naver.com" + clean_p)
                except Exception:
                    continue

            for d_api in list(discovered_apis)[:4]:
                test_url = d_api if '?' in d_api else f"{d_api}?discussionType=localStock&itemCode={ticker_code}&code={ticker_code}&pageSize=20&size=20"
                try:
                    d_res = requests.get(test_url, headers=req_headers, timeout=2.5)
                    if d_res.status_code == 200 and ('{' in d_res.text or '[' in d_res.text):
                        extracted = extract_posts_from_any_json(d_res.json(), ticker_code)
                        if extracted:
                            return extracted[:20]
                except Exception:
                    continue
    except Exception:
        pass

    # 3단계: PC 구형 게시판 및 종목 메인 페이지(item/main.naver) SSR 영역 파싱
    for pc_url in [
        f"https://finance.naver.com/item/board.naver?code={ticker_code}",
        f"https://finance.naver.com/item/main.naver?code={ticker_code}"
    ]:
        try:
            res = requests.get(pc_url, headers={**COMMON_HEADERS, 'Referer': 'https://finance.naver.com/'}, timeout=3)
            soup = BeautifulSoup(decode_html(res), 'html.parser')
            for a_el in soup.select('table.type2 td.title a, .section.new_bbs a[href*="board_read"], a[href*="discussion/"]'):
                title = (a_el.get('title') or a_el.text or '').strip()
                if not title or len(title) < 2:
                    continue
                href = a_el.get('href', '')
                link = ("https://finance.naver.com" + href) if href.startswith('/item') else (
                    ("https://m.stock.naver.com" + href) if href.startswith('/domestic') else href
                )
                row = a_el.find_parent('tr') or a_el.find_parent('li')
                tds = row.select('td') if row else []
                date = tds[0].text.strip() if len(tds) > 0 else '실시간'
                views = tds[3].text.strip() if len(tds) > 3 else '-'
                good = tds[4].text.strip() if len(tds) > 4 else '-'
                bad = tds[5].text.strip() if len(tds) > 5 else '-'
                posts.append({
                    'title': title, 'desc': '', 'author': '주주',
                    'date': date, 'views': views, 'good': good, 'bad': bad,
                    'comments': '', 'link': link
                })
            if posts:
                return posts[:20]
        except Exception:
            continue

    # 서버 IP에서 차단될 경우 빈 리스트를 반환하여 브라우저(Client JS)가 실시간 페치하도록 위임
    return []

# --- 3. 뉴스 크롤링 & 우선순위 기반 정밀 분류기 ---
STOP_WORDS = {'더본코리아', '더본', '백종원', '백종원의', '대표', '빽다방', '홍콩반점', '프랜차이즈', '외식', '진행', '운영', '출시'}

def extract_tokens(title):
    clean_t = title.rsplit(' - ', 1)[0]
    words = re.findall(r'[가-힣A-Za-z0-9]{2,}', clean_t)
    return {w for w in words if w not in STOP_WORDS}

def classify_single_news(title):
    for rk in NEWS_KEYWORDS["RISK"]:
        if rk in title:
            return 'RISK', f'🚨 쟁점·리스크 ({rk})'
    for pk in NEWS_KEYWORDS["PR"]:
        if pk in title:
            return 'PR', f'🎺 자본언플·홍보 ({pk})'
    return 'GEN', '📰 일반동향'

def get_latest_news():
    raw_list = []
    seen_titles = set()

    for sort_mode in ['1', '0']:
        naver_q = quote("더본코리아 OR 백종원 OR 빽다방")
        naver_url = f"https://search.naver.com/search.naver?where=news&query={naver_q}&sort={sort_mode}"
        try:
            res = requests.get(naver_url, headers=COMMON_HEADERS, timeout=4.5)
            soup = BeautifulSoup(decode_html(res), 'html.parser')
            for item in soup.select('.news_area, .bx'):
                title_el = item.select_one('.news_tit') or item.select_one('a[href*="news.naver.com"]')
                if not title_el:
                    continue
                title = (title_el.get('title') or title_el.text or '').strip()
                if not title or any(sp in title for sp in NEWS_KEYWORDS["SPAM"]):
                    continue
                if not any(k in title for k in ['백종원', '더본', '빽다방', '소유진', '홍콩반점', '연돈', '새마을식당']):
                    continue
                key = re.sub(r'\W+', '', title)[:18]
                if key in seen_titles:
                    continue
                seen_titles.add(key)

                link = title_el.get('href', '#')
                press_el = item.select_one('.info.press') or item.select_one('.press')
                press = press_el.text.replace('언론사 선정', '').strip() if press_el else '언론보도'
                info_spans = item.select('span.info')
                date_str = info_spans[-1].text.strip() if info_spans else '최신'
                raw_list.append({'pure_title': title, 'press': press, 'link': link, 'date': date_str})
        except Exception:
            pass

    q_encoded = quote("백종원 OR 더본코리아 OR 빽다방 OR 홍콩반점 when:7d")
    rss_url = f"https://news.google.com/rss/search?q={q_encoded}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(rss_url, headers=COMMON_HEADERS, timeout=5)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:60]:
            full_t = entry.title
            if any(sp in full_t for sp in NEWS_KEYWORDS["SPAM"]):
                continue
            parts = full_t.rsplit(' - ', 1)
            pure_t = parts[0].strip()
            press = parts[1].strip() if len(parts) > 1 else '뉴스'
            if not any(k in pure_t for k in ['백종원', '더본', '빽다방', '소유진', '홍콩반점', '연돈', '새마을식당']):
                continue
            key = re.sub(r'\W+', '', pure_t)[:18]
            if key in seen_titles:
                continue
            seen_titles.add(key)
            date_str = entry.published[5:16] if hasattr(entry, 'published') else ''
            raw_list.append({'pure_title': pure_t, 'press': press, 'link': entry.link, 'date': date_str})
    except Exception:
        pass

    if not raw_list:
        return [{'title': '뉴스 로딩 실패', 'pure_title': '뉴스 로딩 실패', 'link': '#', 'date': '-', 'cat_code': 'GEN', 'cat_label': '오류', 'dups': []}]

    clusters = []
    for item in raw_list:
        tokens = extract_tokens(item['pure_title'])
        matched_cluster = None
        for cl in clusters:
            if len(tokens & cl['tokens']) >= 3:
                matched_cluster = cl
                break
        if matched_cluster:
            if item['press'] != matched_cluster['main']['press'] and item['press'] not in [d['press'] for d in matched_cluster['dups']]:
                matched_cluster['dups'].append(item)
                matched_cluster['tokens'] |= tokens
        else:
            clusters.append({'main': item, 'tokens': tokens, 'dups': []})

    final_news = []
    for cl in clusters[:25]:
        main = cl['main']
        dups = cl['dups']
        all_titles_in_cluster = " ".join([main['pure_title']] + [d['pure_title'] for d in dups])
        cat_code, cat_label = classify_single_news(all_titles_in_cluster)
        
        total_cnt = 1 + len(dups)
        if total_cnt >= 3 and cat_code != 'RISK':
            cat_code = 'PR'
            cat_label = f"🎺 보도자료 복붙 ({total_cnt}건 살포)"
        elif total_cnt == 2 and cat_code == 'PR':
            cat_label = f"🎺 보도자료 복붙 (2건 살포)"
        elif total_cnt >= 2 and cat_code == 'RISK':
            cat_label = f"🚨 쟁점 확산 ({total_cnt}건 보도)"

        final_news.append({
            'title': f"{main['pure_title']} - {main['press']}",
            'pure_title': all_titles_in_cluster,
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
        res = requests.get(api_url, headers=COMMON_HEADERS, timeout=4)
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

    disclosures = []
    try:
        notice_url = f"https://finance.naver.com/item/news_notice.naver?code={ticker_code}&page=1"
        n_headers = {**COMMON_HEADERS, 'Referer': f"https://finance.naver.com/item/news.naver?code={ticker_code}"}
        n_res = requests.get(notice_url, headers=n_headers, timeout=4)
        n_soup = BeautifulSoup(decode_html(n_res), 'html.parser')
        for r in n_soup.select('table.type5 tr'):
            a_el = r.select_one('td.title a')
            if not a_el:
                continue
            d_title = a_el.text.strip()
            if not d_title:
                continue
            href = a_el.get('href', '')
            d_link = "https://finance.naver.com" + href if href.startswith('/') else href
            tds = r.select('td')
            d_info = tds[1].text.strip() if len(tds) > 1 else '공시'
            d_date = tds[2].text.strip() if len(tds) > 2 else ''
            disclosures.append({'title': d_title, 'link': d_link, 'info': d_info, 'date': d_date})
            if len(disclosures) >= 5:
                break
    except Exception:
        pass

    stock_info['disclosures'] = disclosures
    return stock_info

# --- 5. 유튜브 채널 고유 업로드 플레이리스트(VLUU) 수집 ---
YOUTUBE_CHANNELS = [
    {
        "name": "김재환의 오재나", "group": "CRITIC",
        "handle": "https://www.youtube.com/@studio_OZN",
        "id": "", "sample_vid": "0Gsvn_I6z1w",
        "fallback": [
            {"vid": "0Gsvn_I6z1w", "title": "안티 댓글을 양산하는 더본코리아와 정솔의 마법 #백종원 #김재환 #종토방고소위협 #오재나", "date": "2026-10-21", "views": "583,154회"},
            {"vid": "4fALTQTUldU", "title": "연돈볼카츠 합의안 타결! 나머지 점주들은 신났을까? #백종원 #김재환 #더본코리아", "date": "2026-10-05", "views": "1,462,077회"},
            {"vid": "X-RHoJtJz3Q", "title": "홍콩반점 점주들은 소송이 장난인가? #오재나 #김재환PD #백종원 #더본코리아", "date": "2026-09-16", "views": "708,169회"}
        ]
    },
    {
        "name": "탐코 : 탐욕의 코리아", "group": "CRITIC",
        "handle": "https://www.youtube.com/channel/UC1rn5BnUdP1OGI6vnxh0IbQ",
        "id": "UC1rn5BnUdP1OGI6vnxh0IbQ", "sample_vid": "DQ3qTgVC9os",
        "fallback": [
            {"vid": "DQ3qTgVC9os", "title": "백종원 운명을 결정할 소송", "date": "2026-10-24", "views": "234,087회"},
            {"vid": "NryKk-8AvPY", "title": "더본코리아를 공정위에 고발합니다", "date": "2026-10-23", "views": "227,784회"},
            {"vid": "3jU0OGvghkA", "title": "백종원과 위생", "date": "2026-10-17", "views": "306,959회"}
        ]
    },
    {
        "name": "백종원 본채널", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@paik_jongwon",
        "id": "UCyn-K7rZLXjGl7VXGweIlcA", "sample_vid": "pON-SAEgYUY",
        "fallback": [
            {"vid": "pON-SAEgYUY", "title": "[출장 중 배고파_청두] \"짜장면에 춘장이 안 들어간다고?\" 청두 올 때마다 무조건 찾는 영혼의 비빔면!", "date": "2026-10-21", "views": "448,386회"},
            {"vid": "bFX5lJgCPBQ", "title": "쌀쌀한 가을에 당면만둣국 한 그릇", "date": "2026-10-20", "views": "426,194회"},
            {"vid": "w53qGlJ1vLI", "title": "막창을 튀겨서 짬뽕에 넣었습니다!", "date": "2026-10-08", "views": "870,363회"}
        ]
    },
    {
        "name": "TBK (글로벌소스)", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@TBK_theborn",
        "id": "UCbgdcVitzVvWdngVx3OYTmA", "sample_vid": "FfC_pNkyaT8",
        "fallback": [
            {"vid": "FfC_pNkyaT8", "title": "Kimchi Egg Ramyun With Mild Paik Ramyun", "date": "2026-10-13", "views": "1,711회"},
            {"vid": "-wHsjUnhoL4", "title": "Dumpling Ramyun with Mild Paik Ramyun", "date": "2026-10-13", "views": "356회"},
            {"vid": "fCRzCl-gqOg", "title": "Mala Ramyun With Mild Paik Ramyun", "date": "2026-10-13", "views": "1,247회"}
        ]
    },
    {
        "name": "더본 테이스티", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@theborn_tasty",
        "id": "", "sample_vid": "gazC1wTYt3k",
        "fallback": [
            {"vid": "gazC1wTYt3k", "title": "침샘 폭발 주의! 대구의 맛, 막창짬뽕 화보 영상 🎬", "date": "2026-10-19", "views": "111,744회"},
            {"vid": "GdNx1GQAG_A", "title": "찾았다! 연돈튀김덮밥 할인 소식🫶", "date": "2026-09-29", "views": "27,791회"},
            {"vid": "7Om-LNDRQgw", "title": "연돈튀김덮밥 도시락 속 들리는 소리는?!", "date": "2026-09-28", "views": "306회"}
        ]
    },
    {
        "name": "더본 NOW", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@theborn_now",
        "id": "", "sample_vid": "nY3ibLP2xbo",
        "fallback": [
            {"vid": "nY3ibLP2xbo", "title": "바비큐부터 아이스크림까지 무료?!🔥 창녕 산토끼밥상의 특별한 여름", "date": "2026-10-06", "views": "579회"},
            {"vid": "tGLX12qPsyg", "title": "어디든 달려갑니다! 더본 푸드트럭 삼총사 전격 해부 🔍", "date": "2026-07-02", "views": "1,299회"}
        ]
    }
]

INNERTUBE_CONTEXT = {
    "client": {"hl": "ko", "gl": "KR", "clientName": "WEB", "clientVersion": "2.20251020.01.00"}
}

def format_view_text(v_str):
    v_str = v_str.replace('조회수', '').strip()
    if not v_str:
        return '집계중'
    if not v_str.endswith('회') and not v_str.endswith('중'):
        return v_str + '회'
    return v_str

def resolve_exact_channel_id(ch):
    if ch.get('id'):
        return ch['id']
    try:
        r_url = "https://www.youtube.com/youtubei/v1/navigation/resolve_url?prettyPrint=false"
        payload = {"context": INNERTUBE_CONTEXT, "url": ch['handle']}
        res = requests.post(r_url, json=payload, headers=COMMON_HEADERS, timeout=3)
        if res.status_code == 200:
            cid = res.json().get('endpoint', {}).get('browseEndpoint', {}).get('browseId', '')
            if cid.startswith('UC'):
                ch['id'] = cid
                return cid
    except Exception:
        pass
    if ch.get('sample_vid'):
        try:
            p_url = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
            payload = {"context": INNERTUBE_CONTEXT, "videoId": ch['sample_vid']}
            res = requests.post(p_url, json=payload, headers=COMMON_HEADERS, timeout=3)
            if res.status_code == 200:
                cid = res.json().get('videoDetails', {}).get('channelId', '')
                if cid.startswith('UC'):
                    ch['id'] = cid
                    return cid
        except Exception:
            pass
    return ""

def parse_playlist_and_video_renderers(data, max_count=3):
    videos = []
    seen_vids = set()
    def walk(obj):
        if len(videos) >= max_count:
            return
        if isinstance(obj, dict):
            if 'playlistVideoRenderer' in obj:
                pvr = obj['playlistVideoRenderer']
                vid = pvr.get('videoId', '')
                if vid and vid not in seen_vids:
                    t_runs = pvr.get('title', {}).get('runs', [])
                    title = t_runs[0].get('text', '') if t_runs else pvr.get('title', {}).get('simpleText', '')
                    info_runs = [r.get('text', '') for r in pvr.get('videoInfo', {}).get('runs', [])]
                    views, pub = '집계중', '최신'
                    for ir in info_runs:
                        if '조회수' in ir or '회' in ir or '천' in ir or '만' in ir:
                            views = format_view_text(ir)
                        elif '전' in ir or '방금' in ir or '오늘' in ir:
                            pub = ir.strip()
                    if title:
                        seen_vids.add(vid)
                        videos.append({
                            'title': title, 'link': f"https://www.youtube.com/watch?v={vid}",
                            'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg", 'date': pub, 'views': views
                        })
            elif 'videoRenderer' in obj:
                vr = obj['videoRenderer']
                vid = vr.get('videoId', '')
                if vid and vid not in seen_vids:
                    t_runs = vr.get('title', {}).get('runs', [])
                    title = t_runs[0].get('text', '') if t_runs else vr.get('title', {}).get('simpleText', '')
                    pub = vr.get('publishedTimeText', {}).get('simpleText', '최신')
                    v_raw = vr.get('viewCountText', {}).get('simpleText', '') or "".join(r.get('text', '') for r in vr.get('viewCountText', {}).get('runs', []))
                    views = format_view_text(v_raw)
                    if title:
                        seen_vids.add(vid)
                        videos.append({
                            'title': title, 'link': f"https://www.youtube.com/watch?v={vid}",
                            'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg", 'date': pub, 'views': views
                        })
            else:
                for v in obj.values(): walk(v)
        elif isinstance(obj, list):
            for item in obj: walk(item)
    walk(data)
    return videos

def fetch_single_channel(ch):
    cid = resolve_exact_channel_id(ch)
    vids = []
    b_url = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false"
    if cid.startswith('UC'):
        uploads_playlist_id = "VLUU" + cid[2:]
        try:
            payload = {"context": INNERTUBE_CONTEXT, "browseId": uploads_playlist_id}
            res = requests.post(b_url, json=payload, headers=COMMON_HEADERS, timeout=3.5)
            if res.status_code == 200:
                vids = parse_playlist_and_video_renderers(res.json(), 3)
        except Exception:
            pass
    if not vids:
        for item in ch.get('fallback', []):
            vid = item['vid']
            vids.append({
                'title': item['title'], 'link': f"https://www.youtube.com/watch?v={vid}",
                'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg", 'date': item['date'], 'views': item['views']
            })
    return {'name': ch['name'], 'group': ch['group'], 'handle': ch['handle'], 'videos': vids}

# --- 6. HTML 대시보드 생성 (레이더 & 뉴스 양방향 키워드 매니저 + 종토방 실시간 브라우저 페치) ---
def generate_html_string():
    with ThreadPoolExecutor(max_workers=10) as executor:
        f_dc = executor.submit(get_dc_best_posts)
        f_jt = executor.submit(get_naver_jongtobang)
        f_news = executor.submit(get_latest_news)
        f_stock = executor.submit(get_stock_and_disclosures)
        f_yt = [executor.submit(fetch_single_channel, ch) for ch in YOUTUBE_CHANNELS]

        dc_posts = f_dc.result()
        jongto_posts = f_jt.result()
        news = f_news.result()
        stock = f_stock.result()
        youtube_data = [f.result() for f in f_yt]

    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M:%S")

    # 브라우저 실시간 레이더 랭킹 연산을 위한 전체 제목 리스트 전달
    all_titles_for_radar = (
        [p['title'] for p in dc_posts if '실패' not in p['title']] +
        [j['title'] for j in jongto_posts] +
        [n['title'].rsplit(' - ', 1)[0] for n in news if '실패' not in n['title']]
    )

    dc_html = ""
    for p in dc_posts:
        dc_html += f"""
        <li>
            <div class="meta-line">{p['date']} | 조회 {p['views']} | <span style="color:#ff5252; font-weight:bold;">추천 {p['upvotes']}</span></div>
            <a href="{p['link']}" target="_blank">{p['title']} <span style="color:#4fc3f7; font-weight:bold;">{p['comments']}</span></a>
        </li>
        """

    jt_html = ""
    if jongto_posts:
        for j in jongto_posts:
            desc_div = f"<div class='jt-desc'>{j['desc']}</div>" if j.get('desc') else ""
            jt_html += f"""
            <li>
                <div class="meta-line">{j['date']} | {j.get('author', '주주')} | 조회 {j['views']} | <span style="color:#ff8a65;">👍 {j['good']}</span> · <span style="color:#90caf9;">👎 {j['bad']}</span></div>
                <a href="{j['link']}" target="_blank" style="font-weight:bold;">{j['title']} <span style="color:#ffd54f;">{j['comments']}</span></a>
                {desc_div}
            </li>
            """

    news_html = ""
    for n in news:
        badge_class = "badge-risk" if n['cat_code'] == 'RISK' else ("badge-pr" if n['cat_code'] == 'PR' else "badge-gen")
        dup_cnt = len(n.get('dups', []))
        dup_html = ""
        if dup_cnt > 0:
            dup_links = ", ".join([f"<a href='{d['link']}' target='_blank' style='color:#ffd54f; font-size:0.85em;'>{d['press']}</a>" for d in n['dups'][:8]])
            dup_html = f"<div class='dup-box' style='margin-top:5px; padding:6px 10px; background:#12141a; border-left:3px solid #ffd54f; font-size:0.82em; color:#aaa;'>📢 동일 보도자료 복붙 언론사 ({dup_cnt}곳): {dup_links}</div>"
        
        safe_raw = n.get('pure_title', n['title']).replace('"', '&quot;')
        news_html += f"""
        <li class="news-item" data-cat="{n['cat_code']}" data-dups="{dup_cnt}" data-raw="{safe_raw}">
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
        disc_html = "<li><a href='https://dart.fss.or.kr/' target='_blank' style='color:#888;'>최근 신규 공시 없음 (DART 바로가기 ↗)</a></li>"

    yt_critic_html = ""
    yt_official_html = ""
    for ch in youtube_data:
        block = f"<div class='channel-name'><a href='{ch['handle']}' target='_blank'>[{ch['name']}] ↗</a></div>"
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

    default_news_kw_json = json.dumps(NEWS_KEYWORDS, ensure_ascii=False)
    default_radar_kw_json = json.dumps(RADAR_KEYWORDS, ensure_ascii=False)
    raw_titles_json = json.dumps(all_titles_for_radar, ensure_ascii=False)
    has_server_jt = "true" if jongto_posts else "false"

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

        /* 상단 실시간 이슈 핵심 명사 레이더 바 */
        .radar-wrapper {{ max-width: 1700px; margin: 0 auto 20px auto; }}
        .radar-bar {{ background: #14171f; border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 18px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }}
        .radar-left {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; flex: 1; }}
        .radar-title {{ color: var(--accent-gold); font-weight: bold; font-size: 0.95em; margin-right: 4px; }}
        .kw-badge {{ background: #232834; color: #d0d7de; padding: 5px 11px; border-radius: 20px; font-size: 0.85em; border: 1px solid #343b4a; display: inline-flex; align-items: center; gap: 5px; }}
        .kw-badge.boosted {{ border-color: rgba(255, 213, 79, 0.5); background: rgba(255, 213, 79, 0.08); }}
        .kw-badge b {{ color: var(--accent-red); }}
        .kw-ban-x {{ color: #768390; cursor: pointer; font-size: 0.9em; margin-left: 2px; padding: 0 2px; }}
        .kw-ban-x:hover {{ color: #ff5252; font-weight: bold; }}

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

        /* 키워드 매니저 공통 스타일 */
        .kw-mgr-btn {{ background: #262c3a; color: var(--accent-gold); border: 1px solid #3d4659; padding: 5px 11px; border-radius: 6px; cursor: pointer; font-size: 0.78em; font-weight: bold; flex-shrink: 0; }}
        .kw-mgr-btn:hover {{ background: #323a4d; }}
        .kw-manager-panel {{ display: none; background: #12151c; border: 1px solid #343b4a; border-radius: 8px; padding: 14px; margin-top: 10px; margin-bottom: 14px; }}
        .kw-sec-title {{ font-size: 0.8em; font-weight: bold; margin: 10px 0 6px 0; display: flex; justify-content: space-between; align-items: center; }}
        .kw-sec-title:first-child {{ margin-top: 0; }}
        .kw-input-row {{ display: flex; gap: 6px; margin-bottom: 8px; }}
        .kw-input {{ flex: 1; background: #1b1f29; border: 1px solid #343b4a; color: #fff; padding: 5px 9px; border-radius: 5px; font-size: 0.8em; }}
        .kw-add-btn {{ background: #2d3546; color: #fff; border: 1px solid #455068; padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 0.78em; font-weight: bold; }}
        .kw-tag-wrap {{ display: flex; flex-wrap: wrap; gap: 5px; max-height: 95px; overflow-y: auto; padding: 4px 0; }}
        .kw-edit-tag {{ padding: 2px 7px; border-radius: 4px; font-size: 0.75em; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; user-select: none; }}
        .kw-edit-tag:hover {{ opacity: 0.8; text-decoration: line-through; }}
        .kw-mgr-footer {{ display: flex; justify-content: space-between; gap: 6px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed #2a2f3a; flex-wrap: wrap; }}

        .chart-img {{ width: 100%; border-radius: 8px; filter: invert(0.9) hue-rotate(180deg); border: 1px solid #333; }}

        .scroll-list {{ list-style: none; padding: 0; margin: 0; max-height: 620px; overflow-y: auto; padding-right: 5px; }}
        .scroll-list::-webkit-scrollbar {{ width: 6px; }}
        .scroll-list::-webkit-scrollbar-thumb {{ background: #343b4a; border-radius: 3px; }}
        .scroll-list li {{ padding: 11px 0; border-bottom: 1px solid #232730; }}
        .scroll-list li:last-child {{ border-bottom: none; }}
        .meta-line {{ font-size: 0.8em; color: var(--text-muted); margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }}

        .jt-desc {{ font-size: 0.83em; color: #9ea7b3; margin-top: 4px; line-height: 1.35; }}

        .n-badge {{ padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: bold; }}
        .badge-risk {{ background: rgba(255, 82, 82, 0.2); color: #ff5252; border: 1px solid rgba(255, 82, 82, 0.4); }}
        .badge-pr {{ background: rgba(255, 213, 79, 0.15); color: #ffd54f; border: 1px solid rgba(255, 213, 79, 0.4); }}
        .badge-gen {{ background: rgba(79, 195, 247, 0.15); color: #4fc3f7; border: 1px solid rgba(79, 195, 247, 0.3); }}

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
        <div class="update-time">마지막 업데이트: {current_time}</div>
    </div>

    <!-- 실시간 이슈 핵심 명사 레이더 바 + 수동 키워드 설정 패널 -->
    <div class="radar-wrapper">
        <div class="radar-bar">
            <div class="radar-left">
                <span class="radar-title">🔥 실시간 이슈 핵심 명사 (× 클릭 시 즉시 제외):</span>
                <span id="radarBadgesContainer" style="display:contents;"></span>
            </div>
            <button class="kw-mgr-btn" onclick="togglePanel('radarManagerPanel')">⚙️ 핵심명사 관리</button>
        </div>

        <div id="radarManagerPanel" class="kw-manager-panel">
            <div class="kw-sec-title" style="color:#ffd54f;">
                <span>📌 우선 추출·보존 핵심 명사 (복합명사 쪼개짐 방지 · 클릭 시 삭제)</span>
            </div>
            <div class="kw-input-row">
                <input type="text" id="inputRadarBoost" class="kw-input" placeholder="우선 추출할 핵심 명사 입력 (예: 우지커피, 당근페이, 순감소)" onkeydown="if(event.key==='Enter') addRadarKw('BOOST')">
                <button class="kw-add-btn" onclick="addRadarKw('BOOST')">+ 추가</button>
            </div>
            <div id="tagsRadarBoost" class="kw-tag-wrap"></div>

            <div class="kw-sec-title" style="color:#ff5252;">
                <span>🚫 레이더 랭킹 제외 불용어 (포함 시 랭킹에서 즉시 숨김 · 클릭 시 복원)</span>
            </div>
            <div class="kw-input-row">
                <input type="text" id="inputRadarStop" class="kw-input" placeholder="랭킹에서 뺄 단어 입력 (예: 근데, 브랜드, 식당)" onkeydown="if(event.key==='Enter') addRadarKw('STOP')">
                <button class="kw-add-btn" onclick="addRadarKw('STOP')">+ 제외 추가</button>
            </div>
            <div id="tagsRadarStop" class="kw-tag-wrap"></div>

            <div class="kw-mgr-footer">
                <button class="kw-add-btn" style="background:#1f2937; color:#9ca3af;" onclick="resetRadarDefault()">↺ 명사 설정 초기화</button>
                <button class="kw-add-btn" style="background:#0284c7; border-color:#0369a1;" onclick="copyAllPythonConfig()">📋 전체 파이썬 설정 코드 복사 (NEWS + RADAR)</button>
            </div>
        </div>
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

        <!-- 2. 뉴스 동향 + 사용자 직접 키워드 관리 매니저 -->
        <div class="card">
            <h2>
                <span>📰 실시간 뉴스 판독기</span>
                <button class="kw-mgr-btn" onclick="togglePanel('kwManagerPanel')">⚙️ 키워드 관리</button>
            </h2>

            <div id="kwManagerPanel" class="kw-manager-panel" style="margin-top:0;">
                <div class="kw-sec-title" style="color:#ff5252;">
                    <span>🚨 쟁점·리스크 키워드 (최우선 적용 · 클릭 시 삭제)</span>
                </div>
                <div class="kw-input-row">
                    <input type="text" id="inputRiskKw" class="kw-input" placeholder="리스크 단어 입력 (예: 휘청, 급감, 태극기)" onkeydown="if(event.key==='Enter') addNewsKw('RISK')">
                    <button class="kw-add-btn" onclick="addNewsKw('RISK')">+ 추가</button>
                </div>
                <div id="tagsRisk" class="kw-tag-wrap"></div>

                <div class="kw-sec-title" style="color:#ffd54f;">
                    <span>🎺 자본언플·홍보 키워드 (클릭 시 삭제)</span>
                </div>
                <div class="kw-input-row">
                    <input type="text" id="inputPrKw" class="kw-input" placeholder="언플 단어 입력 (예: 승부수, 뚫는다, 시연)" onkeydown="if(event.key==='Enter') addNewsKw('PR')">
                    <button class="kw-add-btn" onclick="addNewsKw('PR')">+ 추가</button>
                </div>
                <div id="tagsPr" class="kw-tag-wrap"></div>

                <div class="kw-sec-title" style="color:#9ea7b3;">
                    <span>🚫 스팸·목록 제외 키워드 (포함 시 뉴스 숨김)</span>
                </div>
                <div class="kw-input-row">
                    <input type="text" id="inputSpamKw" class="kw-input" placeholder="제외할 단어 입력" onkeydown="if(event.key==='Enter') addNewsKw('SPAM')">
                    <button class="kw-add-btn" onclick="addNewsKw('SPAM')">+ 추가</button>
                </div>
                <div id="tagsSpam" class="kw-tag-wrap"></div>

                <div class="kw-mgr-footer">
                    <button class="kw-add-btn" style="background:#1f2937; color:#9ca3af;" onclick="resetNewsDefault()">↺ 뉴스 설정 초기화</button>
                    <button class="kw-add-btn" style="background:#0284c7; border-color:#0369a1;" onclick="copyAllPythonConfig()">📋 전체 파이썬 설정 코드 복사</button>
                </div>
            </div>

            <div class="tab-group" id="newsFilterTabs">
                <button class="tab-btn active" data-filter="ALL" onclick="filterNews('ALL', this)">전체보기</button>
                <button class="tab-btn" data-filter="RISK" onclick="filterNews('RISK', this)">🚨 쟁점·리스크</button>
                <button class="tab-btn" data-filter="PR" onclick="filterNews('PR', this)">🎺 자본언플·복붙</button>
                <button class="tab-btn" data-filter="GEN" onclick="filterNews('GEN', this)">📰 일반동향</button>
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
            <h2>🦅 골목식당 갤러리 개념글 (실시간 파묘 50선)</h2>
            <ul class="scroll-list" style="max-height: 600px; display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px;">
                {dc_html}
            </ul>
        </div>

        <div class="card">
            <h2>
                <span>🤬 네이버 종토방 실시간 민심</span>
                <a href="https://m.stock.naver.com/domestic/stock/475560/discussion" target="_blank" style="font-size:0.75em; color:#ffd54f;">Npay 토론방 ↗</a>
            </h2>
            <div id="jtStatusBanner" style="font-size:0.8em; color:#8b949e; margin-bottom:8px;"></div>
            <ul class="scroll-list" id="jongtoList" style="max-height: 560px;">
                {jt_html}
            </ul>
        </div>
    </div>

    <script>
        const DEFAULT_NEWS_KW = {default_news_kw_json};
        const DEFAULT_RADAR_KW = {default_radar_kw_json};
        const RAW_TITLES = {raw_titles_json};
        const HAS_SERVER_JT = {has_server_jt};

        const NEWS_STORAGE_KEY = 'theborn_news_kw_v6';
        const RADAR_STORAGE_KEY = 'theborn_radar_kw_v6';

        let currentFilter = 'ALL';
        let userNewsKw = loadStored(NEWS_STORAGE_KEY, DEFAULT_NEWS_KW);
        let userRadarKw = loadStored(RADAR_STORAGE_KEY, DEFAULT_RADAR_KW);

        function loadStored(key, fallbackObj) {{
            try {{
                const saved = localStorage.getItem(key);
                if (saved) return JSON.parse(saved);
            }} catch (e) {{}}
            return JSON.parse(JSON.stringify(fallbackObj));
        }}

        function togglePanel(id) {{
            const el = document.getElementById(id);
            el.style.display = (el.style.display === 'block') ? 'none' : 'block';
        }}

        // --- 1. 실시간 이슈 핵심 명사(레이더) 랭킹 엔진 ---
        const JOSA_REGEX = /(에서부터|으로부터|에서|으로|이랑|하고|부터|까지|마저|조차|에게|한테|처럼|보다|라고|이라|다는|라는|은|는|이|가|을|를|의|에|로|과|와|도|만|한|할|함|임)$/;
        const PRED_REGEX = /(있다|없다|같다|되다|하다|이다|봤다|왔다|갔다|했다|됐다|난다|준다|본다|한다|된다|하면|되면|오면|가면|보면|치면|쓰면|알면|나면|주면|받으면|먹으면|겠냐|겠노|겠네|하노|하냐|하나|할까|볼까|하자|해라|마라|거임|건가|인듯|인가|구만|구나|던데|는데|길래|잖아|더라|봐유|애유|네유|햇네|했네)$/;

        function normalizeNoun(word, stopSet, boostList) {{
            let w = word.toLowerCase().replace(/[ㄱ-ㅎㅏ-ㅣ]+/g, '');
            if (w.length < 2 || /^\\d+$/.test(w) || /^\\d+[월일편명개년배위곳잔만원호%]+$/.test(w)) return '';
            if (stopSet.has(w) || PRED_REGEX.test(w)) return '';

            // 우선 추출(BOOST) 명사가 단어 시작부에 포함되어 있으면 원형 그대로 보존
            for (const bw of boostList) {{
                const bLow = bw.toLowerCase();
                if (w === bLow || (w.startsWith(bLow) && w.length <= bLow.length + 2)) {{
                    return bw;
                }}
            }}

            let stemmed = w.replace(JOSA_REGEX, '');
            if (stemmed.length >= 2) w = stemmed;
            if (stopSet.has(w) || PRED_REGEX.test(w)) return '';
            if (w.length >= 3 && (w.endsWith('군') || w.endsWith('시') || w.endsWith('점')) && !/(장군|교시|폐점|출점|지점|반점)$/.test(w)) {{
                w = w.slice(0, -1);
            }}
            return stopSet.has(w) ? '' : w;
        }}

        function recomputeRadarKeywords() {{
            const stopSet = new Set(userRadarKw.STOP.map(s => s.toLowerCase()));
            const boostList = userRadarKw.BOOST || [];
            const boostSet = new Set(boostList.map(b => b.toLowerCase()));
            const freq = {{}};

            RAW_TITLES.forEach(title => {{
                const perTitleSet = new Set();
                // 1) 우선 추출(BOOST) 명사 직접 매칭
                boostList.forEach(bw => {{
                    if (title.toLowerCase().includes(bw.toLowerCase()) && !stopSet.has(bw.toLowerCase())) {{
                        perTitleSet.add(bw);
                    }}
                }});
                // 2) 일반 어절 형태소 정규화 추출
                const matches = title.match(/[가-힣A-Za-z0-9]{{2,}}/g) || [];
                matches.forEach(rawW => {{
                    const norm = normalizeNoun(rawW, stopSet, boostList);
                    if (norm && norm.length >= 2) perTitleSet.add(norm);
                }});
                perTitleSet.forEach(token => {{
                    freq[token] = (freq[token] || 0) + 1;
                }});
            }});

            // 접두사 병합 (짧은 핵심 명사로 통합)
            const keys = Object.keys(freq).sort((a, b) => a.length - b.length);
            const merged = {{}};
            const stemMap = {{}};
            keys.forEach(word => {{
                let target = word;
                for (const shorter of keys) {{
                    if (shorter !== word && shorter.length >= 2 && word.toLowerCase().startsWith(shorter.toLowerCase())) {{
                        target = stemMap[shorter] || shorter;
                        break;
                    }}
                }}
                stemMap[word] = target;
                merged[target] = (merged[target] || 0) + freq[word];
            }});

            const sorted = Object.entries(merged)
                .filter(([_, cnt]) => cnt >= 2)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 12);

            const container = document.getElementById('radarBadgesContainer');
            if (!sorted.length) {{
                container.innerHTML = "<span class='kw-badge'>#집계된중복명사없음</span>";
                return;
            }}
            container.innerHTML = sorted.map(([kw, cnt]) => {{
                const isBoost = boostSet.has(kw.toLowerCase());
                return `<span class="kw-badge ${{isBoost ? 'boosted' : ''}}">
                    #${{kw}} <b>${{cnt}}</b>
                    <span class="kw-ban-x" title="'${{kw}}' 키워드를 레이더에서 즉시 제외" onclick="banRadarWord('${{kw}}')">×</span>
                </span>`;
            }}).join('');
        }}

        function banRadarWord(word) {{
            if (!userRadarKw.STOP.includes(word)) {{
                userRadarKw.STOP.unshift(word);
                saveRadarKw();
            }}
        }}

        function saveRadarKw() {{
            localStorage.setItem(RADAR_STORAGE_KEY, JSON.stringify(userRadarKw));
            renderRadarTags();
            recomputeRadarKeywords();
        }}

        function renderRadarTags() {{
            document.getElementById('tagsRadarBoost').innerHTML = userRadarKw.BOOST.map((kw, idx) =>
                `<span class="kw-edit-tag badge-pr" title="클릭하여 삭제" onclick="removeRadarKw('BOOST', ${{idx}})">${{kw}} ×</span>`
            ).join('');
            document.getElementById('tagsRadarStop').innerHTML = userRadarKw.STOP.map((kw, idx) =>
                `<span class="kw-edit-tag badge-risk" title="클릭하여 제외 해제" onclick="removeRadarKw('STOP', ${{idx}})">${{kw}} ×</span>`
            ).join('');
        }}

        function addRadarKw(type) {{
            const input = document.getElementById(type === 'BOOST' ? 'inputRadarBoost' : 'inputRadarStop');
            const raw = input.value.trim();
            if (!raw) return;
            raw.split(',').map(s => s.trim()).filter(Boolean).forEach(w => {{
                if (!userRadarKw[type].includes(w)) userRadarKw[type].unshift(w);
            }});
            input.value = '';
            saveRadarKw();
        }}

        function removeRadarKw(type, idx) {{
            userRadarKw[type].splice(idx, 1);
            saveRadarKw();
        }}

        function resetRadarDefault() {{
            localStorage.removeItem(RADAR_STORAGE_KEY);
            userRadarKw = JSON.parse(JSON.stringify(DEFAULT_RADAR_KW));
            renderRadarTags();
            recomputeRadarKeywords();
        }}

        // --- 2. 뉴스 키워드 분류 엔진 ---
        function saveNewsKw() {{
            localStorage.setItem(NEWS_STORAGE_KEY, JSON.stringify(userNewsKw));
            renderNewsTags();
            reclassifyAllNews();
        }}

        function renderNewsTags() {{
            const renderGroup = (type, elId, cls) => {{
                document.getElementById(elId).innerHTML = userNewsKw[type].map((kw, idx) =>
                    `<span class="kw-edit-tag ${{cls}}" title="클릭하여 삭제" onclick="removeNewsKw('${{type}}', ${{idx}})">${{kw}} ×</span>`
                ).join('');
            }};
            renderGroup('RISK', 'tagsRisk', 'badge-risk');
            renderGroup('PR', 'tagsPr', 'badge-pr');
            renderGroup('SPAM', 'tagsSpam', 'badge-gen');
        }}

        function addNewsKw(type) {{
            const inputId = type === 'RISK' ? 'inputRiskKw' : (type === 'PR' ? 'inputPrKw' : 'inputSpamKw');
            const input = document.getElementById(inputId);
            const raw = input.value.trim();
            if (!raw) return;
            raw.split(',').map(s => s.trim()).filter(Boolean).forEach(word => {{
                if (!userNewsKw[type].includes(word)) userNewsKw[type].unshift(word);
            }});
            input.value = '';
            saveNewsKw();
        }}

        function removeNewsKw(type, idx) {{
            userNewsKw[type].splice(idx, 1);
            saveNewsKw();
        }}

        function resetNewsDefault() {{
            localStorage.removeItem(NEWS_STORAGE_KEY);
            userNewsKw = JSON.parse(JSON.stringify(DEFAULT_NEWS_KW));
            renderNewsTags();
            reclassifyAllNews();
        }}

        function reclassifyAllNews() {{
            let counts = {{ ALL: 0, RISK: 0, PR: 0, GEN: 0 }};
            document.querySelectorAll('#newsList .news-item').forEach(li => {{
                const rawTitle = li.getAttribute('data-raw') || li.innerText;
                const dupCnt = parseInt(li.getAttribute('data-dups') || '0', 10);
                const totalCnt = 1 + dupCnt;

                if (userNewsKw.SPAM.some(sp => rawTitle.includes(sp))) {{
                    li.setAttribute('data-cat', 'SPAM');
                    li.style.display = 'none';
                    return;
                }}

                let cat = 'GEN';
                let label = '📰 일반동향';
                let matchedRisk = userNewsKw.RISK.find(rk => rawTitle.includes(rk));
                let matchedPr = userNewsKw.PR.find(pk => rawTitle.includes(pk));

                if (matchedRisk) {{
                    cat = 'RISK';
                    label = totalCnt >= 2 ? `🚨 쟁점 확산 (${{totalCnt}}건 · ${{matchedRisk}})` : `🚨 쟁점·리스크 (${{matchedRisk}})`;
                }} else if (matchedPr) {{
                    cat = 'PR';
                    label = totalCnt >= 2 ? `🎺 보도자료 복붙 (${{totalCnt}}건 · ${{matchedPr}})` : `🎺 자본언플·홍보 (${{matchedPr}})`;
                }} else if (totalCnt >= 3) {{
                    cat = 'PR';
                    label = `🎺 보도자료 복붙 (${{totalCnt}}건 살포)`;
                }}

                li.setAttribute('data-cat', cat);
                const badgeEl = li.querySelector('.n-badge');
                if (badgeEl) {{
                    badgeEl.className = 'n-badge ' + (cat === 'RISK' ? 'badge-risk' : (cat === 'PR' ? 'badge-pr' : 'badge-gen'));
                    badgeEl.textContent = label;
                }}

                counts.ALL++;
                counts[cat]++;
                li.style.display = (currentFilter === 'ALL' || currentFilter === cat) ? 'block' : 'none';
            }});

            const tabLabels = {{
                ALL: `전체 (${{counts.ALL}})`,
                RISK: `🚨 리스크 (${{counts.RISK}})`,
                PR: `🎺 언플·복붙 (${{counts.PR}})`,
                GEN: `📰 일반 (${{counts.GEN}})`
            }};
            document.querySelectorAll('#newsFilterTabs .tab-btn').forEach(btn => {{
                const f = btn.getAttribute('data-filter');
                if (tabLabels[f]) btn.textContent = tabLabels[f];
            }});
        }}

        function copyAllPythonConfig() {{
            const pyCode = "NEWS_KEYWORDS = " + JSON.stringify(userNewsKw, null, 4) +
                           "\\n\\nRADAR_KEYWORDS = " + JSON.stringify(userRadarKw, null, 4);
            navigator.clipboard.writeText(pyCode).then(() => {{
                alert("✅ NEWS_KEYWORDS 및 RADAR_KEYWORDS 파이썬 코드가 복사되었습니다!\\n코드 최상단 설정 구역에 그대로 붙여넣으시면 됩니다.");
            }});
        }}

        // --- 3. 네이버 종토방 클라이언트 실시간 페치 (서버 IP 차단 시 브라우저가 직접 수집) ---
        async function fetchJongtoFromBrowser() {{
            if (HAS_SERVER_JT) return;
            const banner = document.getElementById('jtStatusBanner');
            const listEl = document.getElementById('jongtoList');
            banner.textContent = "🔄 브라우저에서 네이버 종토방 실시간 데이터를 불러오는 중...";

            const targetApis = [
                "https://m.stock.naver.com/api/discuss/localStock/475560?rsno=0&size=20",
                "https://m.stock.naver.com/front-api/discussion/list?discussionType=localStock&itemCode=475560&pageSize=20",
                "https://finance.naver.com/item/main.naver?code=475560"
            ];
            const proxies = [
                url => `https://api.allorigins.win/raw?url=${{encodeURIComponent(url)}}`,
                url => `https://api.codetabs.com/v1/proxy?quest=${{encodeURIComponent(url)}}`
            ];

            for (const api of targetApis) {{
                for (const makeProxy of proxies) {{
                    try {{
                        const res = await fetch(makeProxy(api));
                        if (!res.ok) continue;
                        const text = await res.text();

                        if (text.trim().startsWith('{{') || text.trim().startsWith('[')) {{
                            const data = JSON.parse(text);
                            const posts = [];
                            const walk = (obj) => {{
                                if (!obj || typeof obj !== 'object') return;
                                if (Array.isArray(obj)) {{ obj.forEach(walk); return; }}
                                const t = obj.title || obj.subject;
                                if (typeof t === 'string' && t.length >= 2 && (obj.discussionId || obj.nid || obj.readCount !== undefined || obj.viewCount !== undefined)) {{
                                    posts.push(obj);
                                }} else {{
                                    Object.values(obj).forEach(walk);
                                }}
                            }};
                            walk(data);
                            if (posts.length > 0) {{
                                banner.textContent = "✅ 실시간 연동 완료";
                                listEl.innerHTML = posts.slice(0, 20).map(p => {{
                                    const nid = p.discussionId || p.nid || p.articleId || '';
                                    const title = p.title || p.subject;
                                    const desc = (p.contents || p.summary || '').replace(/<[^>]+>/g, ' ').slice(0, 95);
                                    const date = String(p.date || p.writtenAt || '실시간').slice(0, 16);
                                    const views = p.readCount ?? p.viewCount ?? '-';
                                    const good = p.goodCount ?? p.recommendCount ?? p.sympathyCount ?? 0;
                                    const bad = p.badCount ?? p.notRecommendCount ?? p.antipathyCount ?? 0;
                                    const cmt = p.commentCount ? `[${{p.commentCount}}]` : '';
                                    const link = nid ? `https://m.stock.naver.com/domestic/stock/475560/discussion/${{nid}}` : `https://m.stock.naver.com/domestic/stock/475560/discussion`;
                                    RAW_TITLES.push(title);
                                    return `<li>
                                        <div class="meta-line">${{date}} | 조회 ${{views}} | <span style="color:#ff8a65;">👍 ${{good}}</span> · <span style="color:#90caf9;">👎 ${{bad}}</span></div>
                                        <a href="${{link}}" target="_blank" style="font-weight:bold;">${{title}} <span style="color:#ffd54f;">${{cmt}}</span></a>
                                        ${{desc ? `<div class="jt-desc">${{desc}}</div>` : ''}}
                                    </li>`;
                                }}).join('');
                                recomputeRadarKeywords();
                                return;
                            }}
                        }} else if (text.includes('board_read.naver')) {{
                            const parser = new DOMParser();
                            const doc = parser.parseFromString(text, 'text/html');
                            const links = Array.from(doc.querySelectorAll('a[href*="board_read.naver"]'));
                            if (links.length > 0) {{
                                banner.textContent = "✅ 네이버 증권 메인 실시간 연동 완료";
                                listEl.innerHTML = links.slice(0, 15).map(a => {{
                                    const title = a.getAttribute('title') || a.textContent.trim();
                                    const href = a.getAttribute('href');
                                    const link = href.startsWith('http') ? href : `https://finance.naver.com${{href}}`;
                                    RAW_TITLES.push(title);
                                    return `<li>
                                        <div class="meta-line">실시간 종토방</div>
                                        <a href="${{link}}" target="_blank" style="font-weight:bold;">${{title}}</a>
                                    </li>`;
                                }}).join('');
                                recomputeRadarKeywords();
                                return;
                            }}
                        }}
                    }} catch (e) {{}}
                }}
            }}
            banner.innerHTML = "⚠️ 네이버 Npay 토론방이 현재 클라이언트(브라우저) 직접 접속만 허용합니다. <a href='https://m.stock.naver.com/domestic/stock/475560/discussion' target='_blank' style='color:#4fc3f7; font-weight:bold;'>[여기를 눌러 실시간 종토방 열기 ↗]</a>";
        }}

        function switchChart(url, btn) {{
            document.getElementById('stockChartImg').src = url;
            btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }}

        function filterNews(cat, btn) {{
            currentFilter = cat;
            btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            reclassifyAllNews();
        }}

        function switchYtTab(group, btn) {{
            btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('ytCriticBox').style.display = (group === 'CRITIC') ? 'block' : 'none';
            document.getElementById('ytOfficialBox').style.display = (group === 'OFFICIAL') ? 'block' : 'none';
        }}

        // 초기 실행
        renderRadarTags();
        recomputeRadarKeywords();
        renderNewsTags();
        reclassifyAllNews();
        fetchJongtoFromBrowser();
    </script>
</body>
</html>
"""
    return html

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        try:
            html_content = generate_html_string()
            self.wfile.write(html_content.encode('utf-8'))
        except Exception as e:
            error_msg = f"<html><body style='background:#121212;color:#fff;'><h1>로딩 중 에러 발생</h1><p>{e}</p></body></html>"
            self.wfile.write(error_msg.encode('utf-8'))

if __name__ == "__main__":
    html_out = generate_html_string()
    with open("theborn_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    print("✅ theborn_dashboard.html V6 업데이트 완료!")
