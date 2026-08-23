import hashlib
import random
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st 
from streamlit_gsheets import GSheetsConnection


st.set_page_config(page_title="법학암기 (Cloud Sync)", layout="wide")
st.title("⚖️ 법학암기카드 (Stable Build)")

REQUIRED_COLUMN_COUNT = 7
HISTORY_COLUMNS = ["date", "card_id", "issue", "correct", "my_answer", "feedback", "evaluation"]


@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)


def empty_history():
    return pd.DataFrame(columns=HISTORY_COLUMNS)


def read_sheet(worksheet, columns):
    """빈 워크시트만 빈 DataFrame으로 처리하고, 연결 오류는 사용자에게 알린다."""
    try:
        data = get_connection().read(worksheet=worksheet, ttl=0)
        return data if not data.empty else pd.DataFrame(columns=columns)
    except Exception as exc:
        st.warning(f"'{worksheet}' 시트를 읽지 못했습니다: {exc}")
        return pd.DataFrame(columns=columns)


def update_sheet(data, worksheet):
    try:
        get_connection().update(worksheet=worksheet, data=data)
        return True
    except Exception as exc:
        st.error(f"❌ '{worksheet}' 저장 실패: {exc}")
        return False


def card_id(row):
    """동일 쟁점명이 다른 편/절에 있을 때도 구분되는 안정적인 내부 식별자."""
    values = [str(row.iloc[index]).strip() if index < len(row) and pd.notna(row.iloc[index]) else "" for index in (1, 2, 3, 4, 5)]
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()[:16]


def pin_text(row):
    paths = [str(row.iloc[i]).strip() for i in (1, 2, 3) if pd.notna(row.iloc[i]) and str(row.iloc[i]).strip().lower() != "nan" and str(row.iloc[i]).strip()]
    article = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) and str(row.iloc[4]).strip().lower() != "nan" else ""
    if article:
        paths[-1:] = [f"{paths[-1]}({article})"] if paths else [f"({article})"]
    return f"📍 {' > '.join(paths)}" if paths else "📍 미분류"


def prepare_cards(uploaded_file):
    if uploaded_file.name.lower().endswith(".csv"):
        cards = pd.read_csv(uploaded_file, header=1)
    else:
        cards = pd.read_excel(uploaded_file, header=1, engine="openpyxl")
    if len(cards.columns) < REQUIRED_COLUMN_COUNT:
        raise ValueError("업로드 파일에는 최소 7개 열이 필요합니다. (F열: 쟁점, G열: 판례 내용)")

    cards = cards.dropna(subset=[cards.columns[5], cards.columns[6]]).copy()
    if cards.empty:
        raise ValueError("F열과 G열에 모두 값이 있는 문제가 없습니다.")
    for index, default in ((1, "미분류"), (2, "일반"), (5, "")):
        cards.iloc[:, index] = cards.iloc[:, index].fillna(default).astype(str).str.strip()
    cards.iloc[:, 6] = cards.iloc[:, 6].fillna("").astype(str).str.strip()
    if len(cards.columns) >= 11:
        cards.iloc[:, 10] = pd.to_datetime(cards.iloc[:, 10], errors="coerce")
    cards["_card_id"] = cards.apply(card_id, axis=1)
    return cards


def is_checked(card):
    # issue만 저장한 기존 Checked 시트와 card_id를 저장한 새 형식을 모두 지원한다.
    return card["_card_id"] in st.session_state.checked_ids or card.iloc[5] in st.session_state.checked_legacy_issues


def save_checked_state():
    cards = st.session_state.cards
    selected = cards[cards.apply(is_checked, axis=1)][["_card_id", cards.columns[5]]].copy()
    selected.columns = ["card_id", "issue"]
    return update_sheet(selected.drop_duplicates(), "Checked")


def append_history(record):
    # 기록 버튼을 누를 때 최신 History를 다시 읽어 다른 세션의 기존 기록을 보존한다.
    latest = read_sheet("History", HISTORY_COLUMNS)
    for column in HISTORY_COLUMNS:
        if column not in latest.columns:
            latest[column] = ""
    return update_sheet(pd.concat([latest[HISTORY_COLUMNS], pd.DataFrame([record])], ignore_index=True), "History")


def as_count(value):
    number = pd.to_numeric(value, errors="coerce")
    return int(number) if pd.notna(number) else 0


def choose_next(cards):
    if cards.empty:
        return False
    candidates = cards[~cards["_card_id"].isin(st.session_state.recent_ids)]
    card = candidates.sample(n=1) if not candidates.empty else cards.sample(n=1)
    selected = card.iloc[0]
    st.session_state.current_id = selected["_card_id"]
    st.session_state.answer_visible = False
    st.session_state.recent_ids = (st.session_state.recent_ids + [selected["_card_id"]])[-5:]
    return True


if "initialized" not in st.session_state:
    history = read_sheet("History", HISTORY_COLUMNS)
    checked = read_sheet("Checked", ["card_id", "issue"])
    ever_checked = read_sheet("EverChecked", ["card_id", "issue", "count"])
    st.session_state.history = history if not history.empty else empty_history()
    st.session_state.checked_ids = set(checked.get("card_id", pd.Series(dtype=str)).dropna().astype(str))
    st.session_state.checked_legacy_issues = set(checked.get("issue", pd.Series(dtype=str)).dropna().astype(str))
    st.session_state.ever_checked = {
        str(row.get("card_id") or row.get("issue")): as_count(row.get("count"))
        for _, row in ever_checked.iterrows()
    }
    st.session_state.recent_ids = []
    st.session_state.current_id = None
    st.session_state.answer_visible = False
    st.session_state.initialized = True


uploaded = st.sidebar.file_uploader("엑셀 파일 업로드", type=["csv", "xlsx"])
if not uploaded:
    st.info("👈 사이드바에서 엑셀 파일을 업로드해 주세요!")
    st.stop()

try:
    st.session_state.cards = prepare_cards(uploaded)
except Exception as exc:
    st.error(f"⚠️ 업로드 파일을 처리할 수 없습니다: {exc}")
    st.stop()

cards = st.session_state.cards
parts = sorted(cards.iloc[:, 1].dropna().unique())
t1, t2, t3, t4, t5 = st.tabs(["📖 문제 풀기", "📊 학습 리포트", "📑 전체 쟁점 정리", "📌 현재 체크 문제", "🕒 누적 체크 기록"])

with t1:
    st.sidebar.header("🎯 학습 설정")
    study_mode = st.sidebar.radio("학습 모드", ["타이핑 모드", "플래시카드(눈으로)"])
    scope = st.sidebar.radio("범위", ["전체", "✅ 체크만"])
    period = st.sidebar.selectbox("기간 선택", ["전체 기간", "오늘 공부", "최근 3일", "최근 7일", "최근 1달"])
    selected_parts = st.sidebar.multiselect("편 선택", parts, default=parts)

    filtered = cards[cards.iloc[:, 1].isin(selected_parts)].copy()
    if period != "전체 기간":
        if len(cards.columns) < 12:  # _card_id가 추가되어 원본 11열은 총 12열
            st.sidebar.warning("기간 필터를 사용하려면 원본 K열에 날짜가 필요합니다.")
        else:
            days = {"오늘 공부": 0, "최근 3일": 2, "최근 7일": 6, "최근 1달": 29}[period]
            cutoff = pd.Timestamp(datetime.now().date() - timedelta(days=days))
            filtered = filtered[filtered.iloc[:, 10].notna() & (filtered.iloc[:, 10] >= cutoff)]
    if scope == "✅ 체크만":
        filtered = filtered[filtered.apply(is_checked, axis=1)]

    if st.button("🔄 다음 문제") or st.session_state.current_id is None:
        if not choose_next(filtered):
            st.info("해당 기간/범위에 맞는 문제가 없습니다.")
            st.stop()
        st.rerun()

    current_rows = cards[cards["_card_id"] == st.session_state.current_id]
    if current_rows.empty:
        st.warning("현재 문제를 찾을 수 없습니다. 새 문제를 선택해 주세요.")
        st.session_state.current_id = None
        st.rerun()
    current = current_rows.iloc[0]
    st.caption(pin_text(current))
    left, right = st.columns([5, 1])
    with left:
        st.markdown(f"### ❓ 쟁점: {current.iloc[5]}")
    with right:
        checked_now = is_checked(current)
        if st.button("❌ 해제" if checked_now else "📌 체크"):
            if checked_now:
                st.session_state.checked_ids.discard(current["_card_id"])
                st.session_state.checked_legacy_issues.discard(current.iloc[5])
            else:
                st.session_state.checked_ids.add(current["_card_id"])
                st.session_state.ever_checked[current["_card_id"]] = st.session_state.ever_checked.get(current["_card_id"], 0) + 1
                ever = pd.DataFrame([
                    {"card_id": key, "issue": cards.loc[cards["_card_id"] == key].iloc[0, 5] if not cards.loc[cards["_card_id"] == key].empty else key, "count": count}
                    for key, count in st.session_state.ever_checked.items()
                ])
                if not update_sheet(ever, "EverChecked"):
                    st.stop()
            if save_checked_state():
                st.rerun()

    typed_answer = ""
    if study_mode == "타이핑 모드":
        typed_answer = st.text_area("워딩 입력:", height=150, key=f"answer_{current['_card_id']}")
    else:
        st.info("💡 눈으로 판례를 떠올린 후 아래 [정답 확인]을 눌러주세요.")
    if st.button("✅ 정답 확인"):
        st.session_state.answer_visible = True

    if st.session_state.answer_visible:
        answer_col, model_col = st.columns(2)
        answer_col.warning("📝 나의 답변")
        answer_col.write(typed_answer if typed_answer else "눈으로 복습 중")
        model_col.success("👨‍⚖️ 실제 판례")
        model_col.write(current.iloc[6])
        if study_mode == "타이핑 모드":
            matched = len(set(typed_answer.split()) & set(str(current.iloc[6]).split()))
            st.caption(f"💡 키워드 일치: {matched}개")

        evaluation = st.radio("스스로 평가하기", ["쉬움", "보통", "어려움"], index=None, horizontal=True, key=f"evaluation_{current['_card_id']}")
        feedback = st.text_input("보완할 점:", key=f"feedback_{current['_card_id']}")
        if st.button("💾 기록 저장"):
            record = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "card_id": current["_card_id"],
                "issue": current.iloc[5], "correct": current.iloc[6],
                "my_answer": typed_answer if study_mode == "타이핑 모드" else "플래시카드",
                "feedback": feedback, "evaluation": evaluation or "",
            }
            if append_history(record):
                st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([record])], ignore_index=True)
                st.success("✅ 저장 완료!")

with t2:
    st.header("📊 학습 리포트")
    if st.button("🔄 리포트 새로고침"):
        st.session_state.history = read_sheet("History", HISTORY_COLUMNS)
        st.rerun()
    report_parts = st.multiselect("1. 편 선택 (리포트)", parts, key="report_parts")
    if report_parts:
        sections = sorted(cards[cards.iloc[:, 1].isin(report_parts)].iloc[:, 2].unique())
        report_sections = st.multiselect("2. 절 선택 (리포트)", sections, default=sections, key="report_sections")
        shown = 0
        for _, row in cards[(cards.iloc[:, 1].isin(report_parts)) & (cards.iloc[:, 2].isin(report_sections))].iterrows():
            records = st.session_state.history
            if "card_id" in records.columns:
                has_card_id = records["card_id"].notna() & records["card_id"].astype(str).ne("")
                records = records[
                    (has_card_id & records["card_id"].astype(str).eq(str(row["_card_id"])))
                    | (~has_card_id & records["issue"].astype(str).eq(str(row.iloc[5])))
                ]
            if records.empty:
                continue
            shown += 1
            with st.expander(f"📌 {row.iloc[5]}", expanded=False):
                for _, record in records.iloc[::-1].iterrows():
                    st.caption(f"📅 학습 일시: {record.get('date', '')} · 평가: {record.get('evaluation', '') or '-'}")
                    st.warning(f"**보완 사항**: {record.get('feedback', '') or '-'}")
                    a, b = st.columns(2)
                    a.info(f"**나의 답변**\n\n{record.get('my_answer', '')}")
                    b.success(f"**실제 정답**\n\n{record.get('correct', '')}")
        if not shown:
            st.info("선택한 범위에 저장된 학습 기록이 없습니다.")

with t3:
    st.header("📑 전체 쟁점 정리")
    total_parts = st.multiselect("1. 편 선택 (정리)", parts, key="total_parts")
    if total_parts:
        sections = sorted(cards[cards.iloc[:, 1].isin(total_parts)].iloc[:, 2].unique())
        total_sections = st.multiselect("2. 절 선택 (정리)", sections, default=sections, key="total_sections")
        for _, row in cards[(cards.iloc[:, 1].isin(total_parts)) & (cards.iloc[:, 2].isin(total_sections))].iterrows():
            with st.expander(f"🔍 {row.iloc[5]}"):
                st.caption(pin_text(row))
                st.write(f"**내용:** {row.iloc[6]}")

with t4:
    st.header("📌 현재 체크 문제")
    checked_cards = cards[cards.apply(is_checked, axis=1)]
    if checked_cards.empty:
        st.info("체크한 문제가 없습니다.")
    for _, row in checked_cards.iterrows():
        st.caption(pin_text(row))
        st.markdown(f"#### ❓ {row.iloc[5]}")
        st.write(f"**판례:** {row.iloc[6]}")
        st.divider()

with t5:
    st.header("🕒 누적 체크 기록")
    if not st.session_state.ever_checked:
        st.info("누적 체크 기록이 없습니다.")
    for key, count in sorted(st.session_state.ever_checked.items(), key=lambda item: item[1], reverse=True):
        matched = cards[cards["_card_id"].eq(key)]
        title = matched.iloc[0, 5] if not matched.empty else key
        with st.expander(f"🚩 {title} ({count}회)"):
            if not matched.empty:
                st.write(matched.iloc[0, 6])
            else:
                st.caption("현재 업로드한 파일에는 없는 과거 체크 기록입니다.")
