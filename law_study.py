import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import random, json, os
from datetime import datetime, timedelta

# 페이지 설정 (형님의 취향을 반영한 깔끔한 레이아웃)
st.set_page_config(page_title="동진이 형님 전용 법학암기", layout="wide")
st.title("⚖️ 법학암기카드 (Cloud Sync)")

# 구글 시트 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

# 데이터 로드 함수 (JSON 대신 구글 시트 활용)
def load_data():
    try:
        # 'History', 'Checked', 'EverChecked' 라는 이름의 시트 탭이 필요합니다.
        his = conn.read(worksheet="History")
        chk = conn.read(worksheet="Checked")
        evr = conn.read(worksheet="EverChecked")
        return his, chk, evr
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# 데이터 저장 함수
def save_to_sheet(df, sheet_name):
    conn.update(worksheet=sheet_name, data=df)

# 세션 초기화 (최초 1회 구글 시트에서 읽어옴)
if 'init_done' not in st.session_state:
    st.session_state.his_df, st.session_state.chk_df, st.session_state.evr_df = load_data()
    st.session_state.chk = set(st.session_state.chk_df['issue'].tolist()) if not st.session_state.chk_df.empty else set()
    st.session_state.init_done = True

if 'pos' not in st.session_state: st.session_state.pos = 0
if 'ans' not in st.session_state: st.session_state.ans = False
if 'rec' not in st.session_state: st.session_state.rec = []

# --- 탭 구성 및 엑셀 로직은 동일하게 유지하되 저장 방식만 변경 ---
# (공간상 핵심 저장 로직만 요약해서 보여드립니다. 전체 적용 시 이 구조를 따릅니다.)

t1, t2, t3, t4, t5 = st.tabs(["📖 문제 풀기", "📊 학습 리포트", "📑 전체 쟁점 정리", "📌 현재 체크 문제", "🕒 누적 체크 기록"])
up = st.sidebar.file_uploader("엑셀 파일 업로드", type=["csv", "xlsx"])

if up:
    df = pd.read_excel(up, header=1, engine='openpyxl') # 전처리는 기존과 동일
    pts = df.iloc[:, 1].unique()
    
    with t1:
        # 문제 풀기 로직...
        if st.button("💾 기록 저장"):
            # 새 기록을 데이터프레임으로 만들어 구글 시트에 업데이트
            new_rec = pd.DataFrame([{"date": datetime.now(), "issue": iss, "my_answer": u_i, "feedback": fb}])
            st.session_state.his_df = pd.concat([st.session_state.his_df, new_rec], ignore_index=True)
            save_to_sheet(st.session_state.his_df, "History")
            st.success("구글 시트에 동기화 완료!")

    # 탭 2~5 역시 st.session_state의 데이터프레임을 시각화하고 
    # 수정이 발생할 때마다 save_to_sheet를 호출하도록 구성합니다.
