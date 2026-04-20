import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import random, json, os
from datetime import datetime, timedelta

# [1] 페이지 설정
st.set_page_config(page_title="법학암기 (Cloud Sync)", layout="wide")
st.title("⚖️ 법학암기카드 (Stable Build)")

# [2] 구글 시트 연결
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"❌ 구글 시트 연결 설정(Secrets) 확인 필요: {e}")
    st.stop()

# [3] 데이터 로드 및 저장 함수
def load_gsheets_data():
    h_df, c_df, e_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try: h_df = conn.read(worksheet="History", ttl="0")
    except: pass
    try: c_df = conn.read(worksheet="Checked", ttl="0")
    except: pass
    try: e_df = conn.read(worksheet="EverChecked", ttl="0")
    except: pass
    return h_df, c_df, e_df

def save_to_gsheets(df, sheet_name):
    try: conn.update(worksheet=sheet_name, data=df)
    except Exception as e: st.error(f"❌ '{sheet_name}' 저장 실패: {e}")

# [4] 세션 상태 초기화 (NameError 완벽 방어)
if 'init' not in st.session_state:
    h, c, e = load_gsheets_data()
    st.session_state.his = h if not h.empty else pd.DataFrame(columns=["date", "issue", "correct", "my_answer", "feedback"])
    st.session_state.chk = set(c['issue'].tolist()) if (not c.empty and 'issue' in c.columns) else set()
    st.session_state.evr = e.set_index('issue')['count'].to_dict() if (not e.empty and 'issue' in e.columns) else {}
    st.session_state.init = True

if 'cur_iss' not in st.session_state: st.session_state.cur_iss = ""
if 'cur_ans' not in st.session_state: st.session_state.cur_ans = ""
if 'cur_pin' not in st.session_state: st.session_state.cur_pin = ""
if 'pos' not in st.session_state: st.session_state.pos = 0
if 'ans_visible' not in st.session_state: st.session_state.ans_visible = False
if 'rec' not in st.session_state: st.session_state.rec = []

# [5] 메인 UI 구성
t1, t2, t3, t4, t5 = st.tabs(["📖 문제 풀기", "📊 학습 리포트", "📑 전체 쟁점 정리", "📌 현재 체크 문제", "🕒 누적 체크 기록"])
up = st.sidebar.file_uploader("엑셀 파일 업로드", type=["csv", "xlsx"])

if up:
    try:
        if up.name.endswith('.csv'): df = pd.read_csv(up, header=1)
        else: df = pd.read_excel(up, header=1, engine='openpyxl')
        
        # --- [철갑 전처리 시작] ---
        # 1. 쟁점/판례 없는 행은 삭제
        df = df.dropna(subset=[df.columns[5], df.columns[6]])
        
        # 2. 편/절 빈칸 처리 및 문자열 고정 (Sorting 에러 원천 차단)
        df.iloc[:, 1] = df.iloc[:, 1].fillna('미분류').astype(str).str.strip()
        df.iloc[:, 2] = df.iloc[:, 2].fillna('일반').astype(str).str.strip()
        
        # 3. 쟁점명(조문) 포맷팅
        def get_format_iss(row):
            iss = str(row.iloc[5]).strip()
            art = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) and str(row.iloc[4]).lower() != 'nan' else ""
            return f"{iss}({art})" if art else iss
        df[df.columns[5]] = df.apply(get_format_iss, axis=1)
        
        if len(df.columns) >= 11:
            df[df.columns[10]] = pd.to_datetime(df[df.columns[10]], errors='coerce')
        
        all_parts = sorted(df.iloc[:, 1].unique())
        # --- [철갑 전처리 끝] ---

        # [TAB 1] 문제 풀기 (본질)
        with t1:
            st.sidebar.header("🎯 학습 설정")
            md = st.sidebar.radio("범위", ["전체", "✅ 체크만"])
            dt_opt = st.sidebar.selectbox("기간 선택", ["전체 기간", "오늘 공부", "최근 3일", "최근 7일", "최근 1달"])
            sc_parts = st.sidebar.multiselect("편 선택", all_parts, default=all_parts)
            
            fdf = df[df.iloc[:, 1].isin(sc_parts)]
            if len(df.columns) >= 11 and dt_opt != "전체 기간":
                gap = {"오늘 공부": 0, "최근 3일": 3, "최근 7일": 7, "최근 1달": 30}[dt_opt]
                target = datetime.now().date() - timedelta(days=gap)
                fdf = fdf[fdf[fdf.columns[10]].dt.date >= target]
            if md == "✅ 체크만": fdf = fdf[fdf.iloc[:, 5].isin(st.session_state.chk)]
            
            idx_l = fdf.index.tolist()
            if not idx_l: st.info("문제가 없습니다. 조건을 확인해 주세요!")
            else:
                if st.session_state.pos >= len(idx_l): st.session_state.pos = 0
                if st.button("🔄 다음 문제") or st.session_state.cur_iss == "":
                    cd = [i for i in idx_l if df.loc[i].iloc[5] not in st.session_state.rec]
                    st.session_state.pos = idx_l.index(random.choice(cd if cd else idx_l))
                    r = df.loc[idx_l[st.session_state.pos]]
                    st.session_state.cur_iss = r.iloc[5]
                    st.session_state.cur_ans = str(r.iloc[6])
                    pa = [str(r.iloc[i]) for i in range(1, 4) if pd.notna(r.iloc[i]) and str(r.iloc[i]).lower() != 'nan']
                    dt_txt = f" | 🗓️ {r.iloc[10].strftime('%Y-%m-%d')}" if len(df.columns) >= 11 and pd.notna(r.iloc[10]) else ""
                    st.session_state.cur_pin = f"📍 {' > '.join(pa)}{dt_txt}"
                    if st.session_state.cur_iss in st.session_state.rec: st.session_state.rec.remove(st.session_state.cur_iss)
                    st.session_state.rec.append(st.session_state.cur_iss)
                    if len(st.session_state.rec) > 3: st.session_state.rec.pop(0)
                    st.session_state.ans_visible = False; st.rerun()

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
                        save_to_gsheets(pd.DataFrame(list(st.session_state.chk), columns=['issue']), "Checked"); st.rerun()
                
                # 답변 입력 및 정답 확인 (복구됨)
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
                        save_to_gsheets(st.session_state.his, "History"); st.success("✅ 저장 완료!")

        # [TAB 2 & 3] 계층형 구조 (편 > 절 > 쟁점)
        for tab_obj, title, is_history in [(t2, "📊 학습 리포트", True), (t3, "📑 전체 쟁점 정리", False)]:
            with tab_obj:
                st.header(title)
                sel_p = st.multiselect(f"1. 편 선택 ({title})", all_parts, key=f"p_sel_{title}")
                if sel_p:
                    rel_sects = sorted(df[df.iloc[:, 1].isin(sel_p)].iloc[:, 2].unique())
                    sel_s = st.multiselect(f"2. 절 선택 ({title})", rel_sects, default=rel_sects, key=f"s_sel_{title}")
                    st.divider()
                    for p in sel_p:
                        with st.expander(f"📁 {p}", expanded=True):
                            p_df = df[(df.iloc[:, 1] == p) & (df.iloc[:, 2].isin(sel_s))]
                            for s in sorted(p_df.iloc[:, 2].unique()):
                                st.markdown(f"#### 📑 {s}")
                                s_df = p_df[p_df.iloc[:, 2] == s]
                                for _, r in s_df.iterrows():
                                    iss = r.iloc[5]
                                    if is_history:
                                        if iss in st.session_state.his['issue'].values:
                                            with st.container():
                                                c_t, c_d = st.columns([10, 1])
                                                c_t.write(f"**📌 {iss}**")
                                                if c_d.button("🗑️", key=f"del_{title}_{iss}"):
                                                    st.session_state.his = st.session_state.his[st.session_state.his['issue'] != iss]
                                                    save_to_gsheets(st.session_state.his, "History"); st.rerun()
                                                recs = st.session_state.his[st.session_state.his['issue'] == iss]
                                                for _, row in recs.iloc[::-1].iterrows():
                                                    st.caption(f"📅 {row['date']} | {row['feedback']}")
                                    else:
                                        with st.expander(f"🔍 {iss}"): st.write(f"**내용:** {r.iloc[6]}")
                                st.write("")

        # [TAB 4 & 5] 체크 및 누적 기록
        with t4:
            st.header("📌 현재 체크 문제")
            c_df = df[df.iloc[:, 5].isin(st.session_state.chk)]
            for idx, r in c_df.iterrows():
                st.markdown(f"#### ❓ {r.iloc[5]} (📍 {r.iloc[1]} > {r.iloc[2]})")
                st.write(f"**판례:** {r.iloc[6]}"); st.divider()
        with t5:
            st.header("🕒 누적 체크 기록")
            for is_nm, ct in st.session_state.evr.items():
                with st.expander(f"🚩 {is_nm} ({ct}회)"):
                    if is_nm in df[df.columns[5]].values:
                        st.write(df[df.iloc[:, 5] == is_nm].iloc[0, 6])
                    else: st.write("데이터가 없습니다.")

    except Exception as e: st.error(f"⚠️ 오류 발생: {e}")
else: st.info("👈 사이드바에서 엑셀 파일을 업로드해 주세요!")
