import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import random, json, os
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="법학암기 (Cloud Sync)", layout="wide")
st.title("⚖️ 법학암기카드 (Google Sheets 연동)")

# 1. 구글 시트 연결
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"❌ 구글 시트 연결 설정(Secrets) 확인 필요: {e}")
    st.stop()

# 2. 데이터 로드 함수
def load_gsheets_data():
    h_df, c_df, e_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        h_df = conn.read(worksheet="History", ttl="0")
    except: pass
    try:
        c_df = conn.read(worksheet="Checked", ttl="0")
    except: pass
    try:
        e_df = conn.read(worksheet="EverChecked", ttl="0")
    except: pass
    return h_df, c_df, e_df

def save_to_gsheets(df, sheet_name):
    try:
        conn.update(worksheet=sheet_name, data=df)
    except Exception as e:
        st.error(f"❌ '{sheet_name}' 저장 실패: {e}")

# 3. 세션 상태 초기화 (NameError 방지를 위해 모든 변수 사전 정의)
if 'init' not in st.session_state:
    h, c, e = load_gsheets_data()
    st.session_state.his = h if not h.empty else pd.DataFrame(columns=["date", "issue", "correct", "my_answer", "feedback"])
    st.session_state.chk = set(c['issue'].tolist()) if (not c.empty and 'issue' in c.columns) else set()
    st.session_state.evr = e.set_index('issue')['count'].to_dict() if (not e.empty and 'issue' in e.columns) else {}
    st.session_state.init = True

# 현재 문제 정보를 저장할 세션 변수
if 'cur_iss' not in st.session_state: st.session_state.cur_iss = ""
if 'cur_ans' not in st.session_state: st.session_state.cur_ans = ""
if 'cur_pin' not in st.session_state: st.session_state.cur_pin = ""
if 'pos' not in st.session_state: st.session_state.pos = 0
if 'ans_visible' not in st.session_state: st.session_state.ans_visible = False
if 'rec' not in st.session_state: st.session_state.rec = []

# 4. 앱 메인 로직
t1, t2, t3, t4, t5 = st.tabs(["📖 문제 풀기", "📊 학습 리포트", "📑 전체 쟁점 정리", "📌 현재 체크 문제", "🕒 누적 체크 기록"])
up = st.sidebar.file_uploader("엑셀 파일 업로드", type=["csv", "xlsx"])

if up:
    try:
        if up.name.endswith('.csv'): df = pd.read_csv(up, header=1)
        else: df = pd.read_excel(up, header=1, engine='openpyxl')
        
        df = df.dropna(subset=[df.columns[5], df.columns[6]])
        df[df.columns[5]] = df[df.columns[5]].astype(str).str.strip()
        df.iloc[:, 1] = df.iloc[:, 1].fillna("미분류")
        if len(df.columns) >= 11:
            df[df.columns[10]] = pd.to_datetime(df[df.columns[10]], errors='coerce')
        pts = df.iloc[:, 1].unique()
        
        with t1:
            st.sidebar.header("🎯 학습 설정")
            md = st.sidebar.radio("범위", ["전체", "✅ 체크만"])
            date_opt = st.sidebar.selectbox("기간 선택", ["전체 기간", "오늘 공부", "최근 3일", "최근 7일", "최근 1달"])
            sc = st.sidebar.multiselect("편 선택", pts, default=pts)
            
            fdf = df[df.iloc[:, 1].isin(sc)]
            if len(df.columns) >= 11 and date_opt != "전체 기간":
                today = datetime.now().date()
                days_gap = {"오늘 공부": 0, "최근 3일": 3, "최근 7일": 7, "최근 1달": 30}
                target_date = today - timedelta(days=days_gap[date_opt])
                fdf = fdf[fdf[fdf.columns[10]].dt.date >= target_date]
            if md == "✅ 체크만": fdf = fdf[fdf.iloc[:, 5].isin(st.session_state.chk)]
            
            idx_l = fdf.index.tolist()
            if not idx_l:
                st.info("조건에 맞는 문제가 없습니다.")
            else:
                # 문제 선택 로직
                if st.session_state.pos >= len(idx_l): st.session_state.pos = 0
                
                # '다음 문제' 버튼 클릭 시 세션 상태 업데이트
                if st.button("🔄 다음 문제") or st.session_state.cur_iss == "":
                    # 중복 방지 로직 포함
                    cd = [i for i in idx_l if df.loc[i].iloc[5] not in st.session_state.rec]
                    st.session_state.pos = idx_l.index(random.choice(cd if cd else idx_l))
                    
                    r = df.loc[idx_l[st.session_state.pos]]
                    st.session_state.cur_iss = r.iloc[5]
                    st.session_state.cur_ans = str(r.iloc[6])
                    pa = [str(r.iloc[i]) for i in range(1, 4) if pd.notna(r.iloc[i]) and str(r.iloc[i]).lower() != 'nan']
                    dt_txt = f" | 🗓️ {r.iloc[10].strftime('%Y-%m-%d')}" if len(df.columns) >= 11 and pd.notna(r.iloc[10]) else ""
                    st.session_state.cur_pin = f"📍 {' > '.join(pa)}{dt_txt}"
                    
                    # 최근 기록 업데이트
                    if st.session_state.cur_iss in st.session_state.rec: st.session_state.rec.remove(st.session_state.cur_iss)
                    st.session_state.rec.append(st.session_state.cur_iss)
                    if len(st.session_state.rec) > 3: st.session_state.rec.pop(0)
                    
                    st.session_state.ans_visible = False
                    st.rerun()

                # 문제 화면 출력
                st.caption(st.session_state.cur_pin)
                cq, cc = st.columns([5, 1])
                with cq: st.markdown(f"### ❓ 쟁점: {st.session_state.cur_iss}")
                with cc:
                    is_checked = st.session_state.cur_iss in st.session_state.chk
                    if st.button("❌ 해제" if is_checked else "📌 체크", key="chk_btn"):
                        if is_checked: st.session_state.chk.remove(st.session_state.cur_iss)
                        else:
                            st.session_state.chk.add(st.session_state.cur_iss)
                            st.session_state.evr[st.session_state.cur_iss] = st.session_state.evr.get(st.session_state.cur_iss, 0) + 1
                            save_to_gsheets(pd.DataFrame(list(st.session_state.evr.items()), columns=['issue', 'count']), "EverChecked")
                        save_to_gsheets(pd.DataFrame(list(st.session_state.chk), columns=['issue']), "Checked")
                        st.rerun()

                user_input = st.text_area("워딩 입력:", height=150, key=f"input_{st.session_state.cur_iss}")
                
                if st.button("✅ 정답 확인"): st.session_state.ans_visible = True
                
                if st.session_state.ans_visible:
                    c1, c2 = st.columns(2)
                    with c1: st.warning("📝 나의 답변"); st.write(user_input if user_input else "내용 없음")
                    with c2: st.success("👨‍⚖️ 실제 판례"); st.write(st.session_state.cur_ans)
                    
                    feedback = st.text_input("보완할 점:", key=f"fb_{st.session_state.cur_iss}")
                    if st.button("💾 기록 저장"):
                        # 모든 변수를 세션 상태에서 가져오므로 NameError가 발생하지 않음
                        new_row = pd.DataFrame([{
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "issue": st.session_state.cur_iss,
                            "correct": st.session_state.cur_ans,
                            "my_answer": user_input,
                            "feedback": feedback
                        }])
                        st.session_state.his = pd.concat([st.session_state.his, new_row], ignore_index=True)
                        save_to_gsheets(st.session_state.his, "History")
                        st.success("✅ 구글 시트 저장 완료!")

        # 탭 2~5는 로드된 세션 데이터를 기반으로 출력
        with t2:
            st.header("📊 학습 리포트")
            if st.session_state.his.empty: st.info("기록이 없습니다.")
            else: st.dataframe(st.session_state.his, use_container_width=True)

        with t3:
            st.header("📑 전체 쟁점 정리")
            st.dataframe(df.iloc[:, [1, 5, 6]], use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ 데이터 처리 중 오류: {e}")
else:
    st.info("👈 사이드바에서 엑셀 파일을 업로드해 주세요!")
