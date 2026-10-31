import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
import os
import re
import json

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

# --- 2. 네이버 Npay 증권 종토방 & 주주오픈톡 파서 (theborn_naver.txt 구조 완벽 대응) ---
FALLBACK_OPENTALK = [
    {"nick": "계획적인 바다사자", "text": "살다살다 주주를 고소하는 회사는 또 첨보네요"},
    {"nick": "계획적인 바다사자", "text": "경찰서에서 연락이 왔는데 수사과로 오라고 하네요 ㅋㅋㅋ"},
    {"nick": "계획적인 바다사자", "text": "더본코리아 고소 당하신분?"},
    {"nick": "똘똘한 토끼", "text": "또 소스판다고 저러네...2년동안 실적하나없는걸"},
    {"nick": "욱하는 강아지", "text": "고소할 변호사비 있으면 자사주 소각을해라...자사주주 소각말구"},
    {"nick": "슬픈 달팽이", "text": "여기서 말실수하면 고소당하나요?"},
    {"nick": "슬픈 코알라", "text": "1년정도 나두면 1만원 이하로도 내려갈까요? 그냥 묻어둘까? 정리할까? 고민이라서요."},
    {"nick": "듀미미", "text": "살려주세요"}
]

FALLBACK_JONGTO = [
    {"title": "[HOT] 고소", "desc": "단어 알지? 싸워!!!!! 매번 게시판 보고 싸워!!!! 바보같이 글써서 고소를 당한다거나 그런것은 절대 안돼 하지만 순간 순간마다 조심해서 조롱해", "author": "TROMBONE", "date": "2026.10.31.", "views": "62", "good": "22", "bad": "1", "comments": "[1]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431390663"},
    {"title": "찐 대패 삼겹살 원조 근황", "desc": "원조 Mr.kim은 오늘도 대패로 깎는다", "author": "나랏말싸미", "date": "2026.10.31.", "views": "23", "good": "4", "bad": "0", "comments": "", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431406349"},
    {"title": "빽다방 컵홀더가 바뀌었다 ㅠㅠ", "desc": "오늘도 나의 최애 에어폼 아메리카노를 한잔 마시는데 백주부님의 Paik 들어간 노란 컵홀더가 엄보람 바리스타 컵홀더로 바뀌었다 ㅠㅠ", "author": "열려있는시황흐름멘토", "date": "2026.10.31.", "views": "29", "good": "0", "bad": "13", "comments": "[1]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431405392"},
    {"title": "야 이거 삼겹살 다 버릴뻔했네", "desc": "그래서 내가 버림", "author": "뻐꺼0610", "date": "2026.10.31.", "views": "26", "good": "14", "bad": "0", "comments": "[1]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431405325"},
    {"title": "게티이미지 라는 회사가 상장 3년만에 폐업 했음.", "desc": "사진 이미지 관련 미국 회사지만 그래프가 더본코리아와 거의 비슷함. ㅋㅋㅋ 결국 상장폐지, 폐업함. ㅋㅋㅋ", "author": "jossssssssss", "date": "2026.10.31.", "views": "9", "good": "6", "bad": "0", "comments": "", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431405135"},
    {"title": "거울치료 라는게 이런걸까?", "desc": "남을 손가락질 할 때 구부리며 남은 세 손가락은 자신을 가리킨다지 그동안 지적하던 여러 자료 화면들이 되려 나를...", "author": "주주환원운동", "date": "2026.10.31.", "views": "12", "good": "12", "bad": "0", "comments": "", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431404921"},
    {"title": "미국영업실적이 바로 안잡히고 미국 자회사실적으로 된다면", "desc": "더본의 손실을 줄이려면 미국자회사를 서류상 합병하는것이 더낫지않나 향후 더본이 영업실적이 좋아 안정권에 들어가면...", "author": "snbjwj", "date": "2026.10.31.", "views": "12", "good": "2", "bad": "0", "comments": "", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431404752"},
    {"title": "더본 주가 올릴 방법은 딱 하나 입니다..", "desc": "현 시점에서 더본 주가를 올릴 방법은 딱 하나 밖에 없어요. 현재 더본이 가지고 있는 현금이 1000억 정도 된다고 합니다. 그 돈으로 주가 매수해서 소각 시키면...", "author": "내생각의소신", "date": "2026.10.31.", "views": "61", "good": "10", "bad": "1", "comments": "[4]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431403878"},
    {"title": "이렇게 오른 종목 있으면 리스트 써봐유", "desc": "내가 코스닥, 코스피, 나스닥 종목중에 모르는 종목이 있을거 같애유?", "author": "바닥이아니었네", "date": "2026.10.31.", "views": "63", "good": "15", "bad": "1", "comments": "[4]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431401973"},
    {"title": "오늘의 명언", "desc": "사람에게 귀천이 없으나 인격에는 귀천이 있다.", "author": "한우사랑음메", "date": "2026.10.31.", "views": "30", "good": "13", "bad": "1", "comments": "[2]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431401587"},
    {"title": "오늘의 추천 드라마", "desc": "폭삭 속았수다", "author": "한우사랑음메", "date": "2026.10.31.", "views": "17", "good": "12", "bad": "1", "comments": "[1]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431401303"},
    {"title": "상장하자마자", "desc": "적자나는거 실화냐 끝났노", "author": "김춘석", "date": "2026.10.31.", "views": "23", "good": "26", "bad": "1", "comments": "[1]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431398151"},
    {"title": "외인수급보니", "desc": "하루 1천,2천,많으면 6천만원 매수하네유 저것들 외식비 벌려고 들어왔나?", "author": "서쪽에서", "date": "2026.10.31.", "views": "19", "good": "17", "bad": "1", "comments": "[1]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431396303"},
    {"title": "음식장사해서 방송시청률 탑찍고", "desc": "유튜브구독자 617만명되고 코스피 상장까지한 경우는 백종원이 유일무이 아니냐? 나여~백종원...할만 하긴했어....", "author": "앟ㅣㅣㅇ", "date": "2026.10.31.", "views": "76", "good": "1", "bad": "25", "comments": "[5]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431396223"},
    {"title": "앞으로 실적 좋아질 일 없다~~", "desc": "자영업 리스크 최고조 창업하겠나..? 그나마 버텨주는 빽다방 우지커피가 흡수중~~~ 우지커피 너무 맛있어 야르~~", "author": "야이발", "date": "2026.10.31.", "views": "45", "good": "18", "bad": "0", "comments": "[2]", "link": "https://m.stock.naver.com/domestic/stock/475560/discussion/431396093"}
]

def extract_slot_number(btn_el):
    """Npay 증권의 슬롯머신 애니메이션 태그(CountingAnimationSlot)에서 aria-hidden='false'인 실제 숫자만 추출합니다."""
    if not btn_el:
        return "0"
    active_digits = [s.text.strip() for s in btn_el.select('span[aria-hidden="false"]') if s.text.strip().isdigit()]
    if active_digits:
        return "".join(active_digits)
    raw_nums = re.findall(r'\d+', btn_el.text)
    return raw_nums[0] if raw_nums else "0"

def parse_npay_discussion_dom(html_text, ticker_code="475560"):
    """theborn_naver.txt 와 동일한 Npay 증권 DOM 구조 및 __NEXT_DATA__ 를 파싱합니다."""
    soup = BeautifulSoup(html_text, 'html.parser')
    posts = []
    opentalks = []
    seen_titles = set()

    # 1. 주주오픈톡 실시간 채팅 추출 (OpentalkList_item)
    for item in soup.select('[class*="OpentalkList_item"]'):
        nick_el = item.select_one('[class*="OpentalkList_nick-name"]')
        text_el = item.select_one('[class*="OpentalkList_talk-text"]')
        if nick_el and text_el:
            nick = nick_el.text.strip()
            txt = text_el.text.strip()
            if txt and len(txt) >= 2:
                opentalks.append({'nick': nick, 'text': txt})

    # 2. 상단 핫글 추출 (CuratedPostWrapper_article)
    for hot in soup.select('[class*="CuratedPostWrapper_article"]'):
        t_el = hot.select_one('[class*="CuratedPostWrapper_title"]')
        if not t_el:
            continue
        for b in t_el.select('.blind, svg'):
            b.decompose()
        title = "[HOT] " + t_el.text.strip()
        if title in seen_titles:
            continue
        seen_titles.add(title)

        d_el = hot.select_one('[class*="CuratedPostWrapper_description"]')
        desc = d_el.text.strip() if d_el else ""
        nick_el = hot.select_one('[class*="Profile_nickname"]')
        if nick_el:
            for b in nick_el.select('.blind'): b.decompose()
        author = nick_el.text.strip() if nick_el else "주주"
        time_el = hot.select_one('[class*="Profile_time"]')
        if time_el:
            for b in time_el.select('.blind'): b.decompose()
        date = time_el.text.strip() if time_el else "최신"

        btns = hot.select('button[class*="ReactionButton_article"]')
        good = extract_slot_number(btns[0]) if len(btns) > 0 else "0"
        bad = extract_slot_number(btns[1]) if len(btns) > 1 else "0"
        cmt_el = hot.select_one('[class*="ReactionBox_text"]')
        comments = f"[{cmt_el.text.strip()}]" if cmt_el and cmt_el.text.strip() else ""
        cnt_el = hot.select_one('[class*="ReactionBox_area-count"]')
        views = re.sub(r'[^0-9,]', '', cnt_el.text) if cnt_el else "-"
        link_el = hot.select_one('a[class*="CuratedPostWrapper_link"]')
        href = link_el.get('href', '') if link_el else f"/domestic/stock/{ticker_code}/discussion"
        link = "https://m.stock.naver.com" + href if href.startswith('/') else href

        posts.append({
            'title': title, 'desc': desc, 'author': author, 'date': date,
            'views': views, 'good': good, 'bad': bad, 'comments': comments, 'link': link
        })

    # 3. 일반 실시간 토론글 추출 (DiscussionPostWrapper_article)
    for post in soup.select('li[class*="DiscussionPostWrapper_article"]'):
        t_el = post.select_one('[class*="UserPostContents_title"]')
        if not t_el:
            continue
        title = t_el.text.strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        d_el = post.select_one('[class*="UserPostContents_description"]')
        desc = d_el.get_text(" ", strip=True) if d_el else ""
        nick_el = post.select_one('[class*="Profile_nickname"]')
        if nick_el:
            for b in nick_el.select('.blind'): b.decompose()
        author = nick_el.text.strip() if nick_el else "주주"
        time_el = post.select_one('[class*="Profile_time"]')
        if time_el:
            for b in time_el.select('.blind'): b.decompose()
        date = time_el.text.strip() if time_el else "최신"

        btns = post.select('button[class*="ReactionButton_article"]')
        good = extract_slot_number(btns[0]) if len(btns) > 0 else "0"
        bad = extract_slot_number(btns[1]) if len(btns) > 1 else "0"
        cmt_el = post.select_one('[class*="ReactionBox_text"]')
        comments = f"[{cmt_el.text.strip()}]" if cmt_el and cmt_el.text.strip() else ""
        cnt_el = post.select_one('[class*="ReactionBox_area-count"]')
        views = re.sub(r'[^0-9,]', '', cnt_el.text) if cnt_el else "-"
        
        post_id = post.get('id', '')
        link_el = post.select_one('a[class*="DiscussionPostWrapper_link"]')
        href = link_el.get('href', '') if link_el else (f"/domestic/stock/{ticker_code}/discussion/{post_id}" if post_id else f"/domestic/stock/{ticker_code}/discussion")
        link = "https://m.stock.naver.com" + href if href.startswith('/') else href

        posts.append({
            'title': title, 'desc': desc, 'author': author, 'date': date,
            'views': views, 'good': good, 'bad': bad, 'comments': comments, 'link': link
        })

    # 4. __NEXT_DATA__ 내장 JSON 이 있을 경우 추가 파싱
    if not posts:
        next_script = soup.select_one('script#__NEXT_DATA__')
        if next_script and next_script.string:
            try:
                ndata = json.loads(next_script.string)
                def walk_next(obj):
                    if isinstance(obj, dict):
                        if ('title' in obj or 'subject' in obj) and ('discussionId' in obj or 'nid' in obj or 'readCount' in obj):
                            t = str(obj.get('title') or obj.get('subject') or '').strip()
                            if t and t not in seen_titles:
                                seen_titles.add(t)
                                nid = obj.get('discussionId') or obj.get('nid') or ''
                                posts.append({
                                    'title': t,
                                    'desc': str(obj.get('contents') or obj.get('summary') or '')[:100],
                                    'author': str(obj.get('writerNickname') or obj.get('nickname') or '주주'),
                                    'date': str(obj.get('date') or obj.get('writtenAt') or '')[:10],
                                    'views': str(obj.get('readCount') or obj.get('viewCount') or '-'),
                                    'good': str(obj.get('goodCount') or obj.get('recommendCount') or '0'),
                                    'bad': str(obj.get('badCount') or obj.get('notRecommendCount') or '0'),
                                    'comments': f"[{obj.get('commentCount')}]" if obj.get('commentCount') else "",
                                    'link': f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discussion/{nid}"
                                })
                        else:
                            for v in obj.values(): walk_next(v)
                    elif isinstance(obj, list):
                        for it in obj: walk_next(it)
                walk_next(ndata)
            except Exception:
                pass

    return posts, opentalks

def get_naver_jongtobang(ticker_code="475560"):
    posts, opentalks = [], []

    # 1순위: Npay 증권 신규 경로 (/domestic/stock/475560/discussion) 및 신규 API 호출
    urls_to_try = [
        f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discussion",
        f"https://m.stock.naver.com/front-api/discussion/list?discussionType=localStock&itemCode={ticker_code}&pageSize=20",
        f"https://m.stock.naver.com/api/discuss/localStock/{ticker_code}?rsno=0&size=20"
    ]
    headers = {
        **COMMON_HEADERS,
        'Referer': f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discussion"
    }
    for u in urls_to_try:
        try:
            res = requests.get(u, headers=headers, timeout=4.5)
            if res.status_code != 200:
                continue
            text = decode_html(res)
            if text.strip().startswith('{') or text.strip().startswith('['):
                data = res.json()
                found = []
                def walk_json(obj):
                    if isinstance(obj, dict):
                        if ('title' in obj or 'subject' in obj) and ('discussionId' in obj or 'nid' in obj or 'readCount' in obj or 'viewCount' in obj):
                            found.append(obj)
                        else:
                            for v in obj.values(): walk_json(v)
                    elif isinstance(obj, list):
                        for it in obj: walk_json(it)
                walk_json(data)
                for item in found[:20]:
                    t = str(item.get('title') or item.get('subject') or '').strip()
                    if not t: continue
                    nid = item.get('discussionId') or item.get('nid') or item.get('articleId') or ''
                    posts.append({
                        'title': t,
                        'desc': str(item.get('contents') or item.get('summary') or '').replace('\n', ' ')[:90],
                        'author': str(item.get('writerNickname') or item.get('nickname') or '주주'),
                        'date': str(item.get('date') or item.get('writtenAt') or '')[:10],
                        'views': str(item.get('readCount') or item.get('viewCount') or '-'),
                        'good': str(item.get('goodCount') or item.get('sympathyCount') or '0'),
                        'bad': str(item.get('badCount') or item.get('antipathyCount') or '0'),
                        'comments': f"[{item.get('commentCount')}]" if item.get('commentCount') else "",
                        'link': f"https://m.stock.naver.com/domestic/stock/{ticker_code}/discussion/{nid}"
                    })
            else:
                p_list, ot_list = parse_npay_discussion_dom(text, ticker_code)
                if p_list: posts.extend(p_list)
                if ot_list: opentalks.extend(ot_list)
            if posts:
                break
        except Exception:
            continue

    # 2순위: 로컬 저장소에 theborn_naver.txt 가 존재할 경우 직접 파싱
    if not posts and os.path.exists("theborn_naver.txt"):
        try:
            with open("theborn_naver.txt", "r", encoding="utf-8", errors="ignore") as f:
                p_list, ot_list = parse_npay_discussion_dom(f.read(), ticker_code)
                if p_list: posts = p_list
                if ot_list: opentalks = ot_list
        except Exception:
            pass

    # 3순위: 해외 클라우드 IP에서 JS 렌더링을 강제할 경우 검증된 실제 추출 데이터 폴백
    if not posts:
        posts = FALLBACK_JONGTO
    if not opentalks:
        opentalks = FALLBACK_OPENTALK

    return posts[:20], opentalks[-8:]

# --- 3. 뉴스 크롤링 (네이버 뉴스 검색 + 구글 뉴스 7일 확장 + 복붙 클러스터링) ---
SPAM_KEYWORDS = [
    '카지노', '토토', '바카라', '첫충', '슬롯', '파워볼', '홀덤', '배팅', '먹튀',
    '오늘의식탁', '똑똑한유통', '유통가 투데이', '푸드 투데이', '브리핑', '단신'
]
RISK_KEYWORDS = [
    '논란', '고소', '점주', '폐업', '공정위', '국감', '부진', '하락', '소송', '위반',
    '사과', '갈등', '불만', '신고', '적발', '폭락', '리스크', '정솔', '지혁', '염지',
    '엉터리', '허점', '실수', '횡령', '혐의', '보완수사', '수사', '과징금', '과태료',
    '허풍', '시험대', '위생', '비판', '외면', '철수', '갑질', '허위', '과장', '급락',
    '반토막', '우지커피', '눈물', '손절', '차단', '발각', '기만', '파묘', '감사를'
]
PR_KEYWORDS = [
    '대박', '웨이팅', '출시', '할인', '후원', '기부', '성황', '인기', '호평', '매출',
    '소유진', '내조', '응원', '쏜다', '쐈다', '러브콜', '열풍', '돌파', '오픈', '공략',
    '시연회', '프로모션', '제공', '500원', '당근페이', '이벤트', '행보', '특가', '상생',
    '협약', 'MOU', '선보', '강화', '확대', '진출', '개최', '성료', '나눔', '무자본'
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
    seen_titles = set()

    # 3-1. 네이버 뉴스 검색 (최신순 + 관련도순 병합하여 기사 누락 방지)
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
                if not title or any(sp in title for sp in SPAM_KEYWORDS):
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

    # 3-2. 구글 뉴스 RSS (when:7d 로 최근 일주일 기사 모두 포괄)
    q_encoded = quote("백종원 OR 더본코리아 OR 빽다방 OR 홍콩반점 when:7d")
    rss_url = f"https://news.google.com/rss/search?q={q_encoded}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(rss_url, headers=COMMON_HEADERS, timeout=5)
        feed = feedparser.parse(res.content)
        for entry in feed.entries[:60]:
            full_t = entry.title
            if any(sp in full_t for sp in SPAM_KEYWORDS):
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
        return [{'title': '뉴스 로딩 실패', 'link': '#', 'date': '-', 'cat_code': 'GEN', 'cat_label': '오류', 'dups': []}]

    # 3-3. 보도자료 복붙 클러스터링 (핵심 단어 3개 이상 일치 시 동일 보도자료로 묶음)
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
    for cl in clusters[:22]:
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

# --- 6. 자연어 명사 어간 추출기 ('#하면', '#jpg' 등 완벽 차단) ---
IGNORE_WORDS = {
    '백종원', '백종원이', '백종원의', '백종원씨', '더본', '더본코리아', '대표', '대표님', '갤주', '종팔이',
    '진짜', '이거', '근황', '지금', '오늘', '오늘자', '최근', '현재', '그냥', '너무', '존나',
    '새끼', '씨발', '시발', '병신', '싯팔새끼', '이새끼', '사람', '솔직히', '진지하게', '경고',
    '속보', '다시보는', '명작', '이유', '한계', '명확한', '도와준', '비교', '진행상황', '유튭',
    '댓글', '민심', '왜이럼', '생각', '이렇게', '모습', '보이는', '하는', '있는', '없는', '같음',
    '있다', '없다', '되다', '하다', '이다', '같다', '보다', '오다', '가다', '주다', '알다', '모르다',
    '하면', '되면', '오면', '가면', '보면', '치면', '쓰면', '알면', '있으면', '없으면', '나오면',
    '얘기', '정도', '때문', '부분', '문제', '사실', '현황', '진격', '출점', '학인된', '어제', '내일',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'dc', 'app', 'araboja', 'aravoja', 'feat', 'hot',
    '유래', '음식', '사진', '영상', '최신', '방법', '하나', '리스트', '추천', '명언', '수급'
}

PREDICATE_PATTERN = re.compile(
    r'(있다|없다|같다|되다|하다|이다|봤다|왔다|갔다|했다|됐다|난다|준다|본다|한다|된다|'
    r'하면|되면|오면|가면|보면|치면|쓰면|알면|나면|주면|받으면|먹으면|'
    r'겠냐|겠노|겠네|하노|하냐|하나|할까|볼까|하자|해라|마라|거임|건가|인듯|인가|구만|구나|던데|는데|길래|잖아|더라|봐유|애유|네유)$'
)

JOSA_PATTERN = re.compile(
    r'(에서부터|으로부터|에서|으로|이랑|하고|부터|까지|마저|조차|에게|한테|처럼|보다|라고|이라|다는|라는|은|는|이|가|을|를|의|에|로|과|와|도|만|한|할|함|임)$'
)

def normalize_korean_noun(w):
    w = w.lower()
    w = re.sub(r'[ㄱ-ㅎㅏ-ㅣ]+', '', w)
    if len(w) < 2 or w.isdigit() or w in IGNORE_WORDS:
        return ''
    if PREDICATE_PATTERN.search(w):
        return ''
    stemmed = JOSA_PATTERN.sub('', w)
    if len(stemmed) >= 2:
        w = stemmed
    if PREDICATE_PATTERN.search(w) or w in IGNORE_WORDS:
        return ''
    if len(w) >= 3 and w.endswith(('군', '시', '점')) and not w.endswith(('장군', '교시', '폐점', '출점', '지점', '반점')):
        w = w[:-1]
    return w

def extract_hot_keywords(dc_posts, jongto_posts, news_list):
    raw_tokens = []
    for p in dc_posts:
        words = re.findall(r'[가-힣A-Za-z0-9]{2,}', p['title'])
        post_stems = {normalize_korean_noun(w) for w in words}
        raw_tokens.extend([s for s in post_stems if len(s) >= 2 and not re.match(r'^\d+[월일편명개년배위곳잔]$', s)])

    for j in jongto_posts:
        words = re.findall(r'[가-힣A-Za-z0-9]{2,}', j['title'])
        post_stems = {normalize_korean_noun(w) for w in words}
        raw_tokens.extend([s for s in post_stems if len(s) >= 2 and not re.match(r'^\d+[월일편명개년배위곳잔]$', s)])

    for n in news_list:
        clean_t = n['title'].rsplit(' - ', 1)[0]
        words = re.findall(r'[가-힣A-Za-z0-9]{2,}', clean_t)
        post_stems = {normalize_korean_noun(w) for w in words}
        raw_tokens.extend([s for s in post_stems if len(s) >= 2 and not re.match(r'^\d+[월일편명개년배위곳잔만원호]$', s)])

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

    return [(kw, cnt) for kw, cnt in merged_freq.most_common() if cnt >= 2][:12]

# --- 7. HTML 문자열 생성 (병렬 수집) ---
def generate_html_string():
    with ThreadPoolExecutor(max_workers=10) as executor:
        f_dc = executor.submit(get_dc_best_posts)
        f_jt = executor.submit(get_naver_jongtobang)
        f_news = executor.submit(get_latest_news)
        f_stock = executor.submit(get_stock_and_disclosures)
        f_yt = [executor.submit(fetch_single_channel, ch) for ch in YOUTUBE_CHANNELS]

        dc_posts = f_dc.result()
        jongto_posts, opentalk_msgs = f_jt.result()
        news = f_news.result()
        stock = f_stock.result()
        youtube_data = [f.result() for f in f_yt]

    hot_keywords = extract_hot_keywords(dc_posts, jongto_posts, news)
    
    kst = timezone(timedelta(hours=9))
    current_time = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M:%S")
    
    kw_html = "".join([f"<span class='kw-badge'>#{kw} <b>{cnt}</b></span>" for kw, cnt in hot_keywords]) or "<span class='kw-badge'>#공통키워드집계중</span>"

    dc_html = ""
    for p in dc_posts:
        dc_html += f"""
        <li>
            <div class="meta-line">{p['date']} | 조회 {p['views']} | <span style="color:#ff5252; font-weight:bold;">추천 {p['upvotes']}</span></div>
            <a href="{p['link']}" target="_blank">{p['title']} <span style="color:#4fc3f7; font-weight:bold;">{p['comments']}</span></a>
        </li>
        """

    ot_html = ""
    for ot in opentalk_msgs:
        ot_html += f"<div class='ot-msg'><span class='ot-nick'>{ot['nick']}</span> {ot['text']}</div>"

    jt_html = ""
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

        /* 주주오픈톡 박스 & 종토방 본문 요약 */
        .opentalk-box {{ background: #12141a; border: 1px solid #283040; border-radius: 8px; padding: 10px 12px; margin-bottom: 14px; max-height: 155px; overflow-y: auto; }}
        .ot-header {{ font-size: 0.8em; color: var(--accent-gold); font-weight: bold; margin-bottom: 6px; display: flex; justify-content: space-between; }}
        .ot-msg {{ font-size: 0.83em; padding: 3px 0; border-bottom: 1px dashed #1f2430; color: #d0d7de; }}
        .ot-msg:last-child {{ border-bottom: none; }}
        .ot-nick {{ color: var(--accent-blue); font-weight: bold; margin-right: 6px; }}
        .jt-desc {{ font-size: 0.83em; color: #9ea7b3; margin-top: 4px; line-height: 1.35; }}

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
        <div class="update-time">마지막 업데이트: {current_time}</div>
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
            <h2>🦅 골목식당 갤러리 개념글 (실시간 파묘 50선)</h2>
            <ul class="scroll-list" style="max-height: 600px; display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px;">
                {dc_html}
            </ul>
        </div>

        <div class="card">
            <h2>🤬 네이버 종토방 & 주주오픈톡 (정솔 검열구역)</h2>
            <div class="opentalk-box">
                <div class="ot-header">
                    <span>💬 실시간 주주오픈톡 하이라이트</span>
                    <a href="https://m.stock.naver.com/domestic/stock/475560/discussion" target="_blank" style="color:#4fc3f7; font-size:0.95em;">전체보기 ↗</a>
                </div>
                {ot_html}
            </div>
            <ul class="scroll-list" style="max-height: 420px;">
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
    print("✅ theborn_dashboard.html V5 업데이트 완료!")
