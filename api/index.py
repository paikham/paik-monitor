import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler

# ==============================================================================
# 🎯 [사용자 직접 관리 구역 1] 뉴스 분류 키워드 사전
# ==============================================================================
NEWS_KEYWORDS = {
    "RISK": [
        "수렁", "반토막", "떠나가자", "점주 이탈", "가맹점 이탈", "휘청", "유출", "침해", "해킹", "해지",
        "모욕죄", "문닫", "고소", "폐업", "폐점", "공정위", "국감", "소송", "위반", "사과", "갈등",
        "불만", "신고", "적발", "폭락", "정솔", "지혁", "허점", "횡령", "혐의", "무혐의",
        "보완수사", "수사", "과징금", "과태료", "허풍", "위생", "비판", "외면", "철수", "갑질",
        "허위", "과장", "급락", "우지커피", "눈물", "손절", "차단", "발각", "기만", "파묘",
        "태극기", "오류", "지적", "급감", "실태", "문 닫", "틀렸다", "타격", "순감소", "순감", "꺾였다",
        "청구포기", "패소", "원산지", "짬처리", "퇴출", "일침", "불똥", "악재", "가중", "무색", "위축", "흔들"
    ],
    "PR": [
        "일냈다", "불티", "1000잔", "우녹스", "맞손", "파트너십", "데이터화", "맛 표준화", "탑재", "투트랙",
        "글로버스", "외식사업가", "송훈", "공짜", "100원", "통했다", "지휘", "대기", "대박",
        "웨이팅", "출시", "할인", "후원", "기부", "성황", "인기", "호평", "소유진", "내조",
        "응원", "쏜다", "쐈다", "러브콜", "열풍", "돌파", "오픈", "공략", "시연", "프로모션",
        "제공", "500원", "파격딜", "당근페이", "이벤트", "특가", "상생", "협약", "MOU",
        "선보", "강화", "확대", "진출", "개최", "성료", "나눔", "승부수", "성공", "뚫는다",
        "유통망", "블루오션", "세일즈", "세일", "외식왕", "파브리", "반전", "풍미", "러시",
        "완판", "일일 배달", "하루 배달", "일일 라이더", "라이더 변신", "한 판 더", "선물", "통영굴짬뽕", "연착륙"
    ],
    "SPAM": [
        "카지노", "토토", "바카라", "첫충", "슬롯", "파워볼", "홀덤", "배팅"
    ]
}

# ==============================================================================
# 🎯 [사용자 직접 관리 구역 2] 실시간 이슈 핵심 명사 (레이더) 설정 사전
# ==============================================================================
RADAR_KEYWORDS = {
    "BOOST": [
        "신공떡볶이", "신공", "요우티아오", "청구포기", "역전우동", "우녹스", "원산지", "빽보이피자",
        "정보유출", "개인정보", "가맹해지", "KISA", "모욕죄", "펨코", "에펨코리아", "군산짬뽕",
        "영업손실", "영업적자", "적자수렁", "반토막", "종토방", "변호사X", "모욕산업", "골목셰프", "쓰리셰프",
        "국감", "축제", "폐점", "판결", "농가", "짬뽕", "안성재", "혐의", "창업", "응서", "연돈", "오너",
        "빽다방", "홍콩반점", "연돈볼카츠", "새마을식당", "골목식당", "오너리스크",
        "정솔", "지혁", "소유진", "김재환", "오재나", "탐코", "상하이", "청두", "예산", "베네치아",
        "삼국축제", "국정감사", "공정위", "대패삼겹살", "원조쌈밥집", "유정수", "최강록", "정지선",
        "백반집", "국밥집", "우지커피", "컴포즈"
    ],
    "STOP": [
        "단독", "포토", "칼럼", "데스크칼럼", "인터뷰", "기획", "속보", "신고", "직원", "일반",
        "없어", "없어도", "없어서", "있어", "있어도", "많은", "적은", "빠른", "개인적", "개인", "영업", "분기",
        "근데", "아니", "진짜", "이거", "저거", "뭔가", "이제", "와서", "혹시", "니들",
        "알고", "어쩌라고", "백종원", "백종원이", "백종원의", "백종원씨", "더본", "더본코리아",
        "대표", "대표님", "갤주", "종팔이", "근황", "지금", "오늘", "오늘자", "최근", "현재",
        "그냥", "너무", "존나", "새끼", "씨발", "시발", "병신", "싯팔새끼", "이새끼", "사람",
        "솔직히", "진지하게", "경고", "다시보는", "명작", "이유", "한계", "명확한",
        "도와준", "비교", "진행상황", "유튭", "댓글", "민심", "왜이럼", "생각", "이렇게",
        "모습", "보이는", "하는", "있는", "없는", "같음", "있다", "없다", "되다", "하다",
        "이다", "같다", "보다", "오다", "가다", "주다", "알다", "모르다", "하면", "되면",
        "얘기", "정도", "때문", "부분", "문제", "사실", "현황", "진격", "학인된", "어제",
        "내일", "jpg", "jpeg", "png", "gif", "webp", "mp4", "dc", "app", "araboja",
        "aravoja", "feat", "hot", "유래", "음식", "사진", "영상", "최신", "방법", "하나",
        "리스트", "추천", "명언", "수급", "지랄", "레전드", "전문가", "인정하는", "증거자료", "업로드"
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

# --- 1. 디시인사이드 골목식당 갤러리 개념글 (1페이지 50선 + 2페이지 생존 확인용 동시 수집) ---
def fetch_dc_page(page_num=1):
    url = f"https://gall.dcinside.com/board/lists/?id=bjwstreet&exception_mode=recommend&page={page_num}"
    headers = {
        **COMMON_HEADERS,
        'Referer': 'https://gall.dcinside.com/board/lists/?id=bjwstreet',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    for _ in range(2):
        try:
            response = requests.get(url, headers=headers, timeout=4.5)
            soup = BeautifulSoup(decode_html(response), 'html.parser')
            posts = soup.select('.us-post')
            results = []
            for post in posts[:50]:
                num_el = post.select_one('.gall_num')
                post_no = num_el.text.strip() if num_el else ''
                if not post_no.isdigit():
                    continue
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
                        'no': post_no, 'title': title, 'link': link,
                        'upvotes': upvotes, 'views': views,
                        'comments': comments, 'date': date
                    })
            if len(results) >= 10:
                return results
            time.sleep(0.3)
        except Exception:
            time.sleep(0.3)
    return []

def get_dc_best_posts_with_page2():
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(fetch_dc_page, 1)
        f2 = ex.submit(fetch_dc_page, 2)
        p1 = f1.result()
        p2 = f2.result()
    if not p1:
        p1 = [{'no': 'ERR', 'title': '갤러리 일시 응답 지연 (새로고침 해주세요)', 'link': '#', 'upvotes': '0', 'views': '0', 'comments': '[0]', 'date': '-'}]
    p2_meta = {'nos': [x['no'] for x in p2], 'titles': [x['title'] for x in p2]}
    return p1, p2_meta

# --- 2. 4단계 한국어 기사 문맥 대조 & 물타기 언플 판독 엔진 ---
STOP_WORDS = {'더본코리아', '더본', '백종원', '백종원의', '대표', '빽다방', '홍콩반점', '프랜차이즈', '외식', '진행', '운영', '출시'}

def extract_tokens(title):
    clean_t = title.rsplit(' - ', 1)[0]
    words = re.findall(r'[가-힣A-Za-z0-9]{2,}', clean_t)
    return {w for w in words if w not in STOP_WORDS}

HARD_RISK_PATTERNS = [
    (r"(믿었는데|떠나가자|다\s*떠나|등\s*돌린|곡소리|비명|외면|눈물)", "가맹점주 이탈·원성"),
    (r"(가맹.*해지|폐업|폐점|문\s*닫|철수|퇴출|순감소|50곳\s*순감|꺾였다|급감|해지.*급증|가맹점\s*이탈|점주\s*이탈|매출\s*위축|가맹사업.*흔들)", "가맹해지·매출 위축"),
    (r"(적자\s*수렁|반토막|적자\s*전환|무색|3분기도\s*적자|연속\s*적자.*폭락|주가.*폭락|신저가|국내는.*휘청|국내.*휘청|부진의\s*수렁)", "실적 악화·적자 수렁"),
    (r"(유출|침해|해킹|KISA|개인정보|계좌정보|보안\s*논란|수탁사)", "개인정보·보안 사고"),
    (r"(무더기\s*고소|수백명\s*고소|쪼개기|합의금\s*장사|종토방.*고소|변호사\s*일침|처벌\s*우려|처벌대상|소송\s*위험|무혐의|청구포기|패소|피고소)", "고소 남발·법적 분쟁"),
    (r"(위생|원산지|꼼수|책임\s*회피|외주\s*탓|갑질|공정위|국감|불똥|경영\s*부담.*가중|끊이지\s*않는\s*악재|0원\s*쿠폰.*논란)", "경영 논란·오너리스크")
]

SPIN_PR_PATTERNS = [
    (r"(오너\s*리스크\s*해소|리스크.*완화|백종원\s*일냈다|반등\s*열쇠\s*될까)", "오너리스크 해소·반등 억빠"),
    (r"((적자|영업손실|영업적자|손실).*(줄었다|줄였다|줄여|감소|축소|개선|원가\s*잡았다))", "적자 축소 물타기"),
    (r"((줄었다|줄였다|줄여|감소|축소|개선).*(적자|영업손실|영업적자|손실))", "적자 축소 물타기")
]

STANDARD_PR_PATTERNS = [
    (r"(중국.*매장.*확대|상하이|하루\s*1000잔|불티|무섭게\s*팔린다|中\s*진출|영토\s*확장|아망추.*인기|출점\s*가속|대박\s*조짐|추가\s*출점|더\s*낸다|연착륙)", "중국 빽다방 홍보"),
    (r"(우녹스|이탈리아\s*오븐|맛\s*표준화|파트너십|맞손|업무협약|MOU|협약|협력|공동\s*개발|데이터화|탑재|오븐\s*시장|유럽.*투트랙|꺼낸\s*승부수|배달전문점\s*실험)", "해외·신사업 홍보"),
    (r"(피자.*(배달|알바|라이더|오토바이|직접|시켰더니|시키셨|선물|홍보|나서|변신)|일일\s*배달|하루\s*배달|일일\s*라이더|치즈킥|소방서)", "유튜브 배달쇼 홍보"),
    (r"(소유진|아트하우스|대저택|미술관|내조|애셋맘)", "오너 일가 화제성 언플"),
    (r"(통영\s*굴|통영굴짬뽕|팔도\s*짬뽕|신제품|신메뉴|출시|선보|프로모션|할인|특가|이벤트|나눔점|기부|체험행사)", "신메뉴·이벤트 홍보"),
    (r"(\[똑똑한|\[유통가|\[푸드|브리핑|단신|꽂힌\s*소스시장|성장동력\s*확보)", "보도자료·업계 홍보")
]

def classify_news_v16(cluster_titles_text, dup_count):
    total_cnt = 1 + dup_count

    for pattern, reason in HARD_RISK_PATTERNS:
        if re.search(pattern, cluster_titles_text):
            if total_cnt >= 2:
                return "RISK", f"🚨 쟁점확산 ({total_cnt}건 · {reason})", reason
            return "RISK", f"🚨 리스크 ({reason})", reason

    for pattern, reason in SPIN_PR_PATTERNS:
        if re.search(pattern, cluster_titles_text):
            if total_cnt >= 2:
                return "PR", f"🎺 복붙언플 ({total_cnt}건 · {reason})", reason
            return "PR", f"🎺 물타기언플 ({reason})", reason

    for pattern, reason in STANDARD_PR_PATTERNS:
        if re.search(pattern, cluster_titles_text):
            if total_cnt >= 2:
                return "PR", f"🎺 복붙언플 ({total_cnt}건 · {reason})", reason
            return "PR", f"🎺 자본언플 ({reason})", reason

    safe_text = cluster_titles_text.replace("이탈리아", "이태리")
    for rk in NEWS_KEYWORDS["RISK"]:
        if rk in safe_text:
            if total_cnt >= 2:
                return "RISK", f"🚨 쟁점확산 ({total_cnt}건 · {rk})", rk
            return "RISK", f"🚨 리스크 ({rk})", rk

    for pk in NEWS_KEYWORDS["PR"]:
        if pk in safe_text:
            if total_cnt >= 2:
                return "PR", f"🎺 복붙언플 ({total_cnt}건 · {pk})", pk
            return "PR", f"🎺 자본언플 ({pk})", pk

    if total_cnt >= 3:
        return "PR", f"🎺 보도자료 복붙 ({total_cnt}건 살포)", "보도자료 살포"

    return "GEN", "📰 일반동향", "일반동향"

def get_latest_news():
    raw_list = []
    seen_titles = set()

    naver_queries = [
        ("더본코리아 OR 백종원 OR 빽다방", '1'),
        ("더본코리아 OR 백종원 논란 OR 고소 OR 해지 OR 유출 OR 수렁 OR 반토막 OR 순감", '0'),
        ("더본코리아 OR 백종원 OR 빽다방", '0')
    ]
    for q_str, sort_mode in naver_queries:
        naver_url = f"https://search.naver.com/search.naver?where=news&query={quote(q_str)}&sort={sort_mode}"
        try:
            res = requests.get(naver_url, headers=COMMON_HEADERS, timeout=4.0)
            soup = BeautifulSoup(decode_html(res), 'html.parser')
            for item in soup.select('.news_area, .bx'):
                title_el = item.select_one('.news_tit') or item.select_one('a[href*="news.naver.com"]')
                if not title_el:
                    continue
                title = (title_el.get('title') or title_el.text or '').strip()
                if not title or any(sp in title for sp in NEWS_KEYWORDS["SPAM"]):
                    continue
                if not any(k in title for k in ['백종원', '더본', '빽다방', '소유진', '홍콩반점', '연돈', '새마을식당', '빽보이', '신공', '역전우동']):
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

    rss_queries = [
        "백종원 OR 더본코리아 OR 빽다방 OR 빽보이피자 when:7d",
        "(백종원 OR 더본코리아) (논란 OR 고소 OR 해지 OR 유출 OR 무혐의 OR 수렁 OR 반토막 OR 순감) when:14d"
    ]
    for rq in rss_queries:
        rss_url = f"https://news.google.com/rss/search?q={quote(rq)}&hl=ko&gl=KR&ceid=KR:ko"
        try:
            res = requests.get(rss_url, headers=COMMON_HEADERS, timeout=4.5)
            feed = feedparser.parse(res.content)
            for entry in feed.entries[:45]:
                full_t = entry.title
                if any(sp in full_t for sp in NEWS_KEYWORDS["SPAM"]):
                    continue
                parts = full_t.rsplit(' - ', 1)
                pure_t = parts[0].strip()
                press = parts[1].strip() if len(parts) > 1 else '뉴스'
                if not any(k in pure_t for k in ['백종원', '더본', '빽다방', '소유진', '홍콩반점', '연돈', '새마을식당', '빽보이', '신공', '역전우동']):
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
        return [{'title': '뉴스 로딩 실패', 'pure_title': '뉴스 로딩 실패', 'link': '#', 'date': '-', 'cat_code': 'GEN', 'cat_label': '오류', 'dups': [], 'ai_reason': ''}]

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

    scored_clusters = []
    for cl in clusters:
        main = cl['main']
        dups = cl['dups']
        all_titles_in_cluster = " ".join([main['pure_title']] + [d['pure_title'] for d in dups])
        cat_code, cat_label, ai_reason = classify_news_v16(all_titles_in_cluster, len(dups))
        scored_clusters.append({
            'title': f"{main['pure_title']} - {main['press']}",
            'pure_title': all_titles_in_cluster,
            'link': main['link'],
            'date': main['date'],
            'cat_code': cat_code,
            'cat_label': cat_label,
            'ai_reason': ai_reason,
            'dups': dups
        })

    risk_items = [c for c in scored_clusters if c['cat_code'] == 'RISK']
    other_items = [c for c in scored_clusters if c['cat_code'] != 'RISK']
    return (risk_items[:12] + other_items)[:28]

# --- 3. 네이버 금융 주가 + 펀더멘털/시총 증발 계산 + 전자공시 ---
def get_stock_and_disclosures(ticker_code="475560"):
    api_url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{ticker_code}"
    total_shares = 14740746
    paik_shares = 8792850
    ipo_price = 34000
    peak_price = 64500
    low_52w = 12130
    margin_call_price = 6875

    stock_info = {
        'price': '오류', 'raw_price': 12820, 'change_str': '-',
        'vol': '-', 'ipo_drop': '-', 'peak_drop': '-', 'margin_safety': 50,
        'mcap_str': '1,890억 원', 'mcap_lost_str': '-7,618억 원',
        'paik_val_str': '1,127억 원', 'from_52w_low': '+5.7%',
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

        stock_info['ipo_drop'] = f"{((nv - ipo_price) / ipo_price) * 100:.1f}%"
        stock_info['peak_drop'] = f"{((nv - peak_price) / peak_price) * 100:.1f}%"
        
        mcap_eok = int((nv * total_shares) / 100000000)
        peak_mcap_eok = int((peak_price * total_shares) / 100000000)
        paik_eok = int((nv * paik_shares) / 100000000)
        stock_info['mcap_str'] = f"{mcap_eok:,}억 원"
        stock_info['mcap_lost_str'] = f"-{peak_mcap_eok - mcap_eok:,}억 원"
        stock_info['paik_val_str'] = f"{paik_eok:,}억 원"
        stock_info['from_52w_low'] = f"+{((nv - low_52w) / low_52w) * 100:.1f}%"

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

# --- 4. 📺 유튜브 V16 수집 엔진 (전 채널 4개씩 출력 + Mr. Paik 미국채널 박제 + 서브 공식채널 롱폼+쇼츠 최신 4개) ---
YOUTUBE_CHANNELS = [
    {
        "name": "김재환의 오재나", "group": "CRITIC",
        "handle": "https://www.youtube.com/@studio_OZN",
        "id": "", "sample_vid": "ZwHixkCDwaQ",
        "mode": "LONG_ONLY",  # 최신 롱폼 4개
        "owner_keywords": ["오재나", "studio_OZN"],
        "search_query": "김재환의 오재나 백종원",
        "fallback": [
            {"vid": "ZwHixkCDwaQ", "title": "백종원과 변호사X는 몇 명이나 고소했을까? #오재나 #김재환PD #모욕죄 #모욕죄고소 #펨코 #DC #종토방", "date": "1일 전", "views": "38,400회", "is_short": False},
            {"vid": "INoddmJf6dE", "title": "모욕죄는 백종원을 위한 법인가? #에펨코리아 #모욕죄 #김재환PD #오재나 #펨코", "date": "2주 전", "views": "731,925회", "is_short": False},
            {"vid": "0Gsvn_I6z1w", "title": "안티 댓글을 양산하는 더본코리아와 정솔의 마법 #백종원 #김재환 #종토방고소위협 #오재나", "date": "3주 전", "views": "634,231회", "is_short": False},
            {"vid": "4fALTQTUldU", "title": "연돈볼카츠 합의안 타결! 나머지 점주들은 신났을까? #백종원 #김재환 #더본코리아", "date": "1개월 전", "views": "1,500,179회", "is_short": False}
        ]
    },
    {
        "name": "탐코 : 탐욕의 코리아", "group": "CRITIC",
        "handle": "https://www.youtube.com/@tamkorea",
        "id": "UC1rn5BnUdP1OGI6vnxh0IbQ", "sample_vid": "LbNF4wQJ9sk",
        "mode": "LONG_ONLY",  # 최신 롱폼 4개
        "owner_keywords": ["탐코", "탐욕의 코리아", "tamkorea"],
        "search_query": "탐코 탐욕의 코리아 백종원",
        "fallback": [
            {"vid": "LbNF4wQJ9sk", "title": "숫자가 가리키는 백종원의 종말", "date": "2주 전", "views": "18,536회", "is_short": False},
            {"vid": "RkFbcgPNofs", "title": "무너진 백종원 대기업의 꿈", "date": "2주 전", "views": "21,673회", "is_short": False},
            {"vid": "cpvolw4BJqg", "title": "백종원을 파멸시킬 세 부류의 인간", "date": "3주 전", "views": "61,912회", "is_short": False}
        ]
    },
    {
        "name": "조선연예실록", "group": "CRITIC",
        "handle": "https://www.youtube.com/@tvsillok",
        "id": "", "sample_vid": "k5djjpipVbE",
        "mode": "LONG_ONLY",  # 최신 롱폼 4개
        "owner_keywords": ["조선연예실록", "tvsillok"],
        "search_query": "조선연예실록 백종원",
        "fallback": [
            {"vid": "k5djjpipVbE", "title": "믿었던 빽다방마저 배신하려나?", "date": "2일 전", "views": "57,916회", "is_short": False},
            {"vid": "HBakbY09OtM", "title": "백종원 날개가 없다", "date": "3일 전", "views": "52,538회", "is_short": False},
            {"vid": "aFV6CdkKGeY", "title": "백종원 씨는 국민을 무시하지 마세요", "date": "10일 전", "views": "48,563회", "is_short": False},
            {"vid": "P2tEH9SR4aE", "title": "백종원 피자 배달에 보이는 위생관념", "date": "12일 전", "views": "98,058회", "is_short": False}
        ]
    },
    {
        "name": "백종원 본채널", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@paik_jongwon",
        "id": "UCyn-K7rZLXjGl7VXGweIlcA", "sample_vid": "6NnIoQ1mOKY",
        "mode": "LONG_ONLY",  # 백종원 본채널은 최신 롱폼 4개
        "owner_keywords": ["백종원", "PAIK JONG WON"],
        "search_query": "백종원 PAIK JONG WON",
        "fallback": [
            {"vid": "6NnIoQ1mOKY", "title": "겨울 바다의 맛을 제대로 담은 통영굴짬뽕 먹으러 왔습니다", "date": "6일 전", "views": "993,870회", "is_short": False},
            {"vid": "fGPEmOd53BY", "title": "피자 배달 알바합니다! 그런데 사람들이 못 알아봅니다ㅋㅋ", "date": "1주 전", "views": "1,364,758회", "is_short": False},
            {"vid": "KNG-_c_p87k", "title": "[출장 중 배고파_청두] 1시간 40분 웨이팅?! 청두식 마라훠궈의 진짜 매운맛을 보여드립니다", "date": "2주 전", "views": "348,657회", "is_short": False},
            {"vid": "9a0n0ZWrLRI", "title": "[출장 중 배고파_일본 오사카] 현지 직장인들이 줄 서서 먹는다는 일본식 돼지고기 스테이크", "date": "3주 전", "views": "569,011회", "is_short": False}
        ]
    },
    {
        "name": "Mr. Paik (미국 진출용 신설)", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@mr.paik_us_official",
        "id": "", "sample_vid": "IMKlMFCdT5M",
        "mode": "ALL_LATEST",  # 롱폼+쇼츠 통합 최신 4개
        "owner_keywords": ["Mr. Paik", "Mr.Paik_US_Official"],
        "search_query": "\"Mr. Paik\" Tteokbokki Bulgogi Chapaguri",
        "fallback": [
            {"vid": "IMKlMFCdT5M", "title": "[Shorts] Chapaguri with Steak! Ultimate Korean Ramen", "date": "오늘", "views": "923회", "is_short": True},
            {"vid": "uOcrFY6aC-g", "title": "[Shorts] The Easiest Korean Bulgogi Recipe!", "date": "1일 전", "views": "790회", "is_short": True},
            {"vid": "j0Q9wDBwdK8", "title": "[Shorts] Crispy Spicy Garlic Korean Fried Chicken Recipe!", "date": "2일 전", "views": "1,798회", "is_short": True},
            {"vid": "fCFJbPI-U00", "title": "[Shorts] The Easiest Tteokbokki Recipe! Chewy Korean Rice Cakes", "date": "2일 전", "views": "888회", "is_short": True}
        ]
    },
    {
        "name": "TBK (글로벌소스)", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@TBK_theborn",
        "id": "UCbgdcVitzVvWdngVx3OYTmA", "sample_vid": "joHpz7hNmEM",
        "mode": "ALL_LATEST",  # 롱폼+쇼츠 통합 최신 4개
        "owner_keywords": ["TBK"],
        "search_query": "TBK 더본코리아 소스",
        "fallback": [
            {"vid": "FfC_pNkyaT8", "title": "[Shorts] Kimchi Egg Ramyun With Mild Paik Ramyun", "date": "1개월 전", "views": "1,711회", "is_short": True},
            {"vid": "-wHsjUnhoL4", "title": "[Shorts] Dumpling Ramyun with Mild Paik Ramyun", "date": "1개월 전", "views": "356회", "is_short": True},
            {"vid": "fCRzCl-gqOg", "title": "[Shorts] Mala Ramyun With Mild Paik Ramyun", "date": "1개월 전", "views": "1,247회", "is_short": True},
            {"vid": "joHpz7hNmEM", "title": "미국에서도 그 맛 그대로, K-부대찌개 초간단 레시피", "date": "4개월 전", "views": "14,363회", "is_short": False}
        ]
    },
    {
        "name": "더본 테이스티", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@theborn_tasty",
        "id": "", "sample_vid": "gazC1wTYt3k",
        "mode": "ALL_LATEST",  # 롱폼+쇼츠 통합 최신 4개
        "owner_keywords": ["더본 테이스티", "더본테이스티", "theborn_tasty"],
        "search_query": "\"더본 테이스티\"",
        "fallback": [
            {"vid": "gazC1wTYt3k", "title": "침샘 폭발 주의! 대구의 맛, 막창짬뽕 화보 영상 🎬", "date": "4주 전", "views": "111,798회", "is_short": False},
            {"vid": "GdNx1GQAG_A", "title": "찾았다! 연돈튀김덮밥 할인 소식🫶", "date": "1개월 전", "views": "27,791회", "is_short": False},
            {"vid": "7Om-LNDRQgw", "title": "[Shorts] 연돈튀김덮밥 도시락 속 들리는 소리는?!", "date": "1개월 전", "views": "306회", "is_short": True},
            {"vid": "5Wtv9jpPVWI", "title": "롤링파스타에 미슐랭 파브리 셰프가 등장한 이유는? 🧑‍🍳🍝", "date": "3개월 전", "views": "969,145회", "is_short": False}
        ]
    },
    {
        "name": "더본 NOW", "group": "OFFICIAL",
        "handle": "https://www.youtube.com/@theborn_now",
        "id": "", "sample_vid": "nY3ibLP2xbo",
        "mode": "ALL_LATEST",  # 롱폼+쇼츠 통합 최신 4개
        "owner_keywords": ["더본NOW", "더본 NOW", "theborn_now"],
        "search_query": "\"더본NOW\"",
        "fallback": [
            {"vid": "nY3ibLP2xbo", "title": "바비큐부터 아이스크림까지 무료?!🔥 창녕 산토끼밥상의 특별한 여름", "date": "1개월 전", "views": "617회", "is_short": False},
            {"vid": "tGLX12qPsyg", "title": "어디든 달려갑니다! 더본 푸드트럭 삼총사 전격 해부 🔍", "date": "4개월 전", "views": "1,324회", "is_short": False}
        ]
    }
]

INNERTUBE_CONTEXT = {
    "client": {"hl": "ko", "gl": "KR", "clientName": "WEB", "clientVersion": "2.20251020.01.00"}
}

def format_view_text(v_str):
    v_str = str(v_str).replace('조회수', '').strip()
    if not v_str:
        return '집계중'
    if v_str.isdigit():
        return f"{int(v_str):,}회"
    if not v_str.endswith('회') and not v_str.endswith('중'):
        return v_str + '회'
    return v_str

def format_minutes_to_ko_date(diff_min):
    if diff_min < 60:
        return f"{max(1, diff_min)}분 전"
    hours = diff_min // 60
    if hours < 24:
        return f"{hours}시간 전"
    days = hours // 24
    if days < 7:
        return f"{days}일 전"
    weeks = days // 7
    if days < 30:
        return f"{weeks}주 전"
    months = days // 30
    if months < 12:
        return f"{months}개월 전"
    return f"{days // 365}년 전"

def parse_ko_age_to_minutes(date_str):
    if not date_str:
        return 999999
    s = str(date_str).strip()
    if s in ('방금', '오늘', '최신'):
        return 5
    if s == '쇼츠':
        return 50000
    m = re.search(r'(\d+)\s*(초|분|시간|일|주|개월|달|년)', s)
    if m:
        val = int(m.group(1))
        unit = m.group(2)
        mult = {'초': 0.02, '분': 1, '시간': 60, '일': 1440, '주': 10080, '개월': 43200, '달': 43200, '년': 525600}
        return int(val * mult.get(unit, 1440))
    m_iso = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m_iso:
        try:
            dt = datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)), tzinfo=timezone(timedelta(hours=9)))
            now = datetime.now(timezone(timedelta(hours=9)))
            diff_min = int((now - dt).total_seconds() // 60)
            return max(1, diff_min)
        except Exception:
            pass
    return 999999

def deduplicate_and_sort_videos(videos, max_count=4, reject_older_than_months=10):
    if not videos:
        return []
    max_age_min = reject_older_than_months * 43200
    unique_vids = []
    seen_vids = set()
    seen_titles = set()

    for v in videos:
        if '_age_min' not in v:
            v['_age_min'] = parse_ko_age_to_minutes(v.get('date', ''))

    for v in sorted(videos, key=lambda x: x['_age_min']):
        vid = v.get('vid') or v.get('link', '').split('v=')[-1].split('/')[-1]
        clean_t = re.sub(r'^(\[Shorts\]|\[본영상\])\s*', '', v.get('title', ''), flags=re.IGNORECASE)
        norm_t = re.sub(r'\W+', '', clean_t).lower()[:24]
        if not vid or not norm_t or vid in seen_vids or norm_t in seen_titles:
            continue
        if v['_age_min'] <= max_age_min:
            seen_vids.add(vid)
            seen_titles.add(norm_t)
            unique_vids.append(v)

    return unique_vids[:max_count]

def resolve_exact_channel_id(ch):
    if ch.get('id') and ch['id'].startswith('UC'):
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
            s_url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
            res = requests.post(s_url, json={"context": INNERTUBE_CONTEXT, "query": ch['sample_vid']}, headers=COMMON_HEADERS, timeout=3)
            if res.status_code == 200:
                m_cid = re.search(r'"browseId"\s*:\s*"(UC[a-zA-Z0-9_-]{22})"', res.text)
                if m_cid:
                    ch['id'] = m_cid.group(1)
                    return m_cid.group(1)
        except Exception:
            pass
    return ""

def fetch_channel_rss_videos(cid):
    """공식 XML 피드에서 롱폼과 쇼츠를 각각 구분(is_short)하여 정확한 업로드 시각과 함께 가져옵니다."""
    if not cid or not cid.startswith('UC'):
        return []
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    out = []
    try:
        res = requests.get(rss_url, headers=COMMON_HEADERS, timeout=3.5)
        if res.status_code != 200:
            return []
        feed = feedparser.parse(res.content)
        now_utc = datetime.now(timezone.utc)
        for entry in feed.entries[:15]:
            vid = getattr(entry, 'yt_videoid', '')
            link = getattr(entry, 'link', f"https://www.youtube.com/watch?v={vid}")
            title = getattr(entry, 'title', '').strip()
            if not vid or not title:
                continue

            is_short = '/shorts/' in link
            age_min = 60
            date_str = "최신"
            pub_raw = getattr(entry, 'published', '')
            if pub_raw:
                try:
                    dt = datetime.fromisoformat(pub_raw.replace('Z', '+00:00'))
                    age_min = max(1, int((now_utc - dt).total_seconds() // 60))
                    date_str = format_minutes_to_ko_date(age_min)
                except Exception:
                    pass

            views_str = "집계중"
            media_stats = getattr(entry, 'media_statistics', None)
            if isinstance(media_stats, dict) and media_stats.get('views'):
                views_str = format_view_text(media_stats['views'])

            out.append({
                'vid': vid,
                'title': f"[Shorts] {title}" if (is_short and not title.startswith('[Shorts]')) else title,
                'link': f"https://www.youtube.com/watch?v={vid}",
                'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                'date': date_str,
                'views': views_str,
                'is_short': is_short,
                '_age_min': age_min
            })
    except Exception:
        pass
    return out

def extract_videos_from_innertube(data_node, max_scan=20, owner_keywords=None, target_cid=None, force_long_only=True):
    videos = []
    seen_vids = set()

    def walk(obj):
        if len(videos) >= max_scan:
            return
        if isinstance(obj, dict):
            if 'channelFeaturedContentRenderer' in obj or 'channelVideoPlayerRenderer' in obj:
                return
            if 'videoRenderer' in obj:
                vr = obj['videoRenderer']
                vid = vr.get('videoId', '')
                if vid and vid not in seen_vids:
                    nav_url = vr.get('navigationEndpoint', {}).get('commandMetadata', {}).get('webCommandMetadata', {}).get('url', '')
                    is_short = '/shorts/' in nav_url
                    if is_short and force_long_only:
                        return

                    if owner_keywords or target_cid:
                        owner_runs = (
                            vr.get('ownerText', {}).get('runs', []) or
                            vr.get('longBylineText', {}).get('runs', []) or
                            vr.get('shortBylineText', {}).get('runs', [])
                        )
                        owner_name = "".join(r.get('text', '') for r in owner_runs)
                        owner_id = owner_runs[0].get('navigationEndpoint', {}).get('browseEndpoint', {}).get('browseId', '') if owner_runs else ""
                        id_ok = bool(target_cid and owner_id == target_cid)
                        name_ok = bool(owner_keywords and any(k.lower() in owner_name.lower() for k in owner_keywords))
                        if (owner_name or owner_id) and not (id_ok or name_ok):
                            return

                    t_runs = vr.get('title', {}).get('runs', [])
                    title = "".join(r.get('text', '') for r in t_runs) if t_runs else vr.get('title', {}).get('simpleText', '')
                    pub = (
                        vr.get('publishedTimeText', {}).get('simpleText', '') or
                        "".join(r.get('text', '') for r in vr.get('publishedTimeText', {}).get('runs', []))
                    ).replace('스트리밍 시간:', '').replace('최초 공개:', '').strip()
                    v_raw = vr.get('viewCountText', {}).get('simpleText', '') or "".join(r.get('text', '') for r in vr.get('viewCountText', {}).get('runs', []))
                    if '시청 중' in v_raw or '예정' in pub or not pub:
                        return
                    if title:
                        seen_vids.add(vid)
                        videos.append({
                            'vid': vid,
                            'title': f"[Shorts] {title}" if (is_short and not title.startswith('[Shorts]')) else title,
                            'link': f"https://www.youtube.com/watch?v={vid}",
                            'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                            'date': pub,
                            'views': format_view_text(v_raw),
                            'is_short': is_short,
                            '_age_min': parse_ko_age_to_minutes(pub)
                        })
            else:
                for v in obj.values():
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data_node)
    return videos

def fetch_single_channel(ch):
    cid = resolve_exact_channel_id(ch)
    mode = ch.get('mode', 'LONG_ONLY')
    rss_all = []
    tab_long_vids = []
    is_live = False
    b_url = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false"

    # 1단계: 공식 XML 피드 조회 (롱폼과 쇼츠 모두 최신 15개 수집)
    if cid.startswith('UC'):
        rss_all = fetch_channel_rss_videos(cid)
        if rss_all:
            is_live = True

    # 2단계: InnerTube '동영상(Videos)' 탭 조회하여 순수 본영상(롱폼) 확보
    if cid.startswith('UC'):
        try:
            payload = {"context": INNERTUBE_CONTEXT, "browseId": cid, "params": "EgZ2aWRlb3M="}
            res = requests.post(b_url, json=payload, headers=COMMON_HEADERS, timeout=3.5)
            if res.status_code == 200:
                r_json = res.json()
                tabs = r_json.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
                videos_tab_content = None
                videos_tab_params = None
                for t in tabs:
                    tr = t.get('tabRenderer', {})
                    t_title = tr.get('title', '')
                    t_url = tr.get('endpoint', {}).get('commandMetadata', {}).get('webCommandMetadata', {}).get('url', '')
                    if t_title in ('동영상', 'Videos') or t_url.endswith('/videos'):
                        if tr.get('content'):
                            videos_tab_content = tr.get('content')
                        else:
                            videos_tab_params = tr.get('endpoint', {}).get('browseEndpoint', {}).get('params')
                        break

                if videos_tab_content:
                    tab_long_vids = extract_videos_from_innertube(videos_tab_content, 18, force_long_only=True)
                elif videos_tab_params:
                    res2 = requests.post(b_url, json={"context": INNERTUBE_CONTEXT, "browseId": cid, "params": videos_tab_params}, headers=COMMON_HEADERS, timeout=3.5)
                    if res2.status_code == 200:
                        tabs2 = res2.json().get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
                        for t2 in tabs2:
                            tr2 = t2.get('tabRenderer', {})
                            if tr2.get('content'):
                                tab_long_vids.extend(extract_videos_from_innertube(tr2.get('content'), 18, force_long_only=True))
                if tab_long_vids:
                    is_live = True
        except Exception:
            pass

    # [핵심 1] ALL_LATEST 모드 (백종원 본채널을 제외한 더본 공식 채널들: Mr. Paik, TBK, 더본 테이스티, 더본 NOW)
    # -> 롱폼 + 숏폼 구분 없이 실제 업로드 최신순 4개 출력!
    if mode == 'ALL_LATEST':
        all_pool = rss_all + tab_long_vids
        for fb in ch.get('fallback', []):
            all_pool.append({
                'vid': fb['vid'], 'title': fb['title'],
                'link': f"https://www.youtube.com/watch?v={fb['vid']}",
                'thumb': f"https://i.ytimg.com/vi/{fb['vid']}/mqdefault.jpg",
                'date': fb['date'], 'views': fb['views'], 'is_short': fb.get('is_short', False),
                '_age_min': parse_ko_age_to_minutes(fb['date'])
            })
        vids = deduplicate_and_sort_videos(all_pool, max_count=4, reject_older_than_months=10)
        return {'name': ch['name'], 'group': ch['group'], 'handle': ch['handle'], 'videos': vids[:4], 'is_live': is_live, 'mode': mode}

    # [핵심 2] LONG_ONLY 모드 (오재나, 탐코, 조선연예실록, 백종원 본채널)
    # -> 쇼츠를 제외한 순수 롱폼(본영상) 최신순 4개 출력!
    long_candidates = [v for v in rss_all if not v.get('is_short')] + tab_long_vids
    vids = deduplicate_and_sort_videos(long_candidates, max_count=4, reject_older_than_months=6)

    if len(vids) < 4 and ch.get('search_query'):
        try:
            s_url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
            res_s = requests.post(s_url, json={"context": INNERTUBE_CONTEXT, "query": ch['search_query'], "params": "CAI="}, headers=COMMON_HEADERS, timeout=3.5)
            if res_s.status_code == 200:
                found_s = extract_videos_from_innertube(
                    res_s.json(), 20,
                    owner_keywords=ch.get('owner_keywords'),
                    target_cid=cid,
                    force_long_only=True
                )
                if found_s:
                    is_live = True
                long_candidates.extend(found_s)
                vids = deduplicate_and_sort_videos(long_candidates, max_count=4, reject_older_than_months=6)
        except Exception:
            pass

    for item in ch.get('fallback', []):
        long_candidates.append({
            'vid': item['vid'], 'title': item['title'],
            'link': f"https://www.youtube.com/watch?v={item['vid']}",
            'thumb': f"https://i.ytimg.com/vi/{item['vid']}/mqdefault.jpg",
            'date': item['date'], 'views': item['views'], 'is_short': False,
            '_age_min': parse_ko_age_to_minutes(item['date'])
        })
    vids = deduplicate_and_sort_videos(long_candidates, max_count=4, reject_older_than_months=6)

    return {'name': ch['name'], 'group': ch['group'], 'handle': ch['handle'], 'videos': vids[:4], 'is_live': is_live, 'mode': mode}

def fetch_youtube_hot_search():
    s_url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
    payload = {"context": INNERTUBE_CONTEXT, "query": "백종원 더본코리아", "params": "CAI="}
    videos = []
    seen_vids = set()
    try:
        res = requests.post(s_url, json=payload, headers=COMMON_HEADERS, timeout=3.5)
        if res.status_code == 200:
            data = res.json()
            def walk(obj):
                if len(videos) >= 20:
                    return
                if isinstance(obj, dict):
                    if 'videoRenderer' in obj:
                        vr = obj['videoRenderer']
                        vid = vr.get('videoId', '')
                        if vid and vid not in seen_vids:
                            t_runs = vr.get('title', {}).get('runs', [])
                            title = "".join(r.get('text', '') for r in t_runs) if t_runs else vr.get('title', {}).get('simpleText', '')
                            if not any(k in title for k in ['백종원', '더본', '빽다방', '홍콩반점', '연돈', '오재나', '빽보이', '신공', '조선연예실록']):
                                return
                            owner_runs = vr.get('ownerText', {}).get('runs', []) or vr.get('longBylineText', {}).get('runs', [])
                            channel_name = owner_runs[0].get('text', '유튜브') if owner_runs else '유튜브'
                            pub = (
                                vr.get('publishedTimeText', {}).get('simpleText', '') or
                                "".join(r.get('text', '') for r in vr.get('publishedTimeText', {}).get('runs', []))
                            ).replace('스트리밍 시간:', '').replace('최초 공개:', '').strip()
                            v_raw = vr.get('viewCountText', {}).get('simpleText', '') or "".join(r.get('text', '') for r in vr.get('viewCountText', {}).get('runs', []))
                            if '시청 중' in v_raw or '예정' in pub or not pub:
                                return
                            seen_vids.add(vid)
                            videos.append({
                                'vid': vid,
                                'title': title,
                                'channel': channel_name,
                                'link': f"https://www.youtube.com/watch?v={vid}",
                                'thumb': f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                                'date': pub,
                                'views': format_view_text(v_raw),
                                '_age_min': parse_ko_age_to_minutes(pub)
                            })
                    else:
                        for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for it in obj: walk(it)
            walk(data)
    except Exception:
        pass
    return deduplicate_and_sort_videos(videos, max_count=8, reject_older_than_months=3)

# --- 5. HTML 대시보드 생성 ---
def generate_html_string():
    with ThreadPoolExecutor(max_workers=10) as executor:
        f_dc = executor.submit(get_dc_best_posts_with_page2)
        f_news = executor.submit(get_latest_news)
        f_stock = executor.submit(get_stock_and_disclosures)
        f_yt = [executor.submit(fetch_single_channel, ch) for ch in YOUTUBE_CHANNELS]
        f_yt_search = executor.submit(fetch_youtube_hot_search)

        dc_posts, dc_page2_meta = f_dc.result()
        news = f_news.result()
        stock = f_stock.result()
        youtube_data = [f.result() for f in f_yt]
        yt_hot_search = f_yt_search.result()

    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M:%S")

    all_titles_for_radar = (
        [p['title'] for p in dc_posts if p.get('no') != 'ERR'] +
        [n['title'].rsplit(' - ', 1)[0] for n in news if '실패' not in n['title']]
    )

    dc_html = ""
    for idx, p in enumerate(dc_posts):
        safe_title = p['title'].replace('"', '&quot;')
        p_no = p.get('no', 'ERR')
        dc_html += f"""
        <li class="dc-item" data-no="{p_no}" data-rank="{idx}" data-title="{safe_title}" data-up="{p['upvotes']}" data-views="{p['views']}" data-date="{p['date']}" data-link="{p['link']}">
            <div class="meta-line" style="justify-content:space-between;">
                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                    <span class="dc-new-badge" style="display:none;">🆕 NEW</span>
                    <span>{p['date']} | 조회 {p['views']} | <span style="color:#ff5252; font-weight:bold;">추천 {p['upvotes']}</span></span>
                    <span class="dc-diff-badge" style="color:#00e676; font-size:0.85em; font-weight:bold;"></span>
                </div>
                <button class="dc-mini-btn" title="이 게시글을 천안문·박제 목록에 수동 보관" onclick="manualArchiveDcPost('{p_no}')">+박제보관</button>
            </div>
            <a href="{p['link']}" target="_blank">{p['title']} <span style="color:#4fc3f7; font-weight:bold;">{p['comments']}</span></a>
        </li>
        """

    news_html = ""
    for idx, n in enumerate(news):
        badge_class = "badge-risk" if n['cat_code'] == 'RISK' else ("badge-pr" if n['cat_code'] == 'PR' else "badge-gen")
        dup_cnt = len(n.get('dups', []))
        dup_html = ""
        if dup_cnt > 0:
            dup_links = ", ".join([f"<a href='{d['link']}' target='_blank' style='color:#ffd54f; font-size:0.85em;'>{d['press']}</a>" for d in n['dups'][:8]])
            dup_html = f"<div class='dup-box' style='margin-top:5px; padding:6px 10px; background:#12141a; border-left:3px solid #ffd54f; font-size:0.82em; color:#aaa;'>📢 동일 보도자료 복붙 언론사 ({dup_cnt}곳): {dup_links}</div>"
        
        safe_raw = n.get('pure_title', n['title']).replace('"', '&quot;')
        news_key = re.sub(r'\W+', '', n['title'])[:16]
        news_html += f"""
        <li class="news-item" data-idx="{idx}" data-key="{news_key}" data-cat="{n['cat_code']}" data-dups="{dup_cnt}" data-raw="{safe_raw}">
            <div class="meta-line">
                <span class="n-badge {badge_class}" title="클릭 시 [리스크 ➔ 언플 ➔ 일반 ➔ 자동판독 복구] 순환 및 자가학습" style="cursor:pointer;" onclick="cycleNewsManualCat(this)">{n['cat_label']}</span>
                <button class="manual-reset-btn" style="display:none; background:#2b3242; color:#4fc3f7; border:1px solid #4fc3f7; border-radius:4px; font-size:0.7em; padding:1px 6px; cursor:pointer;" onclick="restoreAutoNewsCat(this)">↺ 자동복구</button>
                <span>{n['date']}</span>
            </div>
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
        mode_label = "롱폼+쇼츠 최신 4선" if ch.get('mode') == 'ALL_LATEST' else "롱폼 최신 4선"
        status_badge = f"<span style='font-size:0.72em; color:#00e676; margin-left:6px;'>🟢 LIVE ({mode_label})</span>" if ch.get('is_live') else f"<span style='font-size:0.72em; color:#8b949e; margin-left:6px;'>⚪ 스냅샷 ({mode_label})</span>"
        block = f"<div class='channel-name'><a href='{ch['handle']}' target='_blank'>[{ch['name']}] ↗</a>{status_badge}</div>"
        for v in ch['videos']:
            vid_code = v.get('vid') or v['link'].split('v=')[-1].split('/')[-1]
            safe_vtitle = v['title'].replace("'", "").replace('"', '')
            block += f"""
            <div class="yt-item">
                <div style="position:relative; cursor:pointer;" onclick="playInlineVideo('{vid_code}', '{safe_vtitle}')" title="클릭하여 대시보드 내 미니 플레이어로 재생">
                    <img src="{v['thumb']}" alt="thumb" onerror="this.style.display='none'">
                    <span style="position:absolute; bottom:4px; right:4px; background:rgba(0,0,0,0.8); color:#fff; font-size:0.68em; padding:2px 5px; border-radius:4px;">▶ 바로재생</span>
                </div>
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

    yt_search_html = ""
    if yt_hot_search:
        for v in yt_hot_search:
            vid_code = v.get('vid') or v['link'].split('v=')[-1].split('/')[-1]
            safe_vtitle = v['title'].replace("'", "").replace('"', '')
            yt_search_html += f"""
            <div class="yt-item">
                <div style="position:relative; cursor:pointer;" onclick="playInlineVideo('{vid_code}', '{safe_vtitle}')" title="클릭하여 대시보드 내 미니 플레이어로 재생">
                    <img src="{v['thumb']}" alt="thumb" onerror="this.style.display='none'">
                    <span style="position:absolute; bottom:4px; right:4px; background:rgba(0,0,0,0.8); color:#fff; font-size:0.68em; padding:2px 5px; border-radius:4px;">▶ 바로재생</span>
                </div>
                <div class="yt-info">
                    <a href="{v['link']}" target="_blank">{v['title']}</a>
                    <div class="yt-meta"><span style="color:#ffd54f;">[{v['channel']}]</span> {v['date']} | 조회수 {v['views']}</div>
                </div>
            </div>
            """
    else:
        yt_search_html = "<div style='color:#888; font-size:0.9em;'>실시간 검색 결과를 불러올 수 없습니다.</div>"

    seed_deleted_candidates = [
        {"no": "848625", "title": "애미창녀자식 종원이 '필독'", "up": "222", "views": "2616", "date": "11.16", "link": "https://gall.dcinside.com/board/view/?id=bjwstreet&no=848625", "confirmed": False, "detectedAt": "이전세션"},
        {"no": "847196", "title": "지하에 배달 공장을 만들어놨네 ㅋㅋㅋ", "up": "193", "views": "6733", "date": "11.14", "link": "https://gall.dcinside.com/board/view/?id=bjwstreet&no=847196", "confirmed": False, "detectedAt": "이전세션"},
        {"no": "847598", "title": "(속보)우리동네 새마을식당 최신 리뷰", "up": "220", "views": "7024", "date": "11.14", "link": "https://gall.dcinside.com/board/view/?id=bjwstreet&no=847598", "confirmed": False, "detectedAt": "이전세션"},
        {"no": "848617", "title": "백씨 평소 인격 제대로 보여주는 영상.jpg", "up": "75", "views": "2463", "date": "11.16", "link": "https://gall.dcinside.com/board/view/?id=bjwstreet&no=848617", "confirmed": False, "detectedAt": "이전세션"}
    ]

    default_news_kw_json = json.dumps(NEWS_KEYWORDS, ensure_ascii=False)
    default_radar_kw_json = json.dumps(RADAR_KEYWORDS, ensure_ascii=False)
    raw_titles_json = json.dumps(all_titles_for_radar, ensure_ascii=False)
    dc_page2_json = json.dumps(dc_page2_meta, ensure_ascii=False)
    seed_deleted_json = json.dumps(seed_deleted_candidates, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="strict-origin-when-cross-origin">
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
        
        .header-container {{ text-align: center; border-bottom: 1px solid var(--border-color); padding-bottom: 20px; margin-bottom: 20px; display: flex; flex-direction: column; align-items: center; gap: 10px; }}
        .logo-wrapper {{ display: flex; gap: 20px; justify-content: center; align-items: center; background: #fff; padding: 8px 22px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
        .logo-wrapper img {{ height: 40px; object-fit: contain; }}
        h1 {{ color: var(--accent-red); margin: 0; font-size: 1.9em; letter-spacing: -0.5px; }}
        .update-bar {{ display: flex; align-items: center; gap: 12px; font-size: 0.88em; color: var(--text-muted); flex-wrap: wrap; justify-content: center; }}

        .radar-wrapper {{ max-width: 1700px; margin: 0 auto 20px auto; }}
        .radar-bar {{ background: #14171f; border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 18px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }}
        .radar-left {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; flex: 1; }}
        .radar-title {{ color: var(--accent-gold); font-weight: bold; font-size: 0.95em; margin-right: 4px; }}
        .kw-badge {{ background: #232834; color: #d0d7de; padding: 5px 11px; border-radius: 20px; font-size: 0.85em; border: 1px solid #343b4a; display: inline-flex; align-items: center; gap: 5px; cursor: pointer; transition: 0.15s; }}
        .kw-badge:hover {{ border-color: var(--accent-blue); background: #2b3242; }}
        .kw-badge.active-filter {{ background: rgba(79, 195, 247, 0.25) !important; border-color: var(--accent-blue) !important; color: #fff; font-weight: bold; }}
        .kw-badge.boosted {{ border-color: rgba(255, 213, 79, 0.5); background: rgba(255, 213, 79, 0.08); }}
        .kw-badge b {{ color: var(--accent-red); }}
        .kw-ban-x {{ color: #768390; cursor: pointer; font-size: 0.9em; margin-left: 3px; padding: 0 3px; }}
        .kw-ban-x:hover {{ color: #ff5252; font-weight: bold; }}

        .container {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; max-width: 1700px; margin: 0 auto; }}
        @media (max-width: 1200px) {{ .container {{ grid-template-columns: 1fr 1fr; }} }}
        @media (max-width: 768px) {{ .container {{ grid-template-columns: 1fr; }} }}

        .card {{ background: var(--bg-card); padding: 22px; border-radius: 12px; border: 1px solid var(--border-color); box-shadow: 0 6px 16px rgba(0,0,0,0.4); display: flex; flex-direction: column; }}
        h2 {{ color: var(--accent-blue); font-size: 1.2em; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; margin: 0 0 15px 0; display: flex; justify-content: space-between; align-items: center; gap: 6px; flex-wrap: wrap; }}
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
        .gauge-bar-bg {{ width: 100%; height: 8px; background: #2b303c; border-radius: 4px; overflow: hidden; display: flex; }}
        .gauge-bar-fill {{ height: 100%; background: linear-gradient(90deg, #ff1744, #ff9100, #00e676); width: {stock['margin_safety']}%; }}

        .tab-group {{ display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }}
        .tab-btn {{ background: #232834; color: #aaa; border: 1px solid #343b4a; padding: 5px 10px; border-radius: 6px; cursor: pointer; font-size: 0.8em; font-weight: bold; }}
        .tab-btn.active {{ background: var(--accent-blue); color: #000; border-color: var(--accent-blue); }}

        .kw-mgr-btn {{ background: #262c3a; color: var(--accent-gold); border: 1px solid #3d4659; padding: 5px 10px; border-radius: 6px; cursor: pointer; font-size: 0.76em; font-weight: bold; flex-shrink: 0; }}
        .kw-mgr-btn:hover {{ background: #323a4d; }}
        .kw-manager-panel {{ display: none; background: #12151c; border: 1px solid #343b4a; border-radius: 8px; padding: 14px; margin-top: 10px; margin-bottom: 14px; }}
        .kw-sec-title {{ font-size: 0.8em; font-weight: bold; margin: 10px 0 6px 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; }}
        .kw-sec-title:first-child {{ margin-top: 0; }}
        .kw-input-row {{ display: flex; gap: 6px; margin-bottom: 8px; }}
        .kw-input {{ flex: 1; background: #1b1f29; border: 1px solid #343b4a; color: #fff; padding: 5px 9px; border-radius: 5px; font-size: 0.8em; }}
        .kw-add-btn {{ background: #2d3546; color: #fff; border: 1px solid #455068; padding: 5px 10px; border-radius: 5px; cursor: pointer; font-size: 0.78em; font-weight: bold; }}
        .kw-add-btn:hover {{ opacity: 0.9; }}
        .kw-tag-wrap {{ display: flex; flex-wrap: wrap; gap: 5px; max-height: 95px; overflow-y: auto; padding: 4px 0; }}
        .kw-edit-tag {{ padding: 2px 7px; border-radius: 4px; font-size: 0.75em; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }}
        .kw-edit-tag:hover {{ opacity: 0.8; text-decoration: line-through; }}
        .kw-mgr-footer {{ display: flex; justify-content: space-between; gap: 6px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed #2a2f3a; flex-wrap: wrap; }}

        .chart-img {{ width: 100%; border-radius: 8px; filter: invert(0.9) hue-rotate(180deg); border: 1px solid #333; }}

        .scroll-list {{ list-style: none; padding: 0; margin: 0; max-height: 620px; overflow-y: auto; padding-right: 5px; }}
        .scroll-list::-webkit-scrollbar {{ width: 6px; }}
        .scroll-list::-webkit-scrollbar-thumb {{ background: #343b4a; border-radius: 3px; }}
        .scroll-list li {{ padding: 11px 0; border-bottom: 1px solid #232730; }}
        .scroll-list li:last-child {{ border-bottom: none; }}
        .meta-line {{ font-size: 0.8em; color: var(--text-muted); margin-bottom: 4px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}

        .n-badge {{ padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: bold; }}
        .badge-risk {{ background: rgba(255, 82, 82, 0.2); color: #ff5252; border: 1px solid rgba(255, 82, 82, 0.4); }}
        .badge-pr {{ background: rgba(255, 213, 79, 0.15); color: #ffd54f; border: 1px solid rgba(255, 213, 79, 0.4); }}
        .badge-gen {{ background: rgba(79, 195, 247, 0.15); color: #4fc3f7; border: 1px solid rgba(79, 195, 247, 0.3); }}
        .dc-new-badge {{ background: #00e676; color: #000; padding: 1px 5px; border-radius: 4px; font-size: 0.72em; font-weight: 800; }}
        .dc-mini-btn {{ background: #1e2430; color: #9ca3af; border: 1px solid #343b4a; border-radius: 4px; font-size: 0.72em; padding: 1px 6px; cursor: pointer; }}
        .dc-mini-btn:hover {{ color: #fff; border-color: #4fc3f7; background: #262f40; }}

        .channel-name {{ margin: 18px 0 10px 0; padding-bottom: 5px; border-bottom: 1px dashed #333; }}
        .channel-name:first-child {{ margin-top: 0; }}
        .channel-name a {{ color: #a5d6a7; font-weight: bold; font-size: 1.05em; }}
        .yt-item {{ display: flex; gap: 12px; margin-bottom: 14px; align-items: flex-start; }}
        .yt-item img {{ width: 130px; height: 74px; object-fit: cover; border-radius: 6px; flex-shrink: 0; border: 1px solid #333; display: block; }}
        .yt-info a {{ font-size: 0.95em; font-weight: bold; margin-bottom: 5px; word-break: keep-all; }}
        .yt-meta {{ font-size: 0.8em; color: var(--text-muted); }}

        .hub-btn {{ width: 100%; background: linear-gradient(135deg, #1e293b, #0f172a); color: #4fc3f7; border: 1px solid #334155; padding: 12px 14px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.92em; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; transition: 0.2s; }}
        .hub-btn:hover {{ border-color: #4fc3f7; background: #1e293b; color: #fff; }}

        .inline-player-box {{ display: none; background: #000; border: 1px solid #4fc3f7; border-radius: 8px; padding: 8px; margin-bottom: 12px; }}
        .inline-player-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.8em; color: #4fc3f7; margin-bottom: 6px; font-weight: bold; gap: 6px; }}
    </style>
</head>
<body>
    <div class="header-container">
        <div class="logo-wrapper">
            <img src="https://clogo.saramin.co.kr/company/logo/201904/01/pp9q4h_a2oy-2rxibo_logo.png" referrerpolicy="no-referrer" alt="더본코리아">
            <img src="https://paikdabang.com/wp-content/themes/paikdabang/assets/images/logo.png" referrerpolicy="no-referrer" alt="빽다방">
            <img src="https://start.theborn.co.kr/images/brand/hongkong/common/logo.png" referrerpolicy="no-referrer" alt="홍콩반점">
        </div>
        <h1>더본코리아 빽모니터링 PRO</h1>
        <div class="update-bar">
            <span>마지막 업데이트: {current_time}</span>
            <button class="kw-mgr-btn" onclick="location.reload()">🔄 즉시 새로고침</button>
            <button id="autoRefreshBtn" class="kw-mgr-btn" style="color:#8b949e;" onclick="toggleAutoRefresh()">⏱️ 5분 자동갱신: OFF</button>
        </div>
    </div>

    <div class="radar-wrapper">
        <div class="radar-bar">
            <div class="radar-left">
                <span class="radar-title">🔥 실시간 이슈 핵심 명사 (배지 클릭 시 뉴스+골갤 동시 필터 · × 클릭 시 제외):</span>
                <span id="radarBadgesContainer" style="display:contents;"></span>
            </div>
            <div style="display:flex; gap:6px; align-items:center;">
                <input type="text" id="quickSearchInput" class="kw-input" style="width:185px;" placeholder="🔍 뉴스+골갤 즉시 검색..." oninput="applyQuickSearch(this.value)">
                <button id="clearSearchBtn" class="kw-add-btn" style="display:none; background:#ff5252; border:none;" onclick="applyQuickSearch('')">✕ 해제</button>
                <button class="kw-mgr-btn" onclick="togglePanel('radarManagerPanel')">⚙️ 핵심명사 관리</button>
            </div>
        </div>

        <div id="radarManagerPanel" class="kw-manager-panel">
            <div class="kw-sec-title" style="color:#ffd54f;">
                <span>📌 우선 추출·보존 핵심 명사 (클릭 시 삭제)</span>
            </div>
            <div class="kw-input-row">
                <input type="text" id="inputRadarBoost" class="kw-input" placeholder="우선 추출할 핵심 명사 입력" onkeydown="if(event.key==='Enter') addRadarKw('BOOST')">
                <button class="kw-add-btn" onclick="addRadarKw('BOOST')">+ 추가</button>
            </div>
            <div id="tagsRadarBoost" class="kw-tag-wrap"></div>

            <div class="kw-sec-title" style="color:#ff5252;">
                <span>🚫 레이더 랭킹 제외 불용어 (클릭 시 복원)</span>
            </div>
            <div class="kw-input-row">
                <input type="text" id="inputRadarStop" class="kw-input" placeholder="랭킹에서 뺄 단어 입력" onkeydown="if(event.key==='Enter') addRadarKw('STOP')">
                <button class="kw-add-btn" onclick="addRadarKw('STOP')">+ 제외 추가</button>
            </div>
            <div id="tagsRadarStop" class="kw-tag-wrap"></div>

            <div class="kw-mgr-footer">
                <button class="kw-add-btn" style="background:#1f2937; color:#9ca3af;" onclick="resetRadarDefault()">↺ 명사 설정 초기화</button>
                <button class="kw-add-btn" style="background:#0284c7; border-color:#0369a1;" onclick="copyAllPythonConfig()">📋 전체 파이썬 설정 코드 복사</button>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- [상단 좌측] 1. 더본코리아 주가 & 오너리스크 지표 -->
        <div class="card">
            <h2>
                <span>📉 더본코리아 주가 & 오너리스크 지표</span>
                <span id="lastVisitStockDiff" style="font-size:0.75em; color:#ffd54f;"></span>
            </h2>
            <div class="stock-top">
                <div class="stock-price" id="currentStockPrice" data-raw="{stock['raw_price']}">{stock['price']} 원</div>
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
            <img id="stockChartImg" src="{stock['chart_day']}" referrerpolicy="no-referrer" class="chart-img" alt="주가 차트">

            <h2 style="margin-top:22px; font-size:1.05em;">📑 최근 전자공시 (DART 연동)</h2>
            <ul class="scroll-list" style="max-height: 190px;">
                {disc_html}
            </ul>
        </div>

        <!-- [상단 중앙] 2. 실시간 뉴스 판독기 -->
        <div class="card">
            <h2>
                <span>📰 실시간 뉴스 판독기 (자가학습·물타기 분리)</span>
                <button class="kw-mgr-btn" onclick="togglePanel('kwManagerPanel')">⚙️ 키워드·학습 관리</button>
            </h2>

            <div class="gauge-wrap" style="padding:8px 12px; margin-bottom:10px;">
                <div class="gauge-header" style="margin-bottom:4px;">
                    <span id="ratioRiskText" style="color:#ff5252; font-weight:bold;">🚨 리스크 0%</span>
                    <span style="font-size:0.85em; color:#8b949e;">배지 클릭 시 수동전환+자동학습 (↺ 복구 가능)</span>
                    <span id="ratioPrText" style="color:#ffd54f; font-weight:bold;">🎺 언플·물타기 0%</span>
                </div>
                <div class="gauge-bar-bg">
                    <div id="newsRiskBar" style="height:100%; background:#ff5252; width:50%; transition:0.3s;"></div>
                    <div id="newsPrBar" style="height:100%; background:#ffd54f; width:50%; transition:0.3s;"></div>
                </div>
            </div>

            <div id="kwManagerPanel" class="kw-manager-panel" style="margin-top:0;">
                <div class="kw-sec-title" style="color:#00e676;">
                    <span>🧠 수동 분류 자가학습 메모리 (클릭 시 삭제)</span>
                    <button class="kw-add-btn" style="font-size:0.72em; padding:2px 7px;" onclick="clearLearnedMemory()">학습 초기화</button>
                </div>
                <div id="tagsLearned" class="kw-tag-wrap" style="margin-bottom:8px;"></div>

                <div class="kw-sec-title" style="color:#ff5252;">
                    <span>🚨 쟁점·리스크 키워드 (클릭 시 삭제)</span>
                </div>
                <div class="kw-input-row">
                    <input type="text" id="inputRiskKw" class="kw-input" placeholder="리스크 단어 입력" onkeydown="if(event.key==='Enter') addNewsKw('RISK')">
                    <button class="kw-add-btn" onclick="addNewsKw('RISK')">+ 추가</button>
                </div>
                <div id="tagsRisk" class="kw-tag-wrap"></div>

                <div class="kw-sec-title" style="color:#ffd54f;">
                    <span>🎺 자본언플·홍보 키워드 (클릭 시 삭제)</span>
                </div>
                <div class="kw-input-row">
                    <input type="text" id="inputPrKw" class="kw-input" placeholder="언플 단어 입력" onkeydown="if(event.key==='Enter') addNewsKw('PR')">
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
                    <button class="kw-add-btn" style="background:#1f2937; color:#9ca3af;" onclick="resetNewsDefault()">↺ 뉴스 설정 전체 초기화</button>
                    <button class="kw-add-btn" style="background:#0284c7; border-color:#0369a1;" onclick="copyAllPythonConfig()">📋 학습 단어 포함 파이썬 코드 복사</button>
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

        <!-- [상단 우측] 3. 유튜브 트래픽 전쟁 (전 채널 4선 + Mr.Paik 미국채널 박제) -->
        <div class="card">
            <h2>📺 유튜브 트래픽 전쟁 (채널당 최신 4선)</h2>
            <div class="tab-group">
                <button class="tab-btn active" onclick="switchYtTab('CRITIC', this)">⚡ 비판 (오재나·탐코·실록)</button>
                <button class="tab-btn" onclick="switchYtTab('SEARCH', this)">🔥 전체 유튜브 최신이슈</button>
                <button class="tab-btn" onclick="switchYtTab('OFFICIAL', this)">🛡️ 백종원·더본 공식 (+미국채널)</button>
            </div>

            <div id="inlinePlayerBox" class="inline-player-box">
                <div class="inline-player-header">
                    <span id="inlinePlayerTitle" style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">▶ 동영상 재생 중</span>
                    <button id="popupPlayerBtn" class="kw-add-btn" style="background:#0284c7; border:none; padding:2px 8px;">🪟 팝업창 재생</button>
                    <button class="kw-add-btn" style="background:#ff5252; border:none; padding:2px 8px;" onclick="closeInlineVideo()">✕ 닫기</button>
                </div>
                <div style="position:relative; padding-bottom:56.25%; height:0; overflow:hidden; border-radius:6px;">
                    <iframe id="inlinePlayerFrame" referrerpolicy="strict-origin-when-cross-origin" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;" allowfullscreen></iframe>
                </div>
            </div>

            <div id="ytCriticBox" class="scroll-list">
                {yt_critic_html}
            </div>
            <div id="ytSearchBox" class="scroll-list" style="display:none;">
                {yt_search_html}
            </div>
            <div id="ytOfficialBox" class="scroll-list" style="display:none;">
                {yt_official_html}
            </div>
        </div>

        <!-- [하단 좌측 - 주가 지표 바로 밑] 4. 시총 증발·펀더멘털 & 종토방 허브 -->
        <div class="card">
            <h2>📊 시총 증발·펀더멘털 & 종토방 허브</h2>
            <div class="kpi-grid" style="grid-template-columns: 1fr 1fr; margin-top: 4px;">
                <div class="kpi-box">
                    <div class="kpi-label">현재 시가총액</div>
                    <div class="kpi-val" style="color:#fff;">{stock['mcap_str']}</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-label">고점(9,508억) 대비 증발</div>
                    <div class="kpi-val" style="color:#ff5252;">{stock['mcap_lost_str']}</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-label">주당순이익 (EPS)</div>
                    <div class="kpi-val" style="color:#ff5252;">-441원 (적자전환)</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-label">52주 최저가(12,130원) 대비</div>
                    <div class="kpi-val" style="color:#ffd54f;">{stock['from_52w_low']}</div>
                </div>
            </div>

            <div class="gauge-wrap" style="margin-bottom: 16px;">
                <div class="gauge-header">
                    <span>👤 백종원 보유지분(59.65%) 평가액</span>
                    <span style="color:#ffd54f; font-weight:bold;">{stock['paik_val_str']} (50억 주담대 설정)</span>
                </div>
            </div>

            <h2 style="font-size:1.05em; margin-top:4px;">🤬 실시간 종토방 & 커뮤니티 원클릭 뷰어</h2>
            <div style="font-size:0.8em; color:#8b949e; margin-bottom:10px;">
                버튼 클릭 시 화면 우측에 스마트폰 크기의 실시간 전용 창이 나란히 열립니다.
            </div>
            <button class="hub-btn" onclick="openSidePopup('https://m.stock.naver.com/domestic/stock/475560/discussion', 'naver_jt')">
                <span>🪟 네이버 Npay 종토방 & 주주오픈톡 미니창 열기</span>
                <span>↗</span>
            </button>
            <button class="hub-btn" onclick="openSidePopup('https://www.fmkorea.com/search.php?mid=best&search_keyword=%EB%B0%B1%EC%A2%85%EC%9B%90&search_target=title_content', 'fmkorea_baek')">
                <span>🪟 에펨코리아(펨코) '백종원' 포텐 검색창 열기</span>
                <span>↗</span>
            </button>
            <button class="hub-btn" onclick="openSidePopup('https://gall.dcinside.com/board/lists/?id=bjwstreet', 'dc_all')">
                <span>🪟 골목식당 갤러리 전체글 실시간 미니창 열기</span>
                <span>↗</span>
            </button>
        </div>

        <!-- [하단 중앙·우측 2칸] 5. 골목식당 갤러리 개념글 (1·2페이지 동시 대조 천안문 관리) -->
        <div class="card" style="grid-column: span 2;">
            <h2>
                <span id="dcHeaderTitle">🦅 골목식당 갤러리 개념글 (실시간 파묘 50선)</span>
                <div style="display:flex; gap:6px; align-items:center;">
                    <span id="dcNewCountBadge" style="font-size:0.75em; color:#00e676;"></span>
                    <button id="btnShowDeleted" class="kw-mgr-btn" style="color:#ff5252; border-color:#ff5252;" onclick="togglePanel('dcDeletedPanel')">🚨 천안문·삭제 관리 (0)</button>
                </div>
            </h2>

            <div id="dcDeletedPanel" class="kw-manager-panel" style="display:block; margin-top:0; border-color:#ff5252;">
                <div class="kw-sec-title" style="color:#ff5252;">
                    <span>🚨 천안문·삭제 개별 관리함 (1·2페이지 동시 대조 완료 · [🔍 원문확인] 후 [📌 박제확정] 또는 [✕ 제외] 선택)</span>
                    <div style="display:flex; gap:5px; flex-wrap:wrap;">
                        <button class="kw-add-btn" style="font-size:0.72em; padding:3px 8px; background:#0284c7; border-color:#0369a1;" onclick="pruneAliveFromDeletedLog()">🧹 1·2페이지 생존글 자동정리</button>
                        <button class="kw-add-btn" style="font-size:0.72em; padding:3px 8px; background:#374151;" onclick="clearUnconfirmedDeleted()">🧹 미확정만 비우기</button>
                        <button class="kw-add-btn" style="font-size:0.72em; padding:3px 8px; background:#7f1d1d; border-color:#991b1b;" onclick="clearDeletedHistory()">🗑️ 전체 초기화</button>
                    </div>
                </div>
                <ul id="dcDeletedList" class="scroll-list" style="max-height:240px; font-size:0.88em;"></ul>
            </div>

            <ul id="dcPostList" class="scroll-list" style="max-height: 600px; display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px;">
                {dc_html}
            </ul>
        </div>
    </div>

    <script>
        const DEFAULT_NEWS_KW = {default_news_kw_json};
        const DEFAULT_RADAR_KW = {default_radar_kw_json};
        const RAW_TITLES = {raw_titles_json};
        const DC_PAGE2_META = {dc_page2_json};
        const SEED_DELETED_CANDIDATES = {seed_deleted_json};

        // 영구 고정 키 이름 사용
        const NEWS_STORAGE_KEY = 'theborn_news_kw_master';
        const RADAR_STORAGE_KEY = 'theborn_radar_kw_master';
        const MANUAL_NEWS_CAT_KEY = 'theborn_manual_news_cat_master';
        const LEARNED_TOKENS_KEY = 'theborn_learned_tokens_master';
        const DC_SNAPSHOT_KEY = 'theborn_dc_snapshot_master';
        const DC_DELETED_LOG_KEY = 'theborn_dc_deleted_log_master';
        const DC_IGNORED_NOS_KEY = 'theborn_dc_ignored_nos_master';
        const LAST_STOCK_PRICE_KEY = 'theborn_last_stock_master';
        const AUTO_REFRESH_STATE_KEY = 'theborn_auto_refresh_master';

        let currentFilter = 'ALL';
        let activeKeywordFilter = '';
        let autoRefreshInterval = null;
        let remainSeconds = 300;
        let userNewsKw = loadStored(NEWS_STORAGE_KEY, DEFAULT_NEWS_KW);
        let userRadarKw = loadStored(RADAR_STORAGE_KEY, DEFAULT_RADAR_KW);
        let manualNewsCats = loadStored(MANUAL_NEWS_CAT_KEY, {{}});
        let learnedTokens = loadStored(LEARNED_TOKENS_KEY, {{}});
        let ignoredDeletedNos = new Set(loadStored(DC_IGNORED_NOS_KEY, []));

        // 기존에 잘못 학습된 흔한 일반 단어('분기', '연속' 등) 자동 청소
        ['분기', '연속', '억원', '만원', '매출', '적자', '영업손실'].forEach(badTk => {{
            if (learnedTokens[badTk]) delete learnedTokens[badTk];
        }});
        localStorage.setItem(LEARNED_TOKENS_KEY, JSON.stringify(learnedTokens));

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

        function openSidePopup(url, name) {{
            const w = 520;
            const h = Math.min(window.screen.availHeight - 60, 920);
            const left = window.screen.availWidth - w - 20;
            window.open(url, name, `width=${{w}},height=${{h}},left=${{left}},top=30,resizable=yes,scrollbars=yes`);
        }}

        function playInlineVideo(vid, title) {{
            const box = document.getElementById('inlinePlayerBox');
            const frame = document.getElementById('inlinePlayerFrame');
            const popBtn = document.getElementById('popupPlayerBtn');
            const watchUrl = `https://www.youtube.com/watch?v=${{vid}}`;
            document.getElementById('inlinePlayerTitle').textContent = '▶ ' + title;
            popBtn.onclick = () => openSidePopup(watchUrl, 'yt_popup_player');

            if (window.location.protocol === 'file:') {{
                openSidePopup(watchUrl, 'yt_popup_player');
                return;
            }}
            frame.src = `https://www.youtube.com/embed/${{vid}}?autoplay=1&rel=0`;
            box.style.display = 'block';
        }}

        function closeInlineVideo() {{
            const box = document.getElementById('inlinePlayerBox');
            const frame = document.getElementById('inlinePlayerFrame');
            frame.src = '';
            box.style.display = 'none';
        }}

        // --- ⏱️ V16 영구 유지형 5분 자동갱신 타이머 (새로고침 후에도 절대 OFF로 풀리지 않음) ---
        function formatRemainTime(sec) {{
            const m = Math.floor(sec / 60);
            const s = sec % 60;
            return `${{m}}:${{s < 10 ? '0' + s : s}}`;
        }}

        function startAutoRefreshCountdown() {{
            const btn = document.getElementById('autoRefreshBtn');
            if (autoRefreshInterval) clearInterval(autoRefreshInterval);
            remainSeconds = 300;
            btn.style.color = '#00e676';
            btn.style.borderColor = '#00e676';
            btn.textContent = `⏱️ 5분 자동갱신: ON (${{formatRemainTime(remainSeconds)}})`;

            autoRefreshInterval = setInterval(() => {{
                remainSeconds--;
                if (remainSeconds <= 0) {{
                    clearInterval(autoRefreshInterval);
                    location.reload();
                }} else {{
                    btn.textContent = `⏱️ 5분 자동갱신: ON (${{formatRemainTime(remainSeconds)}})`;
                }}
            }}, 1000);
        }}

        function stopAutoRefreshCountdown() {{
            const btn = document.getElementById('autoRefreshBtn');
            if (autoRefreshInterval) {{
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }}
            btn.textContent = '⏱️ 5분 자동갱신: OFF';
            btn.style.color = '#8b949e';
            btn.style.borderColor = '#3d4659';
        }}

        function toggleAutoRefresh() {{
            const isCurrentlyOn = localStorage.getItem(AUTO_REFRESH_STATE_KEY) === 'ON';
            if (isCurrentlyOn) {{
                localStorage.setItem(AUTO_REFRESH_STATE_KEY, 'OFF');
                stopAutoRefreshCountdown();
            }} else {{
                localStorage.setItem(AUTO_REFRESH_STATE_KEY, 'ON');
                startAutoRefreshCountdown();
            }}
        }}

        function initAutoRefreshState() {{
            if (localStorage.getItem(AUTO_REFRESH_STATE_KEY) === 'ON') {{
                startAutoRefreshCountdown();
            }} else {{
                stopAutoRefreshCountdown();
            }}
        }}

        function checkLastVisitStock() {{
            const el = document.getElementById('currentStockPrice');
            const curPrice = parseInt(el.getAttribute('data-raw') || '0', 10);
            const prevPrice = parseInt(localStorage.getItem(LAST_STOCK_PRICE_KEY) || '0', 10);
            const diffBadge = document.getElementById('lastVisitStockDiff');
            if (prevPrice && prevPrice !== curPrice) {{
                const diff = curPrice - prevPrice;
                const sign = diff > 0 ? '+' : '';
                diffBadge.textContent = `(직전 확인 대비 ${{sign}}${{diff.toLocaleString()}}원)`;
                diffBadge.style.color = diff > 0 ? '#ff5252' : '#4fc3f7';
            }}
            if (curPrice > 0) localStorage.setItem(LAST_STOCK_PRICE_KEY, String(curPrice));
        }}

        // --- 🦅 골갤 1·2페이지 교차 대조 천안문 감지 & 사용자 개별 관리 ---
        function getDeletedLog() {{
            let raw = loadStored(DC_DELETED_LOG_KEY, []);
            SEED_DELETED_CANDIDATES.forEach(seed => {{
                const sNo = String(seed.no);
                if (!ignoredDeletedNos.has(sNo) && !raw.some(d => String(d.no) === sNo)) {{
                    raw.push(seed);
                }}
            }});
            return raw.filter(d => d && d.title && !d.title.includes('비어있습니다') && !d.title.includes('일시 응답 지연'));
        }}

        function saveDeletedLog(list) {{
            list.sort((a, b) => (b.confirmed ? 1 : 0) - (a.confirmed ? 1 : 0));
            localStorage.setItem(DC_DELETED_LOG_KEY, JSON.stringify(list.slice(0, 60)));
            renderDeletedDcLog(list);
        }}

        function trackDcPostsAndDeletions() {{
            let prevMap = loadStored(DC_SNAPSHOT_KEY, null);
            if (!prevMap || Object.keys(prevMap).length === 0) {{
                prevMap = loadStored('theborn_dc_snapshot_v14', {{}});
            }}

            let deletedLog = getDeletedLog();
            const currentItems = Array.from(document.querySelectorAll('#dcPostList .dc-item'));

            const validItems = currentItems.filter(li => {{
                const no = li.getAttribute('data-no') || '';
                return /^\\d+$/.test(no) && no !== '0';
            }});
            if (validItems.length < 15) {{
                renderDeletedDcLog(deletedLog);
                return;
            }}

            const page1Nos = new Set();
            const page1Titles = new Set();
            const page2Nos = new Set((DC_PAGE2_META.nos || []).map(String));
            const page2Titles = new Set(DC_PAGE2_META.titles || []);

            const currentMap = {{}};
            let newCount = 0;
            const prevKeys = Object.keys(prevMap);

            validItems.forEach((li, idx) => {{
                const no = String(li.getAttribute('data-no'));
                const title = li.getAttribute('data-title') || '';
                const up = parseInt((li.getAttribute('data-up') || '0').replace(/,/g, ''), 10);
                const views = li.getAttribute('data-views');
                const date = li.getAttribute('data-date');
                const link = li.getAttribute('data-link');

                page1Nos.add(no);
                page1Titles.add(title);
                currentMap[no] = {{ no, title, up, views, date, link, rank: idx }};

                if (prevKeys.length >= 15) {{
                    if (!prevMap[no]) {{
                        li.querySelector('.dc-new-badge').style.display = 'inline-block';
                        newCount++;
                    }} else {{
                        const upDiff = up - (prevMap[no].up || 0);
                        if (upDiff >= 5) {{
                            li.querySelector('.dc-diff-badge').textContent = `(추천 ▲+${{upDiff}})`;
                        }}
                    }}
                }}
            }});

            if (prevKeys.length >= 15) {{
                Object.values(prevMap).forEach(oldPost => {{
                    const sNo = String(oldPost.no);
                    const inPage1 = page1Nos.has(sNo) || page1Titles.has(oldPost.title);
                    const inPage2 = page2Nos.has(sNo) || page2Titles.has(oldPost.title);
                    if (!inPage1 && !inPage2 && !ignoredDeletedNos.has(sNo)) {{
                        if (!deletedLog.some(d => String(d.no) === sNo)) {{
                            deletedLog.unshift({{
                                ...oldPost,
                                confirmed: false,
                                detectedAt: new Date().toLocaleTimeString('ko-KR', {{ hour: '2-digit', minute: '2-digit' }})
                            }});
                        }}
                    }}
                }});
            }}

            deletedLog = deletedLog.filter(d => {{
                if (d.confirmed) return true;
                const sNo = String(d.no);
                const alive = page1Nos.has(sNo) || page1Titles.has(d.title) || page2Nos.has(sNo) || page2Titles.has(d.title);
                return !alive;
            }});

            localStorage.setItem(DC_SNAPSHOT_KEY, JSON.stringify(currentMap));
            if (newCount > 0 && newCount < 45) {{
                document.getElementById('dcNewCountBadge').textContent = `🆕 신규 개념글 ${{newCount}}건`;
            }}
            saveDeletedLog(deletedLog);
        }}

        function renderDeletedDcLog(deletedLog) {{
            const btn = document.getElementById('btnShowDeleted');
            const listEl = document.getElementById('dcDeletedList');
            const confirmedCnt = deletedLog.filter(d => d.confirmed).length;
            btn.textContent = confirmedCnt > 0
                ? `🚨 천안문·삭제 관리 (${{deletedLog.length}}건 · 📌확정 ${{confirmedCnt}})`
                : `🚨 천안문·삭제 관리 (${{deletedLog.length}})`;

            if (!deletedLog.length) {{
                listEl.innerHTML = "<li style='color:#8b949e;'>감지되거나 보관된 게시글이 없습니다. (개념글 우측 [+박제보관]으로 수동 추가 가능)</li>";
                return;
            }}

            listEl.innerHTML = deletedLog.map(d => {{
                const sNo = String(d.no);
                const statusBadge = d.confirmed
                    ? `<span class="n-badge" style="background:#d50000; color:#fff;">📌 천안문 확정</span>`
                    : `<span class="n-badge badge-risk">🚨 1·2P 동시소멸 (확인대기)</span>`;
                const confirmBtnLabel = d.confirmed ? '📌 확정해제' : '📌 박제확정';
                const confirmBtnStyle = d.confirmed
                    ? 'background:#374151; color:#d1d5db; border-color:#4b5563;'
                    : 'background:#991b1b; color:#fff; border-color:#dc2626;';
                const safeLink = d.link || `https://gall.dcinside.com/board/view/?id=bjwstreet&no=${{sNo}}`;

                return `
                <li style="${{d.confirmed ? 'background:rgba(255,82,82,0.08); padding-left:6px; border-left:3px solid #ff5252;' : ''}}">
                    <div class="meta-line" style="justify-content:space-between;">
                        <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                            ${{statusBadge}}
                            <span>#${{sNo}} | 감지 ${{d.detectedAt || '-'}} | 작성 ${{d.date}} | 조회 ${{d.views}} | <b style="color:#ff5252;">추천 ${{d.up}}</b></span>
                        </div>
                        <div style="display:flex; gap:4px;">
                            <button class="dc-mini-btn" style="color:#4fc3f7; border-color:#0284c7;" onclick="openSidePopup('${{safeLink}}', 'dc_verify')">🔍 원문확인</button>
                            <button class="dc-mini-btn" style="${{confirmBtnStyle}}" onclick="toggleConfirmDeletedPost('${{sNo}}')">${{confirmBtnLabel}}</button>
                            <button class="dc-mini-btn" style="color:#ff5252;" onclick="removeSingleDeletedPost('${{sNo}}')">✕ 제외</button>
                        </div>
                    </div>
                    <a href="${{safeLink}}" target="_blank">🗑️ ${{d.title}}</a>
                </li>
                `;
            }}).join('');
        }}

        function toggleConfirmDeletedPost(no) {{
            const sNo = String(no);
            const list = getDeletedLog();
            const target = list.find(d => String(d.no) === sNo);
            if (target) {{
                target.confirmed = !target.confirmed;
                saveDeletedLog(list);
            }}
        }}

        function removeSingleDeletedPost(no) {{
            const sNo = String(no);
            ignoredDeletedNos.add(sNo);
            localStorage.setItem(DC_IGNORED_NOS_KEY, JSON.stringify(Array.from(ignoredDeletedNos).slice(-300)));
            const list = getDeletedLog().filter(d => String(d.no) !== sNo);
            saveDeletedLog(list);
        }}

        function manualArchiveDcPost(no) {{
            const sNo = String(no);
            const li = document.querySelector(`#dcPostList .dc-item[data-no="${{sNo}}"]`);
            if (!li) return;
            ignoredDeletedNos.delete(sNo);
            localStorage.setItem(DC_IGNORED_NOS_KEY, JSON.stringify(Array.from(ignoredDeletedNos)));
            const list = getDeletedLog();
            const existing = list.find(d => String(d.no) === sNo);
            if (existing) {{
                existing.confirmed = true;
            }} else {{
                list.unshift({{
                    no: sNo,
                    title: li.getAttribute('data-title') || '',
                    up: li.getAttribute('data-up') || '0',
                    views: li.getAttribute('data-views') || '0',
                    date: li.getAttribute('data-date') || '-',
                    link: li.getAttribute('data-link') || '#',
                    confirmed: true,
                    detectedAt: '수동보관'
                }});
            }}
            saveDeletedLog(list);
            document.getElementById('dcDeletedPanel').style.display = 'block';
        }}

        function pruneAliveFromDeletedLog() {{
            const page1Nos = new Set(Array.from(document.querySelectorAll('#dcPostList .dc-item')).map(li => String(li.getAttribute('data-no'))));
            const page1Titles = new Set(Array.from(document.querySelectorAll('#dcPostList .dc-item')).map(li => li.getAttribute('data-title')));
            const page2Nos = new Set((DC_PAGE2_META.nos || []).map(String));
            const page2Titles = new Set(DC_PAGE2_META.titles || []);
            const list = getDeletedLog().filter(d => {{
                if (d.confirmed) return true;
                const sNo = String(d.no);
                return !(page1Nos.has(sNo) || page1Titles.has(d.title) || page2Nos.has(sNo) || page2Titles.has(d.title));
            }});
            saveDeletedLog(list);
        }}

        function clearUnconfirmedDeleted() {{
            const list = getDeletedLog();
            list.forEach(d => {{ if (!d.confirmed) ignoredDeletedNos.add(String(d.no)); }});
            localStorage.setItem(DC_IGNORED_NOS_KEY, JSON.stringify(Array.from(ignoredDeletedNos).slice(-300)));
            saveDeletedLog(list.filter(d => d.confirmed));
        }}

        function clearDeletedHistory() {{
            if (!confirm('박제 확정된 항목을 포함해 전체 기록을 초기화하시겠습니까?')) return;
            const list = getDeletedLog();
            list.forEach(d => ignoredDeletedNos.add(String(d.no)));
            localStorage.setItem(DC_IGNORED_NOS_KEY, JSON.stringify(Array.from(ignoredDeletedNos).slice(-300)));
            localStorage.setItem(DC_DELETED_LOG_KEY, JSON.stringify([]));
            renderDeletedDcLog([]);
        }}

        // --- 🔥 핵심 명사 레이더 ---
        const JOSA_REGEX = /(에서부터|으로부터|에서|으로|이랑|하고|부터|까지|마저|조차|에게|한테|처럼|보다|라고|이라|다는|라는|은|는|이|가|을|를|의|에|로|과|와|도|만|한|할|함|임)$/;
        const PRED_REGEX = /(없어|없어도|없어서|있어|있어도|있어서|같아|같아서|있다|없다|같다|되다|하다|이다|봤다|왔다|갔다|했다|됐다|난다|준다|본다|한다|된다|하면|되면|오면|가면|보면|치면|쓰면|알면|나면|주면|받으면|먹으면|겠냐|겠노|겠네|하노|하냐|하나|할까|볼까|하자|해라|마라|거임|건가|인듯|인가|구만|구나|던데|는데|길래|잖아|더라|봐유|애유|네유|햇네|했네)$/;

        function normalizeNoun(word, stopSet, boostList) {{
            let w = word.toLowerCase().replace(/[ㄱ-ㅎㅏ-ㅣ]+/g, '');
            if (w.length < 2 || /^\\d+$/.test(w) || /^\\d+[월일편명개년배위곳잔만원호%시분초분기]+$/.test(w)) return '';
            if (stopSet.has(w) || PRED_REGEX.test(w)) return '';

            for (const bw of boostList) {{
                const bLow = bw.toLowerCase();
                if (w === bLow || (w.startsWith(bLow) && w.length <= bLow.length + 2)) {{
                    return bw;
                }}
            }}

            let stemmed = w.replace(JOSA_REGEX, '');
            if (stemmed.length >= 2) w = stemmed;
            if (stopSet.has(w) || PRED_REGEX.test(w)) return '';
            if (w.length >= 3 && (w.endsWith('군') || w.endsWith('시') || w.endsWith('점')) && !/(장군|교시|폐점|출점|지점|반점|직영점)$/.test(w)) {{
                w = w.slice(0, -1);
            }}
            return stopSet.has(w) ? '' : w;
        }}

        function recomputeRadarKeywords() {{
            const stopSet = new Set(userRadarKw.STOP.map(s => s.toLowerCase()));
            const boostList = [...(userRadarKw.BOOST || [])].sort((a, b) => b.length - a.length);
            const boostSet = new Set(boostList.map(b => b.toLowerCase()));
            const freq = {{}};

            RAW_TITLES.forEach(title => {{
                const perTitleSet = new Set();
                let remainingTitle = title;

                boostList.forEach(bw => {{
                    const bLow = bw.toLowerCase();
                    if (remainingTitle.toLowerCase().includes(bLow) && !stopSet.has(bLow)) {{
                        perTitleSet.add(bw);
                        remainingTitle = remainingTitle.replace(new RegExp(bw, 'gi'), ' ');
                    }}
                }});

                const matches = remainingTitle.match(/[가-힣A-Za-z0-9]{{2,}}/g) || [];
                matches.forEach(rawW => {{
                    const norm = normalizeNoun(rawW, stopSet, boostList);
                    if (norm && norm.length >= 2) perTitleSet.add(norm);
                }});

                perTitleSet.forEach(token => {{
                    freq[token] = (freq[token] || 0) + 1;
                }});
            }});

            const sorted = Object.entries(freq)
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
                const isActive = activeKeywordFilter.toLowerCase() === kw.toLowerCase();
                return `<span class="kw-badge ${{isBoost ? 'boosted' : ''}} ${{isActive ? 'active-filter' : ''}}" onclick="toggleRadarFilter('${{kw}}')">
                    #${{kw}} <b>${{cnt}}</b>
                    <span class="kw-ban-x" title="'${{kw}}' 키워드를 레이더에서 즉시 제외" onclick="event.stopPropagation(); banRadarWord('${{kw}}')">×</span>
                </span>`;
            }}).join('');
        }}

        function toggleRadarFilter(kw) {{
            if (activeKeywordFilter.toLowerCase() === kw.toLowerCase()) {{
                applyQuickSearch('');
            }} else {{
                applyQuickSearch(kw);
            }}
        }}

        function applyQuickSearch(query) {{
            const input = document.getElementById('quickSearchInput');
            const clearBtn = document.getElementById('clearSearchBtn');
            if (input.value !== query) input.value = query;
            activeKeywordFilter = query.trim();
            clearBtn.style.display = activeKeywordFilter ? 'inline-block' : 'none';

            const qLow = activeKeywordFilter.toLowerCase();
            recomputeRadarKeywords();
            reclassifyAllNews();

            let dcVisibleCount = 0;
            const dcItems = document.querySelectorAll('#dcPostList .dc-item');
            dcItems.forEach(li => {{
                const t = (li.getAttribute('data-title') || '').toLowerCase();
                const show = (!qLow || t.includes(qLow));
                li.style.display = show ? 'block' : 'none';
                if (show) dcVisibleCount++;
            }});

            const dcHeader = document.getElementById('dcHeaderTitle');
            if (qLow) {{
                dcHeader.textContent = `🦅 골목식당 갤러리 개념글 (🔍 '${{activeKeywordFilter}}' 검색결과 ${{dcVisibleCount}}건 / 총 ${{dcItems.length}}선)`;
            }} else {{
                dcHeader.textContent = `🦅 골목식당 갤러리 개념글 (실시간 파묘 ${{dcItems.length}}선)`;
            }}
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

        const LEARN_STOP_WORDS = new Set([
            '백종원', '백종원의', '백종원이', '더본코리아', '더본', '대표', '빽다방', '홍콩반점',
            '3분기', '2분기', '1분기', '4분기', '분기', '연속', '억원', '만원', '매출', '적자', '영업손실', '적자폭',
            '올해', '내년', '하루', '오늘', '최근', '단독', '종합', '해외', '중국', '글로벌', '사업'
        ]);

        function extractLearnableTokens(titleText) {{
            const mainTitle = titleText.split(' - ')[0] || titleText;
            const words = mainTitle.match(/[가-힣A-Za-z]{{2,}}/g) || [];
            const out = [];
            words.forEach(w => {{
                let clean = w.replace(JOSA_REGEX, '');
                if (clean.length >= 2 && !LEARN_STOP_WORDS.has(clean) && !PRED_REGEX.test(clean)) {{
                    out.push(clean);
                }}
            }});
            return out.slice(0, 4);
        }}

        function learnFromManualClassification(titleText, targetCat) {{
            const tokens = extractLearnableTokens(titleText);
            tokens.forEach(tk => {{
                learnedTokens[tk] = {{ cat: targetCat, updated: Date.now() }};
            }});
            localStorage.setItem(LEARNED_TOKENS_KEY, JSON.stringify(learnedTokens));
            renderNewsTags();
        }}

        function unlearnFromTitle(titleText) {{
            const tokens = extractLearnableTokens(titleText);
            tokens.forEach(tk => {{
                delete learnedTokens[tk];
            }});
            localStorage.setItem(LEARNED_TOKENS_KEY, JSON.stringify(learnedTokens));
            renderNewsTags();
        }}

        function removeLearnedToken(tk) {{
            delete learnedTokens[tk];
            localStorage.setItem(LEARNED_TOKENS_KEY, JSON.stringify(learnedTokens));
            renderNewsTags();
            reclassifyAllNews();
        }}

        function clearLearnedMemory() {{
            learnedTokens = {{}};
            manualNewsCats = {{}};
            localStorage.removeItem(LEARNED_TOKENS_KEY);
            localStorage.removeItem(MANUAL_NEWS_CAT_KEY);
            renderNewsTags();
            reclassifyAllNews();
        }}

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

            const learnedEntries = Object.entries(learnedTokens);
            const learnedBox = document.getElementById('tagsLearned');
            if (!learnedEntries.length) {{
                learnedBox.innerHTML = "<span style='font-size:0.75em; color:#8b949e;'>아직 수동 분류로 학습된 단어가 없습니다. (기사 배지 클릭 시 자동 학습)</span>";
            }} else {{
                learnedBox.innerHTML = learnedEntries.map(([tk, info]) => {{
                    const cls = info.cat === 'RISK' ? 'badge-risk' : (info.cat === 'PR' ? 'badge-pr' : 'badge-gen');
                    const prefix = info.cat === 'RISK' ? '🚨' : (info.cat === 'PR' ? '🎺' : '📰');
                    return `<span class="kw-edit-tag ${{cls}}" title="클릭하여 학습 단어 삭제" onclick="removeLearnedToken('${{tk}}')">${{prefix}} ${{tk}} ×</span>`;
                }}).join('');
            }}
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
            localStorage.removeItem(MANUAL_NEWS_CAT_KEY);
            localStorage.removeItem(LEARNED_TOKENS_KEY);
            manualNewsCats = {{}};
            learnedTokens = {{}};
            userNewsKw = JSON.parse(JSON.stringify(DEFAULT_NEWS_KW));
            renderNewsTags();
            reclassifyAllNews();
        }}

        function cycleNewsManualCat(badgeEl) {{
            const li = badgeEl.closest('.news-item');
            const key = li.getAttribute('data-key');
            const titleText = li.querySelector('a')?.innerText || '';
            const curManual = manualNewsCats[key];

            let nextCat = null;
            if (!curManual) {{
                const curAuto = li.getAttribute('data-cat');
                nextCat = (curAuto === 'RISK') ? 'PR' : 'RISK';
            }} else if (curManual === 'RISK') {{
                nextCat = 'PR';
            }} else if (curManual === 'PR') {{
                nextCat = 'GEN';
            }} else {{
                nextCat = null;
            }}

            if (nextCat) {{
                manualNewsCats[key] = nextCat;
                learnFromManualClassification(titleText, nextCat);
            }} else {{
                delete manualNewsCats[key];
                unlearnFromTitle(titleText);
            }}
            localStorage.setItem(MANUAL_NEWS_CAT_KEY, JSON.stringify(manualNewsCats));
            reclassifyAllNews();
        }}

        function restoreAutoNewsCat(btnEl) {{
            const li = btnEl.closest('.news-item');
            const key = li.getAttribute('data-key');
            const titleText = li.querySelector('a')?.innerText || '';
            delete manualNewsCats[key];
            unlearnFromTitle(titleText);
            localStorage.setItem(MANUAL_NEWS_CAT_KEY, JSON.stringify(manualNewsCats));
            reclassifyAllNews();
        }}

        const JS_HARD_RISK = [
            [/믿었는데|떠나가자|다\s*떠나|등\s*돌린|곡소리|비명|외면|눈물/, '가맹점주 이탈·원성'],
            [/가맹.*해지|폐업|폐점|문\s*닫|철수|퇴출|순감소|50곳\s*순감|꺾였다|급감|해지.*급증|가맹점\s*이탈|점주\s*이탈|매출\s*위축|가맹사업.*흔들/, '가맹해지·매출 위축'],
            [/적자\s*수렁|반토막|적자\s*전환|무색|3분기도\s*적자|연속\s*적자.*폭락|주가.*폭락|신저가|국내는.*휘청|국내.*휘청|부진의\s*수렁/, '실적 악화·적자 수렁'],
            [/유출|침해|해킹|KISA|개인정보|계좌정보|보안\s*논란|수탁사/, '개인정보·보안 사고'],
            [/무더기\s*고소|수백명\s*고소|쪼개기|합의금\s*장사|종토방.*고소|변호사\s*일침|처벌\s*우려|처벌대상|소송\s*위험|무혐의|청구포기|패소|피고소/, '고소 남발·법적 분쟁'],
            [/위생|원산지|꼼수|책임\s*회피|외주\s*탓|갑질|공정위|국감|불똥|경영\s*부담.*가중|끊이지\s*않는\s*악재|0원\s*쿠폰.*논란/, '경영 논란·오너리스크']
        ];

        const JS_SPIN_PR = [
            [/오너\s*리스크\s*해소|리스크.*완화|백종원\s*일냈다|반등\s*열쇠\s*될까/, '오너리스크 해소·반등 억빠'],
            [/(적자|영업손실|영업적자|손실).*(줄었다|줄였다|줄여|감소|축소|개선|원가\s*잡았다)/, '적자 축소 물타기'],
            [/(줄었다|줄였다|줄여|감소|축소|개선).*(적자|영업손실|영업적자|손실)/, '적자 축소 물타기']
        ];

        const JS_STANDARD_PR = [
            [/중국.*매장.*확대|상하이|하루\s*1000잔|불티|무섭게\s*팔린다|中\s*진출|영토\s*확장|아망추.*인기|출점\s*가속|대박\s*조짐|추가\s*출점|더\s*낸다|연착륙/, '중국 빽다방 홍보'],
            [/우녹스|이탈리아\s*오븐|맛\s*표준화|파트너십|맞손|업무협약|MOU|협약|협력|공동\s*개발|데이터화|탑재|오븐\s*시장|유럽.*투트랙|꺼낸\s*승부수|배달전문점\s*실험/, '해외·신사업 홍보'],
            [/피자.*(배달|알바|라이더|오토바이|직접|시켰더니|시키셨|선물|홍보|나서|변신)|일일\s*배달|하루\s*배달|일일\s*라이더|치즈킥|소방서/, '유튜브 배달쇼 홍보'],
            [/소유진|아트하우스|대저택|미술관|내조|애셋맘/, '오너 일가 화제성 언플'],
            [/통영\s*굴|통영굴짬뽕|팔도\s*짬뽕|신제품|신메뉴|출시|선보|프로모션|할인|특가|이벤트|나눔점|기부|체험행사/, '신메뉴·이벤트 홍보'],
            [/\[똑똑한|\[유통가|\[푸드|브리핑|단신|꽂힌\s*소스시장|성장동력\s*확보/, '보도자료·업계 홍보']
        ];

        function classifySingleTitleV16(rawTitle, totalCnt, newsKey) {{
            if (manualNewsCats[newsKey]) {{
                const mCat = manualNewsCats[newsKey];
                const mLabels = {{ 'RISK': '🚨 수동지정: 리스크', 'PR': '🎺 수동지정: 언플', 'GEN': '📰 수동지정: 일반' }};
                return [mCat, mLabels[mCat], true];
            }}
            for (const [reg, reason] of JS_HARD_RISK) {{
                if (reg.test(rawTitle)) {{
                    return ['RISK', totalCnt >= 2 ? `🚨 쟁점확산 (${{totalCnt}}건 · ${{reason}})` : `🚨 리스크 (${{reason}})`, false];
                }}
            }}
            for (const [reg, reason] of JS_SPIN_PR) {{
                if (reg.test(rawTitle)) {{
                    return ['PR', totalCnt >= 2 ? `🎺 복붙언플 (${{totalCnt}}건 · ${{reason}})` : `🎺 물타기언플 (${{reason}})`, false];
                }}
            }}
            for (const [reg, reason] of JS_STANDARD_PR) {{
                if (reg.test(rawTitle)) {{
                    return ['PR', totalCnt >= 2 ? `🎺 복붙언플 (${{totalCnt}}건 · ${{reason}})` : `🎺 자본언플 (${{reason}})`, false];
                }}
            }}
            for (const [tk, info] of Object.entries(learnedTokens)) {{
                if (rawTitle.includes(tk)) {{
                    if (info.cat === 'RISK') return ['RISK', `🚨 학습판독: 리스크 (${{tk}})`, false];
                    if (info.cat === 'PR') return ['PR', `🎺 학습판독: 언플 (${{tk}})`, false];
                    if (info.cat === 'GEN') return ['GEN', `📰 학습판독: 일반 (${{tk}})`, false];
                }}
            }}
            const safeTitleForKw = rawTitle.replace(/이탈리아/g, '이태리');
            const matchedRisk = userNewsKw.RISK.find(rk => safeTitleForKw.includes(rk));
            if (matchedRisk) {{
                return ['RISK', totalCnt >= 2 ? `🚨 쟁점확산 (${{totalCnt}}건 · ${{matchedRisk}})` : `🚨 리스크 (${{matchedRisk}})`, false];
            }}
            const matchedPr = userNewsKw.PR.find(pk => safeTitleForKw.includes(pk));
            if (matchedPr) {{
                return ['PR', totalCnt >= 2 ? `🎺 복붙언플 (${{totalCnt}}건 · ${{matchedPr}})` : `🎺 자본언플 (${{matchedPr}})`, false];
            }}
            if (totalCnt >= 3) {{
                return ['PR', `🎺 보도자료 복붙 (${{totalCnt}}건 살포)`, false];
            }}
            return ['GEN', '📰 일반동향', false];
        }}

        function reclassifyAllNews() {{
            let counts = {{ ALL: 0, RISK: 0, PR: 0, GEN: 0 }};
            const qLow = activeKeywordFilter.toLowerCase();

            document.querySelectorAll('#newsList .news-item').forEach(li => {{
                const rawTitle = li.getAttribute('data-raw') || li.innerText;
                const dupCnt = parseInt(li.getAttribute('data-dups') || '0', 10);
                const newsKey = li.getAttribute('data-key') || '';
                const totalCnt = 1 + dupCnt;

                if (userNewsKw.SPAM.some(sp => rawTitle.includes(sp))) {{
                    li.setAttribute('data-cat', 'SPAM');
                    li.style.display = 'none';
                    return;
                }}

                const [cat, label, isManual] = classifySingleTitleV16(rawTitle, totalCnt, newsKey);

                li.setAttribute('data-cat', cat);
                const badgeEl = li.querySelector('.n-badge');
                if (badgeEl) {{
                    badgeEl.className = 'n-badge ' + (cat === 'RISK' ? 'badge-risk' : (cat === 'PR' ? 'badge-pr' : 'badge-gen'));
                    badgeEl.textContent = label;
                }}
                const resetBtn = li.querySelector('.manual-reset-btn');
                if (resetBtn) {{
                    resetBtn.style.display = isManual ? 'inline-block' : 'none';
                }}

                const kwMatch = (!qLow || rawTitle.toLowerCase().includes(qLow));
                if (kwMatch) {{
                    counts.ALL++;
                    counts[cat]++;
                }}

                const catMatch = (currentFilter === 'ALL' || currentFilter === cat);
                li.style.display = (catMatch && kwMatch) ? 'block' : 'none';
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

            const totalRP = (counts.RISK + counts.PR) || 1;
            const riskPct = (counts.RISK + counts.PR === 0) ? 0 : Math.round((counts.RISK / totalRP) * 100);
            const prPct = (counts.RISK + counts.PR === 0) ? 0 : (100 - riskPct);
            document.getElementById('newsRiskBar').style.width = riskPct + '%';
            document.getElementById('newsPrBar').style.width = prPct + '%';
            document.getElementById('ratioRiskText').textContent = `🚨 리스크 ${{riskPct}}% (${{counts.RISK}}건)`;
            document.getElementById('ratioPrText').textContent = `🎺 언플·물타기 ${{prPct}}% (${{counts.PR}}건)`;
        }}

        function copyAllPythonConfig() {{
            const mergedKw = JSON.parse(JSON.stringify(userNewsKw));
            Object.entries(learnedTokens).forEach(([tk, info]) => {{
                if ((info.cat === 'RISK' || info.cat === 'PR') && !mergedKw[info.cat].includes(tk)) {{
                    mergedKw[info.cat].unshift(tk);
                }}
            }});
            const pyCode = "NEWS_KEYWORDS = " + JSON.stringify(mergedKw, null, 4) +
                           "\\n\\nRADAR_KEYWORDS = " + JSON.stringify(userRadarKw, null, 4);
            navigator.clipboard.writeText(pyCode).then(() => {{
                alert("✅ 수동 분류로 학습된 단어를 포함한 NEWS_KEYWORDS 및 RADAR_KEYWORDS 파이썬 코드가 복사되었습니다!");
            }});
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
            document.getElementById('ytSearchBox').style.display = (group === 'SEARCH') ? 'block' : 'none';
            document.getElementById('ytOfficialBox').style.display = (group === 'OFFICIAL') ? 'block' : 'none';
        }}

        initAutoRefreshState();
        checkLastVisitStock();
        trackDcPostsAndDeletions();
        renderRadarTags();
        recomputeRadarKeywords();
        renderNewsTags();
        reclassifyAllNews();
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
    print("✅ theborn_dashboard.html V16 업데이트 완료!")
