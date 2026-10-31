import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
import re

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

def decode_html(res):
    """UTF-8 우선 디코딩 후 실패 시 CP949(EUC-KR)로 안전하게 디코딩합니다."""
    try:
        return res.content.decode('utf-8')
    except UnicodeDecodeError:
        return res.content.decode('cp949', 'replace')

# --- 1. 디시인사이드 골목식당 갤러리 개념글 크롤링 ---
def get_dc_best_posts():
    url = "https://gall.dcinside.com/board/lists/?id=bjwstreet&exception_mode=recommend"
    headers = {**COMMON_HEADERS, 'Referer': 'https://gall.dcinside.com/'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(decode_html(response), 'html.parser')
        posts = soup.select('.us-post')
        
        results = []
        for post in posts[:30]:
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

# --- 2. 네이버 종목토론방 (PC/모바일 다중 파싱 및 예외 격리) ---
def get_naver_jongtobang(ticker_code="475560"):
    results = []

    # 1순위: PC 네이버 금융 종목토론실 (정확한 자기 자신 Referer + td.title a 선택자)
    board_url = f"https://finance.naver.com/item/board.naver?code={ticker_code}&page=1"
    pc_headers = {
        **COMMON_HEADERS,
        'Referer': f"https://finance.naver.com/item/board.naver?code={ticker_code}"
    }
    try:
        res = requests.get(board_url, headers=pc_headers, timeout=4.5)
        soup = BeautifulSoup(decode_html(res), 'html.parser')
        for row in soup.select('table.type2 tr'):
            try:
                title_el = row.select_one('td.title a')
                if not title_el:
                    continue
                title = (title_el.get('title') or title_el.text or '').strip()
                if not title:
                    continue
                href = title_el.get('href', '')
                link = "https://finance.naver.com" + href if href.startswith('/') else href
                
                cmt_el = row.select_one('td.title span.tah')
                comments = cmt_el.text.strip() if cmt_el else ""
                
                tds = row.select('td')
                date = tds[0].text.strip() if len(tds) > 0 else '-'
                views = tds[3].text.strip() if len(tds) > 3 else '-'
                good = tds[4].text.strip() if len(tds) > 4 else '0'
                bad = tds[5].text.strip() if len(tds) > 5 else '0'
                
                results.append({
                    'title': title, 'link': link, 'comments': comments,
                    'date': date, 'views': views, 'good': good, 'bad': bad
                })
                if len(results) >= 20:
                    break
            except Exception:
                continue
        if results:
            return results
    except Exception:
        pass

    # 2순위: 모바일 증권 공식 JSON API (필수 파라미터 rsno=0&filter= 포함 및 개별 예외 처리)
    m_url = f"https://m.stock.naver.com/api/discuss/localStock/{ticker_code}?rsno=0&size=20&filter="
    m_headers = {
        **COMMON_HEADERS,
        'Referer': f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discuss",
        'Accept': 'application/json, text/plain, */*'
    }
    try:
        res = requests.get(m_url, headers=m_headers, timeout=4.5)
        if res.status_code == 200:
            data = res.json()
            items = data if isinstance(data, list) else (data.get('result') or data.get('items') or data.get('datas') or [])
            if isinstance(items, dict):
                items = items.get('list') or items.get('items') or []
            for item in items:
                try:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get('title') or item.get('subject') or '').strip()
                    if not title:
                        continue
                    nid = item.get('discussionId') or item.get('nid') or item.get('articleId') or ''
                    link = f"https://finance.naver.com/item/board_read.naver?code={ticker_code}&nid={nid}" if nid else f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discuss"
                    date_raw = str(item.get('date') or item.get('writtenAt') or '')
                    date = date_raw[5:16].replace('-', '.') if len(date_raw) >= 16 else date_raw[:10]
                    rc = item.get('readCount') or item.get('viewCount') or 0
                    views = f"{int(rc):,}" if str(rc).isdigit() else str(rc)
                    good = str(item.get('goodCount') or item.get('sympathyCount') or 0)
                    bad = str(item.get('badCount') or item.get('antipathyCount') or 0)
                    cmt_cnt = item.get('commentCount') or 0
                    comments = f"[{cmt_cnt}]" if cmt_cnt else ""
                    results.append({
                        'title': title, 'link': link, 'comments': comments,
                        'date': date, 'views': views, 'good': good, 'bad': bad
                    })
                    if len(results) >= 20:
                        break
                except Exception:
                    continue
            if results:
                return results
    except Exception:
        pass

    return [{'title': '종토방 실시간 글 보러가기 (클릭)', 'link': f'https://m.stock.naver.com/domestic/stock/{ticker_code}/discuss', 'comments': '', 'date': '실시간', 'views': '-', 'good': '-', 'bad': '-'}]

# --- 3. 뉴스 크롤링 & 보도자료 복붙(클러스터링) 판독기 ---
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
    q_encoded = quote("백종원 OR 더본코리아 when:3d")
    rss_url = f"https://news.google.com/rss/search?q={q_encoded}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(rss_url, headers=COMMON_HEADERS, timeout=5)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:40]:
            full_t = entry.title
            if any(sp in full_t for sp in SPAM_KEYWORDS):
                continue
            parts = full_t.rsplit(' - ', 1)
            pure_t = parts[0].strip()
            press = parts[1].strip() if len(parts) > 1 else '뉴스'
            if not any(k in pure_t for k in ['백종원', '더본', '빽다방', '소유진', '홍콩반점', '연돈']):
                continue
            date_str = entry.published[5:16] if hasattr(entry, 'published') else ''
            raw_list.append({'pure_title': pure_t, 'press': press, 'link': entry.link, 'date': date_str})
    except Exception:
        pass

    if not raw_list:
        return [{'title': '뉴스 로딩 실패', 'link': '#', 'date': '-', 'cat_code': 'GEN', 'cat_label': '오류', 'dups': []}]

    clusters = []
    for item in raw_list:
        tokens = extract_tokens(item['pure_title'])
        matched_cluster = None
        for cl in clusters:
            if len(tokens & cl['tokens']) >= 2:
                matched_cluster = cl
                break
        if matched_cluster:
            if item['press'] != matched_cluster['main']['press'] and item['press'] not in [d['press'] for d in matched_cluster['dups']]:
                matched_cluster['dups'].append(item)
                matched_cluster['tokens'] |= tokens
        else:
            clusters.append({'main': item, 'tokens': tokens, 'dups': []})

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

    # 전자공시: table.type5 td.title a 선택자 + UTF-8 디코딩 조합으로 정확히 파싱
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

# --- 5. 유튜브: 일반 검색(Search) 전면 배제 & 채널 고유 업로드 재생목록(VLUU) 100% 최신순 수집 ---
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
    """핸들 URL 또는 샘플 영상 ID로부터 해당 채널의 정확한 UC... ID를 추출합니다."""
    if ch.get('id'):
        return ch['id']

    # 1차: InnerTube navigation/resolve_url 로 @핸들에서 정확한 browseId(UC...) 획득
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

    # 2차: 샘플 영상 ID로 Player API 조회하여 정확한 channelId(UC...) 획득
    if ch.get('sample_vid'):
        try:
            p_url = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
            payload = {
                "context": {"client": {"hl": "ko", "gl": "KR", "clientName": "WEB", "clientVersion": "2.20251020.01.00"}},
                "videoId": ch['sample_vid']
            }
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
    """VLUU... 업로드 플레이리스트(playlistVideoRenderer) 및 동영상 탭에서 최신 영상 3개를 추출합니다."""
    videos = []
    seen_vids = set()

    def walk(obj):
        if len(videos) >= max_count:
            return
        if isinstance(obj, dict):
            # 1순위: VLUU... 업로드 재생목록 아이템 (쇼츠+일반영상 모두 최신순 정렬됨)
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
                            'vid': vid,
                            'title': title,
                            'link': f"https://www.youtube.com/watch?v={vid}",
                            'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                            'date': pub,
                            'views': views
                        })
            # 2순위: 일반 videoRenderer
            elif 'videoRenderer' in obj:
                vr = obj['videoRenderer']
                vid = vr.get('videoId', '')
                if vid and vid not in seen_vids:
                    t_runs = vr.get('title', {}).get('runs', [])
                    title = t_runs[0].get('text', '') if t_runs else vr.get('title', {}).get('simpleText', '')
                    pub = vr.get('publishedTimeText', {}).get('simpleText', '최신')
                    v_raw = vr.get('viewCountText', {}).get('simpleText', '')
                    if not v_raw:
                        v_raw = "".join(r.get('text', '') for r in vr.get('viewCountText', {}).get('runs', []))
                    views = format_view_text(v_raw)
                    if title:
                        seen_vids.add(vid)
                        videos.append({
                            'vid': vid,
                            'title': title,
                            'link': f"https://www.youtube.com/watch?v={vid}",
                            'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                            'date': pub,
                            'views': views
                        })
            else:
                for v in obj.values():
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return videos

def fetch_single_channel(ch):
    cid = resolve_exact_channel_id(ch)
    vids = []
    b_url = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false"

    if cid.startswith('UC'):
        # 핵심: UC... 를 VLUU... 로 바꾸면 해당 채널의 '전체 최신 업로드 플레이리스트(쇼츠 포함)'를 100% 최신순으로 반환함
        uploads_playlist_id = "VLUU" + cid[2:]
        try:
            payload = {"context": INNERTUBE_CONTEXT, "browseId": uploads_playlist_id}
            res = requests.post(b_url, json=payload, headers=COMMON_HEADERS, timeout=3.5)
            if res.status_code == 200:
                vids = parse_playlist_and_video_renderers(res.json(), 3)
        except Exception:
            pass

        # 만약 플레이리스트가 비어있다면 채널 Videos 탭 조회
        if not vids:
            try:
                payload = {"context": INNERTUBE_CONTEXT, "browseId": cid, "params": "EgZ2aWRlb3PyBgQKAjoA"}
                res = requests.post(b_url, json=payload, headers=COMMON_HEADERS, timeout=3.5)
                if res.status_code == 200:
                    vids = parse_playlist_and_video_renderers(res.json(), 3)
            except Exception:
                pass

    # 최후 폴백: 타 채널이 섞이는 일반 검색(search) 대신 검증된 채널 전용 최신 영상 스냅샷 사용
    if not vids:
        for item in ch.get('fallback', []):
            vid = item['vid']
            vids.append({
                'title': item['title'],
                'link': f"https://www.youtube.com/watch?v={vid}",
                'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                'date': item['date'],
                'views': item['views']
            })

    return {
        'name': ch['name'],
        'group': ch['group'],
        'handle': ch['handle'],
        'videos': vids
    }

# --- 6. 자연어 명사 어간 추출기 (서술어/동사/형용사/단순수식어 완벽 배제) ---
IGNORE_WORDS = {
    '백종원', '백종원이', '백종원의', '백종원씨', '더본', '더본코리아', '대표', '대표님', '갤주',
    '진짜', '이거', '근황', '지금', '오늘', '오늘자', '최근', '현재', '그냥', '너무', '존나',
    '새끼', '씨발', '시발', '병신', '싯팔새끼', '이새끼', '사람', '솔직히', '진지하게', '경고',
    '속보', '다시보는', '명작', '이유', '한계', '명확한', '도와준', '비교', '진행상황', '유튭',
    '댓글', '민심', '왜이럼', '생각', '이렇게', '모습', '보이는', '하는', '있는', '없는', '같음',
    '있다', '없다', '되다', '하다', '이다', '같다', '보다', '오다', '가다', '주다', '알다', '모르다',
    '얘기', '정도', '때문', '부분', '문제', '사실', '현황', '진격', '출점', '학인된', '어제', '내일'
}

# 동사/형용사 서술형 어미 패턴 ('~다', '~냐', '~노', '~네', '~음', '~거임', '~건가', '~할까' 등 차단)
PREDICATE_PATTERN = re.compile(
    r'(있다|없다|같다|되다|하다|이다|봤다|왔다|갔다|했다|됐다|난다|준다|본다|한다|된다|이다|'
    r'겠냐|겠노|겠네|하노|하냐|하나|할까|볼까|하자|해라|마라|거임|건가|인듯|인가|구만|구나|던데|는데|길래|잖아|더라)$'
)

JOSA_PATTERN = re.compile(
    r'(에서부터|으로부터|에서|으로|이랑|하고|부터|까지|마저|조차|에게|한테|처럼|보다|라고|이라|다는|라는|은|는|이|가|을|를|의|에|로|과|와|도|만|한|할|함|임)$'
)

def normalize_korean_noun(w):
    w = re.sub(r'[ㄱ-ㅎㅏ-ㅣ]+', '', w)
    if len(w) < 2 or w.isdigit():
        return ''
    # 서술어(동사/형용사) 어미로 끝나는 단어 즉시 배제
    if PREDICATE_PATTERN.search(w):
        return ''
    stemmed = JOSA_PATTERN.sub('', w)
    if len(stemmed) >= 2:
        w = stemmed
    if PREDICATE_PATTERN.search(w) or w in IGNORE_WORDS:
        return ''
    # 3글자 이상 지명/매장명 접미사 정규화 (예: 예산군 -> 예산)
    if len(w) >= 3 and w.endswith(('군', '시', '점')) and not w.endswith(('장군', '교시', '폐점', '출점', '지점', '반점')):
        w = w[:-1]
    return w

def extract_hot_keywords(dc_posts, jongto_posts, news_list):
    raw_tokens = []

    # 1. 골갤 개념글 제목
    for p in dc_posts:
        words = re.findall(r'[가-힣A-Za-z0-9]{2,}', p['title'])
        post_stems = set()
        for w in words:
            norm = normalize_korean_noun(w)
            if len(norm) >= 2 and norm not in IGNORE_WORDS and not re.match(r'^\d+[월일편명개년배위]$', norm):
                post_stems.add(norm)
        raw_tokens.extend(post_stems)

    # 2. 종토방 제목
    for j in jongto_posts:
        if '보러가기' in j['title'] or '실패' in j['title']:
            continue
        words = re.findall(r'[가-힣A-Za-z0-9]{2,}', j['title'])
        post_stems = set()
        for w in words:
            norm = normalize_korean_noun(w)
            if len(norm) >= 2 and norm not in IGNORE_WORDS:
                post_stems.add(norm)
        raw_tokens.extend(post_stems)

    # 3. 클러스터링된 대표 뉴스 제목 (복붙 기사는 이미 1개로 합쳐져 있으므로 왜곡 없음)
    for n in news_list:
        clean_t = n['title'].rsplit(' - ', 1)[0]
        words = re.findall(r'[가-힣A-Za-z0-9]{2,}', clean_t)
        post_stems = set()
        for w in words:
            norm = normalize_korean_noun(w)
            if len(norm) >= 2 and norm not in IGNORE_WORDS and not re.match(r'^\d+[월일편명개년배위만원]$', norm):
                post_stems.add(norm)
        raw_tokens.extend(post_stems)

    freq = Counter(raw_tokens)
    sorted_unique = sorted(freq.keys(), key=len)
    merged_freq = Counter()
    stem_map = {}

    for word in sorted_unique:
        mapped = word
        for shorter in sorted_unique:
            if shorter != word and len(shorter) >= 2 and word.startswith(shorter):
                mapped = stem_map.get(shorter, shorter)
                break
        stem_map[word] = mapped
        merged_freq[mapped] += freq[word]

    common_keywords = [(kw, cnt) for kw, cnt in merged_freq.most_common() if cnt >= 2]
    return common_keywords[:12]

# --- 7. HTML 문자열 생성 (멀티스레딩 병렬 수집) ---
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

    hot_keywords = extract_hot_keywords(dc_posts, jongto_posts, news)
    
    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M:%S")
    
    kw_html = ""
    if hot_keywords:
        for kw, cnt in hot_keywords:
            kw_html += f"<span class='kw-badge'>#{kw} <b>{cnt}</b></span>"
    else:
        kw_html = "<span class='kw-badge'>#공통키워드집계중</span>"

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
        <div class="update-time">마지막 업데이트: {current_time} (접속 즉시 실시간 병렬 수집)</div>
    </div>

    <div class="radar-bar">
        <span class="radar-title">🔥 실시간 이슈 핵심 명사 (2회 이상 중복):</span>
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
    return html

# --- Vercel 실시간 웹 송출용 핸들러 (api/index.py) ---
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

# --- GitHub Actions 정적 파일 생성용 (monitor.py) ---
if __name__ == "__main__":
    html_out = generate_html_string()
    with open("theborn_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    print("✅ theborn_dashboard.html V4 업데이트 완료!")
