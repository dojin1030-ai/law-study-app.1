import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import random, json, os
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="법학암기 (Cloud Sync)", layout="wide")
st.title("⚖️ 법학암기카드 (Stable Build)")

# 1. 구글 시트 연결
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"❌ 구글 시트 연결 설정 확인 필요: {e}")
    st.stop()

# 2. 데이터 로드 및 저장 함수
def load_gsheets_data():
    h_df, c_df, e_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try: h_df = conn.read(worksheet="History", ttl=0)
    except: pass
    try: c_df = conn.read(worksheet="Checked", ttl=0)
    except: pass
    try: e_df = conn.read(worksheet="EverChecked", ttl=0)
    except: pass
    return h_df, c_df, e_df

def save_to_gsheets(df, sheet_name):
    try:
        conn.update(worksheet=sheet_name, data=df)
        return True
    except Exception as e:
        st.error(f"❌ '{sheet_name}' 저장 실패: {str(e)}")
        return False

# 3. 세션 상태 초기화
if 'init' not in st.session_state:
    h, c, e = load_gsheets_data()
    st.session_state.his = h if not h.empty else pd.DataFrame(columns=["date", "issue", "correct", "my_answer", "feedback"])
    st.session_state.chk = set(c['issue'].tolist()) if (not c.empty and 'issue' in c.columns) else set()
    st.session_state.evr = e.set_index('issue')['count'].to_dict() if (not e.empty and 'issue' in e.columns) else {}
    st.session_state.init = True

if 'cur_iss' not in st.session_state: st.session_state.cur_iss = ""
if 'cur_ans' not in st.session_state: st.session_state.cur_ans = ""
if 'cur_pin' not in st.session_state: st.session_state.cur_pin = ""
if 'ans_visible' not in st.session_state: st.session_state.ans_visible = False
if 'rec' not in st.session_state: st.session_state.rec = []

# 4. 메인 UI
t1, t2, t3, t4, t5 = st.tabs(["📖 문제 풀기", "📊 학습 리포트", "📑 전체 쟁점 정리", "📌 현재 체크 문제", "🕒 누적 체크 기록"])
up = st.sidebar.file_uploader("엑셀 파일 업로드", type=["csv", "xlsx"])

if up:
    try:
        if up.name.endswith('.csv'): df = pd.read_csv(up, header=1)
        else: df = pd.read_excel(up, header=1, engine='openpyxl')
        
        df = df.dropna(subset=[df.columns[5], df.columns[6]])
        df.iloc[:, 1] = df.iloc[:, 1].fillna('미분류').astype(str).str.strip()
        df.iloc[:, 2] = df.iloc[:, 2].fillna('일반').astype(str).str.strip()
        df[df.columns[5]] = df[df.columns[5]].astype(str).str.strip()
        
        # [K열 날짜 처리 필수] 인덱스 10이 K열입니다.
        if len(df.columns) >= 11:
            df[df.columns[10]] = pd.to_datetime(df[df.columns[10]], errors='coerce')
        
        all_parts = sorted(df.iloc[:, 1].unique())

        def get_pin_text(r):
            paths = [str(r.iloc[i]).strip() for i in [1, 2, 3] if pd.notna(r.iloc[i]) and str(r.iloc[i]).strip().lower() != 'nan' and str(r.iloc[i]).strip() != '']
            art = str(r.iloc[4]).strip() if pd.notna(r.iloc[4]) and str(r.iloc[4]).strip().lower() != 'nan' else ""
            if art:
                if paths: paths[-1] = f"{paths[-1]}({art})"
                else: paths.append(f"({art})")
            return f"📍 {' > '.join(paths)}" if paths else "📍 미분류"

        def pick_next(target_df):
            idx_l = target_df.index.tolist()
            if not idx_l: return False
            cd = [i for i in idx_l if target_df.loc[i].iloc[5] not in st.session_state.rec]
            sel_idx = random.choice(cd if cd else idx_l)
            r = target_df.loc[sel_idx]
            st.session_state.cur_iss = r.iloc[5]
            st.session_state.cur_ans = str(r.iloc[6])
            st.session_state.cur_pin = get_pin_text(r)
            if st.session_state.cur_iss in st.session_state.rec: st.session_state.rec.remove(st.session_state.cur_iss)
            st.session_state.rec.append(st.session_state.cur_iss)
            if len(st.session_state.rec) > 5: st.session_state.rec.pop(0)
            st.session_state.ans_visible = False
            return True

        with t1:
            st.sidebar.header("🎯 학습 설정")
            study_mode = st.sidebar.radio("학습 모드", ["타이핑 모드", "플래시카드(눈으로)"])
            md = st.sidebar.radio("범위", ["전체", "✅ 체크만"])
            
            # [수정] K열(인덱스 10) 기준 날짜 필터링 로직 복구
            dt_opt = st.sidebar.selectbox("기간 선택", ["전체 기간", "오늘 공부", "최근 3일", "최근 7일", "최근 1달"])
            sc_parts = st.sidebar.multiselect("편 선택", all_parts, default=all_parts)
            
            fdf = df[df.iloc[:, 1].isin(sc_parts)]
            
            if len(df.columns) >= 11 and dt_opt != "전체 기간":
                days_map = {"오늘 공부": 0, "최근 3일": 3, "최근 7일": 7, "최근 1달": 30}
                today = datetime.now().date()
                target_date = today - timedelta(days=days_map[dt_opt])
                # K열(인덱스 10)의 날짜와 비교
                fdf = fdf[fdf[df.columns[10]].dt.date >= target_date]

            if md == "✅ 체크만": fdf = fdf[fdf.iloc[:, 5].isin(st.session_state.chk)]
            
            if st.button("🔄 다음 문제") or st.session_state.cur_iss == "":
                if not pick_next(fdf): st.info("해당 기간/범위에 맞는 문제가 없습니다.")
                else: st.rerun()

            st.caption(st.session_state.cur_pin)
            cq, cc = st.columns([5, 1])
            with cq: st.markdown(f"### ❓ 쟁점: {st.session_state.cur_iss}")
            with cc:
                is_ch = st.session_state.cur_iss in st.session_state.chk
                if st.button("❌ 해제" if is_ch else "📌 체크", key="main_chk"):
                    if is_ch: st.session_state.chk.remove(st.session_state.cur_iss)
                    else:
                        st.session_state.chk.add(st.session_state.cur_iss)
                        st.session_state.evr[st.session_state.cur_iss] = st.session_state.evr.get(st.session_state.cur_iss, 0) + 1
                        save_to_gsheets(pd.DataFrame(list(st.session_state.evr.items()), columns=['issue', 'count']), "EverChecked")
                    save_to_gsheets(pd.DataFrame(list(st.session_state.chk), columns=['issue']), "Checked"); st.rerun()
            
            u_i = ""
            if study_mode == "타이핑 모드":
                u_i = st.text_area("워딩 입력:", height=150, key=f"ui_{st.session_state.cur_iss}")
            else:
                st.info("💡 눈으로 판례를 떠올린 후 아래 [정답 확인]을 눌러주세요.")

            if st.button("✅ 정답 확인"): st.session_state.ans_visible = True
            
            if st.session_state.ans_visible:
                c1, c2 = st.columns(2)
                with c1: st.warning("📝 나의 답변"); st.write(u_i if (study_mode == "타이핑 모드" and u_i) else "눈으로 복습 중")
                with c2: st.success("👨‍⚖️ 실제 판례"); st.write(st.session_state.cur_ans)
                
                if study_mode == "타이핑 모드":
                    u_words = set(u_i.split()); a_words = set(st.session_state.cur_ans.split())
                    match_count = len(u_words.intersection(a_words))
                    st.markdown(f"<p style='color:gray; font-size: 0.8em; margin-top: -10px;'>💡 키워드 일치: {match_count}개</p>", unsafe_allow_html=True)
                
                st.write("**스스로 평가하기**")
                ev_cols = st.columns(4)
                evaluation = ""
                if ev_cols[0].button("🟢 쉬움"): evaluation = "쉬움"
                if ev_cols[1].button("🟡 보통"): evaluation = "보통"
                if ev_cols[2].button("🔴 어려움"): evaluation = "어려움"
                
                fb = st.text_input("보완할 점:", key=f"fb_{st.session_state.cur_iss}")
                if st.button("💾 기록 저장") or evaluation:
                    final_fb = f"[{evaluation}] {fb}".strip() if evaluation else fb
                    new_row = pd.DataFrame([{"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "issue": st.session_state.cur_iss, "correct": st.session_state.cur_ans, "my_answer": u_i if study_mode == "타이핑 모드" else "플래시카드", "feedback": final_fb}])
                    st.session_state.his = pd.concat([st.session_state.his, new_row], ignore_index=True)
                    if save_to_gsheets(st.session_state.his, "History"): st.success("✅ 저장 완료!"); st.rerun()

        # 학습 리포트 (보완 상단 / 답변 정답 병렬 구조 엄격 유지)
        with t2:
            st.header("📊 학습 리포트")
            if st.button("🔄 리포트 새로고침"):
                h, c, e = load_gsheets_data()
                st.session_state.his = h; st.rerun()

            sel_p2 = st.multiselect("1. 편 선택 (리포트)", all_parts, key="p_rep")
            if sel_p2:
                rel_s2 = sorted(df[df.iloc[:, 1].isin(sel_p2)].iloc[:, 2].unique())
                sel_s2 = st.multiselect("2. 절 선택 (리포트)", rel_s2, default=rel_s2, key="s_rep")
                for p in sel_p2:
                    with st.expander(f"📁 {p}", expanded=True):
                        p_df = df[(df.iloc[:, 1] == p) & (df.iloc[:, 2].isin(sel_s2))]
                        for s in sorted(p_df.iloc[:, 2].unique()):
                            st.markdown(f"#### 📑 {s}")
                            for _, r in p_df[p_df.iloc[:, 2] == s].iterrows():
                                iss = r.iloc[5]
                                if not st.session_state.his.empty:
                                    mask = st.session_state.his['issue'].apply(lambda x: str(x) == iss or str(x).startswith(iss + "("))
                                    recs = st.session_state.his[mask]
                                    if not recs.empty:
                                        st.write(f"**📌 {iss}**")
                                        for _, row in recs.iloc[::-1].iterrows():
                                            with st.container():
                                                st.caption(f"📅 학습 일시: {row['date']}")
                                                st.warning(f"**보완 사항**: {row['feedback']}")
                                                r_low1, r_low2 = st.columns(2)
                                                r_low1.info(f"**나의 답변**\n\n{row['my_answer']}")
                                                r_low2.success(f"**실제 정답**\n\n{row['correct']}")
                                                st.divider()

        # 전체 쟁점 정리
        with t3:
            st.header("📑 전체 쟁점 정리")
            sel_p3 = st.multiselect("1. 편 선택 (정리)", all_parts, key="p_total")
            if sel_p3:
                rel_s3 = sorted(df[df.iloc[:, 1].isin(sel_p3)].iloc[:, 2].unique())
                sel_s3 = st.multiselect("2. 절 선택 (정리)", rel_s3, default=rel_s3, key="s_total")
                for p in sel_p3:
                    with st.expander(f"📁 {p}", expanded=True):
                        p_df = df[(df.iloc[:, 1] == p) & (df.iloc[:, 2].isin(sel_s3))]
                        for s in sorted(p_df.iloc[:, 2].unique()):
                            st.markdown(f"#### 📑 {s}")
                            for _, r in p_df[p_df.iloc[:, 2] == s].iterrows():
                                with st.expander(f"🔍 {r.iloc[5]}"):
                                    st.caption(get_pin_text(r))
                                    st.write(f"**내용:** {r.iloc[6]}")

        # 현재 체크 문제 (핀 작게 상단 유지)
        with t4:
            st.header("📌 현재 체크 문제")
            c_df = df[df.iloc[:, 5].isin(st.session_state.chk)]
            for _, r in c_df.iterrows():
                st.markdown(f"<span style='font-size:15px; color:gray;'>{get_pin_text(r)}</span>", unsafe_allow_html=True)
                st.markdown(f"<h4 style='margin-top: 5px;'>❓ {r.iloc[5]}</h4>", unsafe_allow_html=True)
                st.write(f"**판례:** {r.iloc[6]}"); st.divider()
                
        with t5:
            st.header("🕒 누적 체크 기록")
            for is_nm, ct in st.session_state.evr.items():
                with st.expander(f"🚩 {is_nm} ({ct}회)"):
                    match_row = df[df.iloc[:, 5] == is_nm]
                    if not match_row.empty: st.write(match_row.iloc[0, 6])

    except Exception as e: st.error(f"⚠️ 오류 발생: {e}")
else: st.info("👈 사이드바에서 엑셀 파일을 업로드해 주세요!")
