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
    st.error(f"❌ 구글 시트 연결 실패. Secrets 설정을 확인하세요: {e}")
    st.stop()

# 2. 데이터 로드 및 저장 함수 (에러 상세 보고 기능 추가)
def load_gsheets_data():
    h_df, c_df, e_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try: h_df = conn.read(worksheet="History", ttl="0")
    except Exception: pass
    try: c_df = conn.read(worksheet="Checked", ttl="0")
    except Exception: pass
    try: e_df = conn.read(worksheet="EverChecked", ttl="0")
    except Exception: pass
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

# 4. 앱 메인 탭
t1, t2, t3, t4, t5 = st.tabs(["📖 문제 풀기", "📊 학습 리포트", "📑 전체 쟁점 정리", "📌 현재 체크 문제", "🕒 누적 체크 기록"])
up = st.sidebar.file_uploader("엑셀 파일 업로드", type=["csv", "xlsx"])

if up:
    try:
        if up.name.endswith('.csv'): df = pd.read_csv(up, header=1)
        else: df = pd.read_excel(up, header=1, engine='openpyxl')
        
        df = df.dropna(subset=[df.columns[5], df.columns[6]])
        df.iloc[:, 1] = df.iloc[:, 1].fillna('미분류').astype(str).str.strip()
        df.iloc[:, 2] = df.iloc[:, 2].fillna('일반').astype(str).str.strip()
        
        # 쟁점명(조문) 포맷팅
        def get_format_iss(row):
            iss = str(row.iloc[5]).strip()
            art = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) and str(row.iloc[4]).lower() != 'nan' else ""
            return f"{iss}({art})" if art else iss
        df[df.columns[5]] = df.apply(get_format_iss, axis=1)
        
        if len(df.columns) >= 11:
            df[df.columns[10]] = pd.to_datetime(df[df.columns[10]], errors='coerce')
        
        all_parts = sorted(df.iloc[:, 1].unique())

        with t1:
            st.sidebar.header("🎯 학습 설정")
            md = st.sidebar.radio("범위", ["전체", "✅ 체크만"])
            dt_opt = st.sidebar.selectbox("기간 선택", ["전체 기간", "오늘 공부", "최근 3일", "최근 7일", "최근 1달"])
            sc_parts = st.sidebar.multiselect("편 선택", all_parts, default=all_parts)
            
            fdf = df[df.iloc[:, 1].isin(sc_parts)]
            if len(df.columns) >= 11 and dt_opt != "전체 기간":
                gap = {"오늘 공부": 0, "최근 3일": 3, "최근 7일": 7, "최근 1달": 30}[dt_opt]
                fdf = fdf[fdf[fdf.columns[10]].dt.date >= (datetime.now().date() - timedelta(days=gap))]
            if md == "✅ 체크만": fdf = fdf[fdf.iloc[:, 5].isin(st.session_state.chk)]
            
            idx_l = fdf.index.tolist()
            if not idx_l: st.info("문제가 없습니다.")
            else:
                # [수정] 문제 전환 로직 분리 (충돌 방지)
                def pick_next():
                    cd = [i for i in idx_l if df.loc[i].iloc[5] not in st.session_state.rec]
                    sel_idx = random.choice(cd if cd else idx_l)
                    r = df.loc[sel_idx]
                    st.session_state.cur_iss = r.iloc[5]
                    st.session_state.cur_ans = str(r.iloc[6])
                    pa = [str(r.iloc[i]) for i in range(1, 4) if pd.notna(r.iloc[i])]
                    dt_txt = f" | 🗓️ {r.iloc[10].strftime('%Y-%m-%d')}" if len(df.columns) >= 11 and pd.notna(r.iloc[10]) else ""
                    st.session_state.cur_pin = f"📍 {' > '.join(pa)}{dt_txt}"
                    if st.session_state.cur_iss in st.session_state.rec: st.session_state.rec.remove(st.session_state.cur_iss)
                    st.session_state.rec.append(st.session_state.cur_iss)
                    if len(st.session_state.rec) > 3: st.session_state.rec.pop(0)
                    st.session_state.ans_visible = False

                if st.button("🔄 다음 문제") or st.session_state.cur_iss == "":
                    pick_next()
                    st.rerun()

                st.caption(st.session_state.cur_pin)
                cq, cc = st.columns([5, 1])
                with cq: st.markdown(f"### ❓ 쟁점: {st.session_state.cur_iss}")
                with cc:
                    is_ch = st.session_state.cur_iss in st.session_state.chk
                    if st.button("❌ 해제" if is_ch else "📌 체크", key="chk_btn_main"):
                        if is_ch: st.session_state.chk.remove(st.session_state.cur_iss)
                        else:
                            st.session_state.chk.add(st.session_state.cur_iss)
                            st.session_state.evr[st.session_state.cur_iss] = st.session_state.evr.get(st.session_state.cur_iss, 0) + 1
                            save_to_gsheets(pd.DataFrame(list(st.session_state.evr.items()), columns=['issue', 'count']), "EverChecked")
                        save_to_gsheets(pd.DataFrame(list(st.session_state.chk), columns=['issue']), "Checked")
                        st.rerun()
                
                u_i = st.text_area("워딩 입력:", height=150, key=f"ui_{st.session_state.cur_iss}")
                if st.button("✅ 정답 확인"): st.session_state.ans_visible = True
                
                if st.session_state.ans_visible:
                    c1, c2 = st.columns(2)
                    with c1: st.warning("📝 나의 답변"); st.write(u_i if u_i else "내용 없음")
                    with c2: st.success("👨‍⚖️ 실제 판례"); st.write(st.session_state.cur_ans)
                    fb = st.text_input("보완할 점:", key=f"fb_{st.session_state.cur_iss}")
                    if st.button("💾 기록 저장"):
                        new_row = pd.DataFrame([{"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "issue": st.session_state.cur_iss, "correct": st.session_state.cur_ans, "my_answer": u_i, "feedback": fb}])
                        st.session_state.his = pd.concat([st.session_state.his, new_row], ignore_index=True)
                        if save_to_gsheets(st.session_state.his, "History"):
                            st.success("✅ 저장 완료!")

        with t2:
            st.header("📊 학습 리포트")
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
                                if iss in st.session_state.his['issue'].values:
                                    st.write(f"**📌 {iss}**")
                                    recs = st.session_state.his[st.session_state.his['issue'] == iss]
                                    for _, row in recs.iloc[::-1].iterrows():
                                        st.caption(f"📅 {row['date']} | {row['feedback']}")

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
                                with st.expander(f"🔍 {r.iloc[5]}"): st.write(f"**내용:** {r.iloc[6]}")

        # TAB 4 & 5 동일
        with t4:
            st.header("📌 현재 체크 문제")
            for idx, r in df[df.iloc[:, 5].isin(st.session_state.chk)].iterrows():
                st.markdown(f"#### ❓ {r.iloc[5]} (📍 {r.iloc[1]} > {r.iloc[2]})")
                st.write(f"**판례:** {r.iloc[6]}")
        with t5:
            st.header("🕒 누적 체크 기록")
            for is_nm, ct in st.session_state.evr.items():
                with st.expander(f"🚩 {is_nm} ({ct}회)"):
                    if is_nm in df[df.columns[5]].values: st.write(df[df.iloc[:, 5] == is_nm].iloc[0, 6])

    except Exception as e: st.error(f"⚠️ 오류: {e}")
else: st.info("👈 사이드바에서 엑셀 파일을 업로드해 주세요!")
