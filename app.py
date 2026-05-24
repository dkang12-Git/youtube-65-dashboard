"""
유튜브 65편 프로젝트 대시보드
Streamlit Cloud 및 로컬 양쪽 지원
"""

import streamlit as st
import json
import re
from pathlib import Path

# ── 페이지 설정 ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="유튜브 65편 프로젝트",
    page_icon="🎬",
    layout="wide",
)

st.markdown("""
<style>
.metric-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
    border: 1px solid #e9ecef;
}
.status-chip {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}
.s-wait   { background:#f0f0f0; color:#555; }
.s-res    { background:#fff3cd; color:#856404; }
.s-draft  { background:#cce5ff; color:#004085; }
.s-final  { background:#d4edda; color:#155724; }
.price-row { border-left: 4px solid #0d6efd; padding: 8px 12px;
             background:#f8f9fa; border-radius:0 6px 6px 0; margin:4px 0; }
.diff-red  { color: #dc3545; font-weight: bold; }
.diff-ora  { color: #fd7e14; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# ── 인증: 로컬파일 or Streamlit Secrets ──────────────────────────────────

def get_gspread_client():
    import gspread
    from google.oauth2.service_account import Credentials

    SCOPES = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    # Streamlit Cloud: st.secrets 사용
    if "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        # 로컬: 파일 사용
        cred_path = Path.home() / "Documents" / "credentials" / "service-account.json"
        if not cred_path.exists():
            st.error(f"서비스 계정 파일 없음: {cred_path}")
            st.stop()
        creds = Credentials.from_service_account_file(str(cred_path), scopes=SCOPES)

    return gspread.authorize(creds)


# ── 데이터 로드 ────────────────────────────────────────────────────────────

SPREADSHEET_ID = "1vmpx1zvVKaRO2JZleVoXJIxiHM9JDm_TOxDXrJrAOPs"

@st.cache_data(ttl=60)
def load_topics():
    try:
        gc = get_gspread_client()
        ws = gc.open_by_key(SPREADSHEET_ID).sheet1
        return ws.get_all_records()
    except Exception as e:
        st.warning(f"Sheets 연결 실패: {e}")
        return []


@st.cache_data(ttl=300)
def load_price_db():
    # 로컬 실행 시 / 배포 시 data/ 폴더 모두 탐색
    candidates = [
        Path(__file__).parent / "data" / "price_db.json",
        Path("data/price_db.json"),
    ]
    for p in candidates:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return None


def norm(s): return re.sub(r"[\s\-_]", "", str(s)).upper()


# ── 탭 ────────────────────────────────────────────────────────────────────
st.title("🎬 유튜브 65편 프로젝트")

tab1, tab2, tab3 = st.tabs(["📋 에피소드 현황", "💰 가격 검색", "📊 브랜드별 비교"])

STATUS_ICON  = {"대기": "🔘", "리서치완료": "🟡", "초안완료": "🔵", "최종완료": "🟢"}
STATUS_CLASS = {"대기": "s-wait", "리서치완료": "s-res", "초안완료": "s-draft", "최종완료": "s-final"}


# ══════════════════════════════════════════════════════════════════════════
# TAB 1 : 에피소드 현황
# ══════════════════════════════════════════════════════════════════════════
with tab1:
    col_btn, _ = st.columns([1, 6])
    with col_btn:
        if st.button("🔄 새로고침"):
            st.cache_data.clear()
            st.rerun()

    topics = load_topics()

    if not topics:
        st.info("데이터 없음 (Sheets 연결 확인)")
    else:
        total = len(topics)
        done  = sum(1 for t in topics if t.get("상태") == "최종완료")
        draft = sum(1 for t in topics if t.get("상태") == "초안완료")
        wait  = sum(1 for t in topics if t.get("상태") == "대기")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("전체", f"{total}편")
        c2.metric("최종완료", f"{done}편", f"{done/total*100:.0f}%")
        c3.metric("초안완료", f"{draft}편")
        c4.metric("대기 중",  f"{wait}편")
        st.progress(done / total if total else 0, text=f"{done}/{total}편 완료")

        st.markdown("---")

        # 필터
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        with fc1:
            status_filter = st.multiselect(
                "상태", ["대기", "리서치완료", "초안완료", "최종완료"],
                default=["대기", "리서치완료", "초안완료"]
            )
        with fc2:
            brand_filter = st.text_input("브랜드", placeholder="시그니아, 포낙…")
        with fc3:
            sort_by = st.selectbox("정렬", ["번호순", "우선순위순"])

        def prio_key(r):
            v = str(r.get("우선순위", "99") or "99")
            m = re.search(r"\d+", v)
            return int(m.group()) if m else 99

        filtered = [
            t for t in topics
            if (not status_filter or t.get("상태", "대기") in status_filter)
            and (not brand_filter or brand_filter.strip() in str(t.get("브랜드", "")))
        ]
        if sort_by == "우선순위순":
            filtered.sort(key=prio_key)
        else:
            filtered.sort(key=lambda t: int(str(t.get("#", 0) or 0)))

        st.markdown(f"**{len(filtered)}개 표시 중**")

        for t in filtered:
            num    = str(t.get("#", "")).zfill(2)
            title  = t.get("영상 제목", "")
            brand  = t.get("브랜드", "")
            status = str(t.get("상태", "대기"))
            icon   = STATUS_ICON.get(status, "⚪")
            cls    = STATUS_CLASS.get(status, "s-wait")
            prio   = t.get("우선순위", "")

            label = f"{icon} {num}편 | {title}"
            if brand:
                label += f"  [{brand}]"

            with st.expander(label):
                ec1, ec2, ec3, ec4 = st.columns(4)
                ec1.markdown(f"**상태**<br><span class='status-chip {cls}'>{status}</span>", unsafe_allow_html=True)
                ec2.markdown(f"**브랜드**<br>{brand or '-'}", unsafe_allow_html=True)
                ec3.markdown(f"**우선순위**<br>{prio or '-'}", unsafe_allow_html=True)
                ec4.markdown(f"**키워드**<br>{t.get('2차 키워드','') or '-'}", unsafe_allow_html=True)

                st.markdown("---")
                st.markdown("**Claude Code 명령어** (Claude Code 채팅창에 붙여넣기):")
                st.code(f"{int(num)}번 시작", language=None)


# ══════════════════════════════════════════════════════════════════════════
# TAB 2 : 가격 검색
# ══════════════════════════════════════════════════════════════════════════
with tab2:
    db = load_price_db()

    if db is None:
        st.error("price_db.json 없음")
        st.stop()

    meta = db.get("_meta", {})
    st.caption(f"기준: {meta.get('정부고시','')} · 생성일: {meta.get('생성일','')}")

    search = st.text_input("🔍 제품명 검색", placeholder="예: Pure 312, Styletto, Virto, Evolv")

    if search.strip():
        kw = norm(search)
        results = [
            (brand, p)
            for brand, products in db["brands"].items()
            for p in products
            if kw in norm(p["제품명"])
        ]

        if not results:
            st.info("검색 결과 없음")
        else:
            st.markdown(f"**{len(results)}개 검색됨**")
            for brand, p in results:
                gov   = p.get("결정가격")
                cons  = p.get("소비자가_보장구") or p.get("소비자가_신제품")
                diff  = p.get("소비자가_초과분", 0)
                dcls  = "diff-red" if diff >= 400000 else ("diff-ora" if diff else "")

                gov_str  = f"{gov:,}원" if gov else "—"
                cons_str = f"{cons:,}원" if cons else "—"
                diff_str = f'<span class="{dcls}">+{diff:,}원</span>' if diff else ""

                st.markdown(f"""
<div class="price-row">
<b>[{brand.upper()}]</b> {p['제품명']}<br>
정부결정가 <b>{gov_str}</b> &nbsp;|&nbsp;
소비자가 <b>{cons_str}</b> &nbsp;
{diff_str}
<br><small>{p.get('제품군','')[:40]}</small>
</div>
""", unsafe_allow_html=True)

    else:
        # 브랜드 카드 요약
        st.markdown("### 브랜드별 가격 현황")
        cols = st.columns(3)
        for i, (brand, products) in enumerate(db["brands"].items()):
            matched = [p for p in products if "결정가격" in p and
                       ("소비자가_보장구" in p or "소비자가_신제품" in p)]
            avg_diff = (sum(p.get("소비자가_초과분",0) for p in matched) // len(matched)) if matched else 0

            with cols[i % 3]:
                st.markdown(f"""
<div class="metric-card">
<b style="font-size:16px">{brand.upper()}</b><br>
<span style="font-size:24px;font-weight:bold">{len(products)}</span>개 제품<br>
<small>매칭 {len(matched)}개</small><br>
<small>평균 초과 {avg_diff:,}원</small>
</div><br>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# TAB 3 : 브랜드별 비교
# ══════════════════════════════════════════════════════════════════════════
with tab3:
    db = load_price_db()
    if db is None:
        st.error("price_db.json 없음")
        st.stop()

    brand_list = list(db["brands"].keys())
    selected = st.selectbox("브랜드", ["전체"] + [b.upper() for b in brand_list])
    show_only_matched = st.checkbox("정부고시 + 소비자가 모두 있는 제품만", value=True)

    brands_to_show = brand_list if selected == "전체" else [selected.lower()]

    rows = []
    for brand in brands_to_show:
        for p in db["brands"].get(brand, []):
            gov  = p.get("결정가격")
            cons = p.get("소비자가_보장구") or p.get("소비자가_신제품")
            diff = p.get("소비자가_초과분")

            if show_only_matched and not (gov and cons):
                continue

            rows.append({
                "브랜드":    brand.upper(),
                "제품명":    p["제품명"],
                "정부결정가": gov,
                "소비자가":  cons,
                "초과분":    diff,
                "제품군":    p.get("제품군", "")[:25],
            })

    if not rows:
        st.info("데이터 없음")
    else:
        st.markdown(f"**{len(rows)}개 제품**")

        # 초과분 기준 색상 강조
        import pandas as pd
        df = pd.DataFrame(rows)
        df["정부결정가"] = df["정부결정가"].apply(lambda x: f"{x:,}원" if x else "—")
        df["소비자가"]   = df["소비자가"].apply(lambda x: f"{x:,}원" if x else "—")
        df["초과분"]     = df["초과분"].apply(lambda x: f"+{x:,}원" if x else "—")
        st.dataframe(df, use_container_width=True, hide_index=True)
