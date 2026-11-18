import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from urllib.parse import quote_plus
from database import (
    init_db, create_user, login_user, insert_survey_data, fetch_survey_data,
    start_learning, end_learning, get_menu_usage, fetch_learning_history,
)


# ---------------------------------------------------------
# 외부 웹사이트(게임)를 하나의 프레임 안에 꼭 맞게 보여주는 함수
#  - 바깥 컴포넌트 높이와 안쪽 iframe 높이를 동일하게 맞춰
#    이중 스크롤과 화면 잘림을 방지합니다.
# ---------------------------------------------------------
def embed_site(url: str, height: int = 760, title: str = "embedded") -> None:
    # 최신 Streamlit(st.iframe 지원): URL을 바로 지정한 높이의 iframe으로 표시
    if hasattr(st, "iframe"):
        st.iframe(url, height=height)
        return
    # 구버전 Streamlit: components.html 사용 (바깥/안쪽 높이를 동일하게 맞춤)
    components.html(
        f"""
        <style>
          html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden; }}
          iframe {{ display: block; width: 100%; height: 100%; border: 0; }}
        </style>
        <iframe src="{url}" title="{title}" allow="fullscreen; autoplay; gamepad" allowfullscreen></iframe>
        """,
        height=height,
        scrolling=False,
    )


def game_page(page_title: str, url: str, key: str) -> None:
    """게임 페이지 공통 레이아웃: 제목 + 높이 조절 + 새 창 열기 + 프레임"""
    head_col, ctrl_col = st.columns((3, 2))
    with head_col:
        st.title(page_title)
    with ctrl_col:
        frame_h = st.slider("화면 높이(px)", 500, 1200, 760, 20, key=f"{key}_height")
        st.link_button("🔗 새 창에서 크게 열기", url, width="stretch")
    embed_site(url, height=frame_h, title=page_title)
    st.caption("화면이 잘리면 위의 슬라이더로 높이를 조절하거나, 새 창에서 열어 보세요.")

# ---------------------------------------------------------
# 유튜브 시청 페이지 (AI학습 / 주식강좌)
#  - videos 에 영상 주소를 넣어 두면 페이지에 바로 표시됩니다.
#  - 화면에서 영상 주소를 붙여 넣어 시청할 수도 있습니다.
# ---------------------------------------------------------
YOUTUBE_LIBRARY = {
    "AI학습": {
        "title": "🤖 AI학습",
        "desc": "인공지능 · 머신러닝 · 생성형 AI 관련 영상을 시청합니다.",
        "videos": [],   # 예: "https://www.youtube.com/watch?v=영상ID"
        "topics": ["인공지능 기초 강의", "머신러닝 입문", "딥러닝 기초", "생성형 AI 활용법", "프롬프트 엔지니어링"],
    },
    "주식강좌": {
        "title": "📈 주식강좌",
        "desc": "주식 투자의 기초 개념을 영상으로 학습합니다. (학습용 자료이며 투자 권유가 아닙니다)",
        "videos": [],
        "topics": ["주식 기초 강의", "재무제표 읽는 법", "ETF 투자 기초", "주식 차트 보는 법", "경제 지표 이해"],
    },
}


def _is_youtube(url: str) -> bool:
    return any(h in url for h in ("youtube.com/", "youtu.be/"))


def youtube_page(key: str) -> None:
    info = YOUTUBE_LIBRARY[key]
    st.title(info["title"])
    st.caption(info["desc"])

    for v in info["videos"]:
        st.video(v)

    url = "https://www.youtube.com/watch?v=JYyoOyLbEdY"         

    # url = st.text_input("YouTube 영상 주소를 붙여 넣으면 여기서 바로 시청할 수 있습니다.",
    #                     key=f"yt_url_{key}", placeholder="https://www.youtube.com/watch?v=...")

    # url = "https://www.youtube.com/watch?v=MHShfgqrUWs"
    # with st.expander(f"{user['username']}님 여기는 content입니다", expanded=True):
    #             url = "https://www.youtube.com/watch?v=MHShfgqrUWs"
    #             st.write("content....")
    #             st.video(url)


    
    if url.strip():
        if _is_youtube(url.strip()):
            st.video(url.strip())
        else:
            st.warning("YouTube 영상 주소(youtube.com 또는 youtu.be)를 입력해 주세요.")
    elif not info["videos"]:
        st.info("아래 추천 검색어로 영상을 찾은 뒤, 주소를 복사해 위 입력칸에 붙여 넣어 보세요.")

    st.markdown("**추천 검색어 (YouTube에서 열기)**")
    with st.container(horizontal=True, gap="small"):
        for t in info["topics"]:
            st.link_button(f"🔎 {t}", "https://www.youtube.com/results?search_query=" + quote_plus(t))

# DB 초기화 및 테이블 생성 (learninghistory 테이블 포함)
init_db()

st.set_page_config(page_title="AI 교육 앱", layout="wide", initial_sidebar_state="collapsed")


# ---------------------------------------------------------
# 메뉴 정의
#  - menu_id : learninghistory.menu_id 에 저장되는 값 (기존 ID 유지 → 이전 이력도 그대로 집계)
#  - name    : 페이지 라우팅에 쓰는 내부 이름 (기존 기능 유지)
#  - label   : 메뉴에 보이는 이름
#  - group   : fixed(Home) / account(우측 상단 버튼) / G_*(상위 메뉴 아래의 하위 메뉴)
# ---------------------------------------------------------
MENUS = [
    {"id": "M01", "name": "Home",          "label": "Home",          "icon": "🏠", "group": "fixed"},
    {"id": "M02", "name": "Login",         "label": "Login",         "icon": "🔐", "group": "account"},
    {"id": "M03", "name": "SignUp",        "label": "SignUp",        "icon": "🧾", "group": "account"},
    # 게임
    {"id": "M06", "name": "블록리게임",     "label": "블록리 게임",    "icon": "🧩", "group": "G_GAME"},
    {"id": "M07", "name": "테트리스게임",   "label": "테트리스 게임",  "icon": "🕹️", "group": "G_GAME"},
    # 파이썬 학습
    {"id": "M05", "name": "pythonid",      "label": "pydroid",       "icon": "🐍", "group": "G_PY"},
    {"id": "M09", "name": "파이썬 강좌",    "label": "파이썬 강좌",    "icon": "📘", "group": "G_PY"},
    # 설문참여
    {"id": "M04", "name": "설문참여",       "label": "설문참여",       "icon": "📝", "group": "G_SURVEY"},
    # 유튜브 시청
    {"id": "M10", "name": "AI학습",        "label": "AI학습",        "icon": "🤖", "group": "G_YT"},
    {"id": "M11", "name": "주식강좌",       "label": "주식강좌",       "icon": "📈", "group": "G_YT"},
    # 메뉴에는 표시하지 않지만 기존 기능/이력 표시를 위해 유지 (G_GAME 으로 바꾸면 다시 보입니다)
    {"id": "M08", "name": "게임 함께보기",  "label": "게임 함께보기",  "icon": "🖥️", "group": "hidden"},
]
MENU_BY_NAME = {m["name"]: m for m in MENUS}
MENU_BY_ID = {m["id"]: m for m in MENUS}

# 상위 메뉴 (클릭하면 하위 메뉴가 펼쳐짐)
MENU_GROUPS = [
    {"key": "G_GAME",   "label": "게임",        "icon": "🎮"},
    {"key": "G_PY",     "label": "파이썬 학습",  "icon": "🐍"},
    {"key": "G_SURVEY", "label": "설문참여",     "icon": "📋"},
    {"key": "G_YT",     "label": "유튜브 시청",  "icon": "📺"},
]
GROUP_KEYS = [g["key"] for g in MENU_GROUPS]

# menu = ["Home", "Login", "SignUp", "설문참여",]
menu = [m["name"] for m in MENUS]   # 기존 변수 유지

# ---------------------------------------------------------
# 세션 상태 초기화 (로그인 관리 + 현재 메뉴 + 학습이력 + 햄버거 메뉴)
# ---------------------------------------------------------
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = ''
if 'current_menu' not in st.session_state:
    st.session_state['current_menu'] = "Home"
if 'history_id' not in st.session_state:
    st.session_state['history_id'] = None
if 'drawer_open' not in st.session_state:
    st.session_state['drawer_open'] = False
if 'menu_order' not in st.session_state:
    st.session_state['menu_order'] = None     # 로그인 시 learninghistory 기반으로 계산한 메뉴 순서
if 'open_group' not in st.session_state:
    st.session_state['open_group'] = None     # 현재 펼쳐진 상위 메뉴 (한 번에 하나만)
if 'flash' not in st.session_state:
    st.session_state['flash'] = None


def current_user() -> str:
    """학습이력에 기록할 사용자 ID (비로그인 시 guest)"""
    return st.session_state['user_id'] if st.session_state['logged_in'] else "guest"


def fmt_sec(sec: int) -> str:
    """초 → '1시간 2분 3초' 형식"""
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}시간 {m}분"
    if m:
        return f"{m}분 {s}초"
    return f"{s}초"


# 앱(세션) 최초 실행 시: 첫 화면(Home) 체류 기록 시작
if st.session_state['history_id'] is None:
    st.session_state['history_id'] = start_learning(
        current_user(), MENU_BY_NAME[st.session_state['current_menu']]["id"]
    )


# ---------------------------------------------------------
# 콜백 함수 (버튼 클릭 → 스크립트 재실행 전에 먼저 실행됨)
# ---------------------------------------------------------
def go_menu(name: str) -> None:
    """메뉴 클릭: 이전 메뉴 체류 기록 마감 → 새 메뉴 기록 시작 → 메뉴 닫기"""
    if name != st.session_state['current_menu']:
        end_learning(st.session_state['history_id'])
        st.session_state['current_menu'] = name
        st.session_state['history_id'] = start_learning(current_user(), MENU_BY_NAME[name]["id"])
    # 선택한 하위 메뉴가 속한 상위 메뉴를 펼친 상태로 기억 (다음에 메뉴를 열면 바로 보이도록)
    group = MENU_BY_NAME[name]["group"]
    st.session_state['open_group'] = group if group in GROUP_KEYS else None
    st.session_state['drawer_open'] = False


def toggle_drawer() -> None:
    st.session_state['drawer_open'] = not st.session_state['drawer_open']


def close_drawer() -> None:
    st.session_state['drawer_open'] = False


def do_logout() -> None:
    """로그아웃: 현재 체류 기록 마감 → 비로그인(guest) 상태로 Home 기록 시작"""
    end_learning(st.session_state['history_id'])
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = ''
    st.session_state['menu_order'] = None   # 다음 로그인 때 다시 계산
    st.session_state['current_menu'] = "Home"
    st.session_state['open_group'] = None
    st.session_state['history_id'] = start_learning("guest", MENU_BY_NAME["Home"]["id"])
    st.session_state['drawer_open'] = False
    st.session_state['flash'] = ("info", "로그아웃되었습니다. 다시 로그인하면 학습 이력에 따라 메뉴가 재배치됩니다.")



def toggle_group(group_key: str) -> None:
    """상위 메뉴 클릭: 같은 메뉴면 접고, 다른 메뉴면 그것만 펼침(기존 메뉴는 자동으로 닫힘)"""
    st.session_state['open_group'] = None if st.session_state['open_group'] == group_key else group_key


def compute_menu_order(userid: str) -> dict:
    """
    learninghistory 참조 메뉴 순서 계산 (로그인할 때 한 번 호출)
      - 하위 메뉴: 누적 체류시간 → 클릭 수 내림차순 (이력 없으면 기본 순서)
      - 상위 메뉴: 하위 메뉴 체류시간 합계 → 클릭 수 합계 내림차순
    반환: {"groups": [상위키...], "children": {상위키: [menu_id...]}}
    """
    usage = get_menu_usage(userid)

    def u(mid):
        return usage.get(mid, (0, 0))

    rows, children_order = [], {}
    for gi, g in enumerate(MENU_GROUPS):
        children = [m["id"] for m in MENUS if m["group"] == g["key"]]
        default_pos = {mid: i for i, mid in enumerate(children)}
        children.sort(key=lambda mid: (-u(mid)[0], -u(mid)[1], default_pos[mid]))
        children_order[g["key"]] = children
        total = sum(u(mid)[0] for mid in children)
        cnt = sum(u(mid)[1] for mid in children)
        rows.append((g["key"], total, cnt, gi))
    rows.sort(key=lambda r: (-r[1], -r[2], r[3]))
    return {"groups": [r[0] for r in rows], "children": children_order}


def group_totals(usage: dict) -> dict:
    """상위 메뉴별 총 체류시간(초) = 하위 메뉴 체류시간 합계"""
    return {
        g["key"]: sum(usage.get(m["id"], (0, 0))[0] for m in MENUS if m["group"] == g["key"])
        for g in MENU_GROUPS
    }


def ordered_menus():
    """
    메뉴 표시용 데이터
      - 순서: 로그인할 때 계산해 둔 st.session_state['menu_order'] 사용
              (로그인 중에는 순서가 바뀌지 않고, logoff → login 할 때 다시 계산)
      - 체류시간: 표시용으로 매번 최신 값을 조회
    반환: (fixed 메뉴 목록, [(상위메뉴, [하위메뉴...]), ...], usage, 상위메뉴 총 체류시간)
    """
    fixed = [m for m in MENUS if m["group"] == "fixed"]
    usage = get_menu_usage(st.session_state['user_id']) if st.session_state['logged_in'] else {}

    order = st.session_state.get('menu_order')
    group_by_key = {g["key"]: g for g in MENU_GROUPS}
    if order:
        groups = [(group_by_key[k], [MENU_BY_ID[mid] for mid in order["children"][k]])
                  for k in order["groups"]]
    else:   # 비로그인: 기본 순서
        groups = [(g, [m for m in MENUS if m["group"] == g["key"]]) for g in MENU_GROUPS]
    return fixed, groups, usage, group_totals(usage)

# ---------------------------------------------------------
# 햄버거 메뉴 + 좌측 슬라이드 메뉴(drawer) 스타일
#  - drawer는 항상 같은 위치에 렌더링되고, transform 값만 바뀌므로
#    열릴 때/닫힐 때 왼쪽에서 부드럽게 슬라이드됩니다.
# ---------------------------------------------------------
BASE_CSS = """
<style>
  /* 게임 화면이 한 프레임 안에 잘 보이도록 기본 여백 축소 (햄버거 버튼 자리만 확보) */
  .block-container{padding-top:3.6rem; padding-bottom:1rem;}

  /* 기본 사이드바는 사용하지 않음 (햄버거 메뉴로 대체) */
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
  [data-testid="stExpandSidebarButton"] {display:none !important;}

  /* ☰ 햄버거 버튼 (좌측 상단 고정) */
  .st-key-hamburger {position:fixed; top:.6rem; left:.9rem; z-index:999995; width:auto !important;}
  .st-key-hamburger button {
      width:46px; height:46px; min-height:46px; padding:0; border-radius:14px;
      font-size:1.45rem; line-height:1; background:#ffffff; border:1px solid #e2e8f0;
      box-shadow:0 6px 18px rgba(15,23,42,.10); transition:transform .15s ease, box-shadow .15s ease;
  }
  .st-key-hamburger button p {font-size:1.45rem; line-height:1; margin:0;}
  .st-key-hamburger button:hover {transform:scale(1.06); box-shadow:0 10px 24px rgba(79,70,229,.22); border-color:#c7d2fe;}


  /* 우측 상단 계정 버튼 (Login / SignUp / 로그아웃) */
  [data-testid="stAppDeployButton"] {display:none !important;}
  .st-key-authbar {position:fixed !important; top:.6rem; right:3.4rem; z-index:999995;
      width:auto !important; flex-wrap:nowrap; gap:.5rem; align-items:center;}
  .st-key-authbar [data-testid="stElementContainer"] {width:auto !important; align-self:center;}
  .st-key-authbar button {min-height:40px; padding:0 .95rem; border-radius:12px; white-space:nowrap;
      box-shadow:0 6px 18px rgba(15,23,42,.08);}
  .st-key-authbar button p {font-weight:700;}
  .st-key-authbar .auth-user {display:inline-block; padding:.45rem .8rem; border-radius:999px;
      background:#eef2ff; color:#3730a3; font-weight:700; font-size:.9rem; white-space:nowrap;}
  .st-key-authbar [data-testid="stMarkdown"], .st-key-authbar [data-testid="stMarkdownContainer"],
  .st-key-authbar [data-testid="stMarkdownContainer"] p {margin:0 !important; line-height:1;}
  @media (max-width: 640px) {
      .st-key-authbar {right:3rem;}
      .st-key-authbar button {padding:0 .6rem; font-size:.85rem;}
      .st-key-authbar .auth-user {display:none;}
  }

  /* ---------- 상위/하위 메뉴 (아코디언) ---------- */
  [class*="st-key-acc_"] {gap:0 !important;}
  [class*="st-key-grpbtn_"] button {font-weight:700;}
  [class*="st-key-grpbtn_"] button > div {width:auto !important;}
  [class*="st-key-grpbtn_"] button::after {
      content:"▼"; margin-left:auto; padding-left:.5rem; font-size:.72rem; color:#64748b;
      transition:transform .35s ease, color .2s ease;
  }
  /* 하위 메뉴 영역: 접힌 상태 (max-height / opacity 전환으로 부드럽게 펼침·접힘) */
  [class*="st-key-sub_"] {
      max-height:0; opacity:0; overflow:hidden; visibility:hidden;
      margin-left:.85rem; width:calc(100% - .85rem) !important; box-sizing:border-box;
      padding:0 0 0 .7rem; border-left:2px solid #e0e7ff; gap:.3rem;
      transition:max-height .4s ease, opacity .3s ease, padding .4s ease, visibility 0s linear .4s;
  }
  [class*="st-key-sub_"] button {min-height:36px; font-size:.92rem;}
  /* 현재 선택된 하위 메뉴 강조 */
  .st-key-drawer button[kind="primary"] {
      background:#eef2ff !important; color:#4338ca !important; border:1px solid #6366f1 !important;
      font-weight:800; box-shadow:inset 3px 0 0 #6366f1;
  }
  .st-key-drawer button[kind="primary"] p {color:#4338ca !important; font-weight:800;}
  .st-key-authbar button[kind="primary"] {background:#4f46e5 !important; border-color:#4f46e5 !important;}
  .st-key-authbar button[kind="primary"] p {color:#fff !important;}

  /* 반투명 배경(클릭하면 메뉴 닫힘) */
  .st-key-backdrop {
      position:fixed !important; inset:0; width:100vw !important; height:100vh;
      z-index:1000001; opacity:0; pointer-events:none; transition:opacity .35s ease;
  }
  .st-key-backdrop button {
      position:fixed; inset:0; width:100vw; height:100vh; border:0; border-radius:0;
      background:rgba(15,23,42,.42); color:transparent !important; cursor:default;
  }
  .st-key-backdrop button:hover, .st-key-backdrop button:focus {background:rgba(15,23,42,.42); color:transparent !important;}

  /* 좌측 슬라이드 메뉴(drawer) */
  .st-key-drawer {
      position:fixed !important; top:0; left:0; bottom:0;
      width:300px !important; max-width:86vw; height:100vh; overflow-y:auto;
      padding:1.1rem 1rem 1.5rem; gap:.4rem;
      background:#ffffff; border-right:1px solid #e2e8f0;
      box-shadow:none;
      z-index:1000002;
      transform:translateX(-110%);
      transition:transform .42s cubic-bezier(.22,1,.36,1);
  }
  .st-key-drawer button {justify-content:flex-start; text-align:left; border-radius:12px; min-height:42px;}
  .st-key-drawer button > div {justify-content:flex-start; width:100%;}
  .st-key-drawer button p {text-align:left;}
  .st-key-drawer .drawer-title {font-size:1.25rem; font-weight:800; color:#0f172a; margin:0;}
  .st-key-drawer .drawer-section {font-size:.74rem; font-weight:800; letter-spacing:.08em;
      color:#6366f1; text-transform:uppercase; margin:.6rem 0 1.05rem;}
  .st-key-drawer_close button, .st-key-drawer_close button > div {justify-content:center;}

  /* 햄버거/배경/메뉴는 모두 fixed 이므로 본문 흐름에서 공간을 차지하지 않도록 */
  .st-key-navroot {height:0; min-height:0; margin-bottom:-1rem; gap:0;}
</style>
"""
OPEN_CSS = """
<style>
  .st-key-drawer {transform:translateX(0); box-shadow:12px 0 40px rgba(15,23,42,.18);}
  .st-key-backdrop {opacity:1; pointer-events:auto;}
</style>
"""



def state_css(groups) -> str:
    """현재 상태(펼친 상위 메뉴, 선택 메뉴)에 따라 바뀌는 CSS"""
    rules = []
    og = st.session_state['open_group']
    if og:
        rules.append(f"""
  .st-key-sub_{og} {{max-height:600px; opacity:1; visibility:visible; padding:.35rem 0 .3rem .7rem;
      transition:max-height .45s ease, opacity .35s ease .05s, padding .45s ease, visibility 0s;}}
  .st-key-grpbtn_{og} button::after {{transform:rotate(180deg); color:#4f46e5;}}""")
    cur_group = MENU_BY_NAME[st.session_state['current_menu']]["group"]
    if cur_group in GROUP_KEYS:
        # 현재 페이지가 속한 상위 메뉴도 글자색으로 강조
        rules.append(f"""
  .st-key-grpbtn_{cur_group} button {{color:#4338ca; border-color:#c7d2fe; background:#f5f7ff;}}
  .st-key-grpbtn_{cur_group} button p {{color:#4338ca;}}""")
    return "<style>" + "".join(rules) + "\n</style>" if rules else ""


def render_auth_bar() -> None:
    """우측 상단 고정 계정 버튼 (클릭 시 learninghistory 기록은 기존 메뉴 클릭과 동일)"""
    current = st.session_state['current_menu']
    with st.container(key="authbar", horizontal=True, vertical_alignment="center", gap="small"):
        if st.session_state['logged_in']:
            st.markdown(f'<span class="auth-user">👤 {st.session_state["user_id"]}</span>',
                        unsafe_allow_html=True)
            st.button("🚪 로그아웃", key="auth_logout", on_click=do_logout)
        else:
            for m in MENUS:
                if m["group"] != "account":
                    continue
                st.button(
                    f"{m['icon']} {m['label']}",
                    key=f"auth_{m['id']}",
                    on_click=go_menu,
                    args=(m["name"],),
                    type="primary" if m["name"] == current else "secondary",
                )


def render_hamburger_menu() -> None:
    with st.container(key="navroot"):
        _render_hamburger_menu_inner()


def _render_hamburger_menu_inner() -> None:
    fixed, groups, usage, gtotals = ordered_menus()
    # 로그인 직후: 가장 많이 이용한 상위 메뉴를 펼쳐서 보여줌
    if st.session_state['open_group'] == "__TOP__":
        st.session_state['open_group'] = groups[0][0]["key"] if groups else None

    st.markdown(
        BASE_CSS + (OPEN_CSS if st.session_state['drawer_open'] else "") + state_css(groups),
        unsafe_allow_html=True,
    )

    with st.container(key="hamburger"):
        st.button("☰", key="btn_hamburger", on_click=toggle_drawer, help="메뉴 열기/닫기")

    # 우측 상단 Login / SignUp (로그인 시 사용자 + 로그아웃)
    render_auth_bar()

    with st.container(key="backdrop"):
        st.button("메뉴 닫기", key="btn_backdrop", on_click=close_drawer)

    current = st.session_state['current_menu']

    with st.container(key="drawer"):
        t_col, c_col = st.columns((5, 1), vertical_alignment="center")
        with t_col:
            st.markdown('<p class="drawer-title">📚 AI 교육 앱</p>', unsafe_allow_html=True)
        with c_col:
            with st.container(key="drawer_close"):
                st.button("✕", key="btn_drawer_close", on_click=close_drawer, help="메뉴 닫기")

        if st.session_state['logged_in']:
            st.success(f"👤 {st.session_state['user_id']}님 로그인 중")
        else:
            st.caption("로그인하면 학습 이력에 따라 메뉴가 재배치됩니다. Login · SignUp은 오른쪽 위에 있습니다.")

        def menu_button(m, show_time=False):
            label = f"{m['icon']}  {m['label']}"
            if show_time and m["id"] in usage:
                label += f"  ·  {fmt_sec(usage[m['id']][0])}"
            st.button(
                label,
                key=f"nav_{m['id']}",
                on_click=go_menu,
                args=(m["name"],),
                type="primary" if m["name"] == current else "secondary",
                width="stretch",
            )

        st.markdown('<div class="drawer-section">Home</div>', unsafe_allow_html=True)
        for m in fixed:
            menu_button(m)

        section = "학습 메뉴 · 로그인 시 이용시간 순 정렬" if st.session_state['logged_in'] else "학습 메뉴"
        st.markdown(f'<div class="drawer-section">{section}</div>', unsafe_allow_html=True)

        # 상위 메뉴(▼/▲) + 하위 메뉴
        #  하위 메뉴는 항상 렌더링하고 CSS로만 접고 펼치므로 애니메이션이 자연스럽게 적용됩니다.
        for g, children in groups:
            with st.container(key=f"acc_{g['key']}"):
                grp_label = f"{g['icon']}  {g['label']}"
                if usage and gtotals.get(g["key"], 0) > 0:
                    grp_label += f"  ·  총 {fmt_sec(gtotals[g['key']])}"   # 하위 메뉴 체류시간 합계
                st.button(
                    grp_label,
                    key=f"grpbtn_{g['key']}",
                    on_click=toggle_group,
                    args=(g["key"],),
                    width="stretch",
                    help="클릭하면 하위 메뉴가 펼쳐집니다",
                )
                with st.container(key=f"sub_{g['key']}"):
                    for m in children:
                        menu_button(m, show_time=bool(usage))


render_hamburger_menu()
choice = st.session_state['current_menu']

# 로그인/로그아웃 직후 메시지 1회 표시
if st.session_state['flash']:
    kind, msg = st.session_state['flash']
    getattr(st, kind)(msg)
    st.session_state['flash'] = None

if choice == "Home":
    st.title("홈 화면")
    st.write("환영합니다. AI 교육적 효과 인식 설문 앱입니다.")
    st.caption("왼쪽 위 ☰ 버튼으로 메뉴를 열고, 오른쪽 위 버튼으로 로그인 · 회원가입할 수 있습니다.")
    if st.session_state['logged_in']:
        st.success(f"{st.session_state['user_id']}님, 로그인 상태입니다.")

        # 나의 학습 이력 (learninghistory 참조)
        st.subheader("📈 나의 학습 이력")
        usage = get_menu_usage(st.session_state['user_id'])
        if usage:
            usage_df = pd.DataFrame(
                [
                    {
                        "menu_id": mid,
                        "메뉴": f"{MENU_BY_ID[mid]['icon']} {MENU_BY_ID[mid]['label']}" if mid in MENU_BY_ID else mid,
                        "누적 체류시간(초)": total,
                        "누적 체류시간": fmt_sec(total),
                        "클릭 수": cnt,
                    }
                    for mid, (total, cnt) in usage.items()
                ]
            ).sort_values(["누적 체류시간(초)", "클릭 수"], ascending=False)
            # 상위 메뉴별 총 체류시간 (하위 메뉴 합산)
            gt = group_totals(usage)
            group_df = pd.DataFrame(
                [
                    {
                        "상위 메뉴": f"{g['icon']} {g['label']}",
                        "하위 메뉴": ", ".join(m["label"] for m in MENUS if m["group"] == g["key"]),
                        "총 체류시간(초)": gt[g["key"]],
                        "총 체류시간": fmt_sec(gt[g["key"]]),
                    }
                    for g in MENU_GROUPS
                ]
            ).sort_values("총 체류시간(초)", ascending=False)
            st.markdown("**상위 메뉴별 총 체류시간** (하위 메뉴 합산)")
            g_col1, g_col2 = st.columns((3, 2))
            with g_col1:
                st.dataframe(group_df, width="stretch", hide_index=True)
            with g_col2:
                st.bar_chart(group_df.set_index("상위 메뉴")["총 체류시간(초)"])

            st.markdown("**하위 메뉴별 체류시간**")
            st.dataframe(usage_df, width="stretch", hide_index=True)
            st.bar_chart(usage_df.set_index("메뉴")["누적 체류시간(초)"])
        else:
            st.info("아직 마감된 학습 이력이 없습니다. 메뉴를 이동하면 체류 시간이 기록됩니다.")

        with st.expander("최근 learninghistory 기록 보기"):
            st.dataframe(fetch_learning_history(st.session_state['user_id']),
                         width="stretch", hide_index=True)

elif choice == "SignUp":
    st.title("회원가입")
    with st.form("signup_form"):
        new_user = st.text_input("ID")
        new_name = st.text_input("Name")
        new_password = st.text_input("Password", type='password')
        new_email = st.text_input("Email")
        submit = st.form_submit_button("가입하기")
        
        if submit:
            if create_user(new_user, new_name, new_password, new_email):
                st.success("계정이 성공적으로 생성되었습니다. 오른쪽 위 Login 버튼을 눌러 로그인해 주세요.")
            else:
                st.error("오류: 이미 존재하는 ID이거나 이메일입니다.")

elif choice == "Login":
    st.title("로그인")
    if st.session_state['logged_in']:
        st.success(f"{st.session_state['user_id']}님, 이미 로그인 상태입니다.")
        st.button("🚪 로그아웃", key="btn_logout_page", on_click=do_logout)
    else:
        with st.form("login_form"):
            userid = st.text_input("ID")
            password = st.text_input("Password", type='password')
            submit = st.form_submit_button("로그인")
            
            if submit:
                result = login_user(userid, password)
                if result:
                    # 비로그인(guest) 상태로 머문 Login 화면 기록 마감
                    end_learning(st.session_state['history_id'])
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = result[0][1]   # DB에 저장된 원래 ID(대소문자 통일)
                    # 로그인 사용자로 현재 메뉴 체류 기록 새로 시작
                    st.session_state['history_id'] = start_learning(
                        st.session_state['user_id'], MENU_BY_NAME["Login"]["id"]
                    )
                    # 학습 이력 기반으로 재배치된 메뉴를 바로 보여줌
                    st.session_state['drawer_open'] = True
                    st.session_state['open_group'] = "__TOP__"   # 가장 많이 이용한 상위 메뉴 펼치기
                    # ★ logoff → login 시 learninghistory 기반 메뉴 재배치
                    st.session_state['menu_order'] = compute_menu_order(st.session_state['user_id'])
                    st.session_state['flash'] = ("success", f"{st.session_state['user_id']}님 환영합니다. 학습 이력에 따라 메뉴가 재배치되었습니다.")
                    st.rerun()
                else:
                    st.error("ID 또는 비밀번호가 틀렸습니다.")

elif choice == "pythonid":
    game_page("🐍 pydroid (온라인 파이썬 실습)", "https://www.online-python.com/", "python")

elif choice == "파이썬 강좌":
    game_page("📘 파이썬 강좌", "https://docs.python.org/ko/3/tutorial/index.html", "pylecture")
    st.markdown("**함께 보면 좋은 강좌**")
    with st.container(horizontal=True, gap="small"):
        st.link_button("📗 점프 투 파이썬 (위키독스)", "https://wikidocs.net/book/1")
        st.link_button("▶️ YouTube 파이썬 기초 강의",
                       "https://www.youtube.com/results?search_query=" + quote_plus("파이썬 기초 강의"))

elif choice == "AI학습":
    youtube_page("AI학습")

elif choice == "주식강좌":
    youtube_page("주식강좌")

elif choice == "블록리게임":
    game_page("🧩 블록리게임", "https://blockly.games/?lang=ko", "blockly")

elif choice == "테트리스게임":
    game_page("🎮 테트리스게임", "https://play.tetris.com/", "tetris")

elif choice == "게임 함께보기":
    st.title("🧩🎮 블록리 + 테트리스 함께보기")
    frame_h = st.slider("화면 높이(px)", 500, 1200, 720, 20, key="both_height")
    left, right = st.columns(2)
    with left:
        st.markdown("**🧩 블록리게임**")
        embed_site("https://blockly.games/?lang=ko", height=frame_h, title="블록리게임")
    with right:
        st.markdown("**🎮 테트리스게임**")
        embed_site("https://play.tetris.com/", height=frame_h, title="테트리스게임")

elif choice == "설문참여":
    st.title("📝 AI의 교육적 효과에 대한 인식 설문조사")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["📋 설문응시", "📊 설문결과 시각화"])
    
    # 설문 문항 및 척도 정의
    questions = [
        "1. AI는 학습자의 학업 성취도를 향상시키는 데 도움이 된다.",
        "2. AI는 개별 학습자의 수준에 맞춘 맞춤형 학습을 제공하는 데 효과적이다.",
        "3. AI를 활용한 교육은 학습자의 흥미와 참여도를 높인다.",
        "4. AI는 교사의 업무 부담을 줄이고 교육의 질을 높이는 데 기여한다.",
        "5. AI 기반 평가 시스템은 공정하고 객관적인 결과를 제공한다.",
        "6. AI 교육 도구는 자기주도적 학습 능력을 기르는 데 유용하다.",
        "7. 교육 현장에서 AI를 도입하는 것은 필수적인 흐름이다.",
        "8. AI는 복잡한 개념이나 원리를 이해하는 데 도움을 준다.",
        "9. AI 활용 교육은 창의력과 문제해결능력 향상에 긍정적인 영향을 미친다.",
        "10. 전반적으로 AI 기술은 미래 교육 발전에 핵심적인 역할을 할 것이다."
    ]
    options = ["1 (전혀 아니다)", "2 (아니다)", "3 (보통이다)", "4 (그렇다)", "5 (매우 그렇다)"]
    
    # ---------------------------
    # 탭 1: 설문응시
    # ---------------------------
    with tab1:
        st.subheader("설문에 참여해 주세요.")
        with st.form("survey_form"):
            # 로그인 되어있는 경우 ID 자동 입력
            if st.session_state['logged_in']:
                user_id = st.text_input("사용자 ID", value=st.session_state['user_id'], disabled=True)
            else:
                user_id = st.text_input("사용자 ID를 입력하세요 (비회원 가능)", max_chars=20)
            
            responses = []
            for q in questions:
                ans = st.radio(q, options, horizontal=True)
                responses.append(int(ans[0]))
                
            submit_button = st.form_submit_button(label="설문 제출")
            
            if submit_button:
                if user_id.strip() == "":
                    st.error("사용자 ID를 입력해 주세요!")
                else:
                    # DB 저장
                    insert_survey_data(
                        user_id, 
                        responses[0], responses[1], responses[2], responses[3], responses[4],
                        responses[5], responses[6], responses[7], responses[8], responses[9]
                    )
                    st.success(f"{user_id}님, 설문이 성공적으로 제출되었습니다. 감사합니다!")

    # ---------------------------
    # 탭 2: 설문결과 시각화
    # ---------------------------
    with tab2:
        st.subheader("설문 결과 통계 및 시각화")
        
        df = fetch_survey_data()
        
        if df.empty:
            st.info("아직 제출된 설문 데이터가 없습니다.")
        else:
            st.write(f"**총 응답자 수:** {len(df)}명")
            st.divider()
            
            for i, q in enumerate(questions):
                col_name = f'q{i+1}'
                
                st.markdown(f"**{q}**")
                
                avg_score = df[col_name].mean()
                
                counts = df[col_name].value_counts().reindex([1, 2, 3, 4, 5], fill_value=0)
                counts.index = ["1점", "2점", "3점", "4점", "5점"]
                
                st.bar_chart(counts)
                
                st.caption(f"이 문항의 평균 점수: **{avg_score:.2f} / 5.0**")
                st.divider()
