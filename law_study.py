import streamlit as st
import pandas as pd
import random, json, os
from datetime import datetime, timedelta

st.set_page_config(page_title="법학암기카드", layout="wide")
st.title("⚖️ 법학암기카드")

H_F, C_F, E_F = "study_history.json", "checked_issues.json", "ever_checked_issues.json"

def ld_js(p, d):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return d

def sv_js(p, d):
    with open(p, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=4)

if 'his' not in st.session_state: st.session_state.his = ld_js(H_F, {})
if 'chk' not in st.session_state: st.session_state.chk = set(ld_js(C_F, []))
if 'evr' not in st.session_state:
    raw = ld_js(E_F, {})
    st.session_state.evr = {i: 1 for i in raw} if isinstance(raw, list) else raw
if 'pos' not in st.session_state: st.session_state.pos = 0
if 'ans' not in st.session_state: st.session_state.ans = False
if 'rec' not in st.session_state: st.session_state.rec = []

t1, t2, t3, t4, t5 = st.tabs(["📖 문제 풀기", "📊 학습 리포트", "📑 전체 쟁점 정리", "📌 현재 체크 문제", "🕒 누적 체크 기록"])
up = st.sidebar.file_uploader("파일 업로드", type=["csv", "xlsx"])

if up:
    try:
        df = pd.read_csv(up, header=1) if up.name.endswith('.csv') else pd.read_excel(up, header=1)
        # 기본 전처리
        df = df.dropna(subset=[df.columns[5], df.columns[6]])
        df[df.columns[5]] = df[df.columns[5]].astype(str).str.strip()
        df.iloc[:, 1] = df.iloc[:, 1].fillna("미분류")
        
        # K열(날짜) 처리: 날짜 형식이 아니면 나중을 위해 NaT로 처리
        if len(df.columns) >= 11:
            df[df.columns[10]] = pd.to_datetime(df[df.columns[10]], errors='coerce')
        
        pts = df.iloc[:, 1].unique()
    except Exception as e: st.error(f"오류: {e}"); st.stop()

    with t1:
        st.sidebar.header("🎯 학습 설정")
        md = st.sidebar.radio("공부 범위", ["전체", "✅ 체크만"])
        
        # --- 날짜 필터링 추가 ---
        st.sidebar.subheader("📅 복습 필터 (K열 날짜 기준)")
        date_opt = st.sidebar.selectbox("기간 선택", ["전체 기간", "오늘 공부", "최근 3일", "최근 7일", "최근 1달"])
        
        sc = st.sidebar.multiselect("편 선택", pts, default=pts)
        fdf = df[df.iloc[:, 1].isin(sc)]
        
        # 날짜 필터링 로직
        if len(df.columns) >= 11 and date_opt != "전체 기간":
            today = datetime.now().date()
            if date_opt == "오늘 공부":
                target_date = today
            elif date_opt == "최근 3일":
                target_date = today - timedelta(days=3)
            elif date_opt == "최근 7일":
                target_date = today - timedelta(days=7)
            elif date_opt == "최근 1달":
                target_date = today - timedelta(days=30)
            
            # K열 날짜가 target_date 이후인 것만 필터링
            fdf = fdf[fdf[fdf.columns[10]].dt.date >= target_date]

        if md == "✅ 체크만": 
            fdf = fdf[fdf.iloc[:, 5].isin(st.session_state.chk)]
        
        idx_l = fdf.index.tolist()
        
        if not idx_l: 
            st.info("해당 조건(편 + 날짜 + 체크여부)에 맞는 문제가 없습니다. 엑셀 K열에 날짜가 입력되어 있는지 확인해 보세요!")
        else:
            if st.session_state.pos >= len(idx_l): st.session_state.pos = 0
            
            if st.button("🔄 다음 문제"):
                cur = df.loc[idx_l[st.session_state.pos]].iloc[5]
                if cur in st.session_state.rec: st.session_state.rec.remove(cur)
                st.session_state.rec.append(cur)
                if len(st.session_state.rec) > 3: st.session_state.rec.pop(0)
                cd = [i for i in idx_l if df.loc[i].iloc[5] not in st.session_state.rec]
                st.session_state.pos = idx_l.index(random.choice(cd if cd else idx_l))
                st.session_state.ans = False; st.rerun()
                
            r = df.loc[idx_l[st.session_state.pos]]
            iss, ans_txt = r.iloc[5], str(r.iloc[6])
            
            # 날짜 정보 표시 (K열에 데이터가 있을 경우)
            dt_info = ""
            if len(df.columns) >= 11 and pd.notna(r.iloc[10]):
                dt_info = f" | 🗓️ 최근 학습: {r.iloc[10].strftime('%Y-%m-%d')}"
            
            pr = str(r.iloc[4]) if pd.notna(r.iloc[4]) and str(r.iloc[4]).lower() != 'nan' else ""
            pa = [str(r.iloc[i]) for i in range(1, 4) if pd.notna(r.iloc[i]) and str(r.iloc[i]).lower() != 'nan']
            st.caption(f"📍 {' > '.join(pa)}" + (f" ({pr})" if pr else "") + dt_info)
            
            c_q, c_c = st.columns([5, 1])
            with c_q: st.markdown(f"### ❓ 쟁점: {iss}")
            with c_c:
                if st.button("❌ 해제" if iss in st.session_state.chk else "📌 체크"):
                    if iss in st.session_state.chk: st.session_state.chk.remove(iss)
                    else:
                        st.session_state.chk.add(iss)
                        st.session_state.evr[iss] = st.session_state.evr.get(iss, 0) + 1
                        sv_js(E_F, st.session_state.evr)
                    sv_js(C_F, list(st.session_state.chk)); st.rerun()
            
            u_i = st.text_area("워딩 입력:", height=150, key=f"ui_{iss}")
            if st.button("✅ 정답 확인"): st.session_state.ans = True
            if st.session_state.ans:
                c1, c2 = st.columns(2)
                with c1: st.warning("📝 나의 답변"); st.write(u_i if u_i else "없음")
                with c2: st.success("👨‍⚖️ 실제 판례"); st.write(ans_txt)
                fb = st.text_input("보완:", key=f"fb_{iss}")
                if st.button("💾 기록 저장"):
                    if iss not in st.session_state.his: st.session_state.his[iss] = []
                    st.session_state.his[iss].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "correct": ans_txt, "my_answer": u_i, "feedback": fb})
                    sv_js(H_F, st.session_state.his); st.success("저장!")

    # --- 나머지 탭 (동일) ---
    with t2:
        st.header("📊 누적 학습 리포트")
        t2f = st.multiselect("편 선택:", pts, default=pts, key="t2f")
        v_i = [i for i in st.session_state.his.keys() if i in df[df.iloc[:, 1].isin(t2f)][df.columns[5]].unique()]
        if not v_i: st.info("없음")
        else:
            for nm in v_i:
                mr = df[df.iloc[:, 5] == nm].iloc[0]
                pr = str(mr.iloc[4]) if pd.notna(mr.iloc[4]) and str(mr.iloc[4]).lower() != 'nan' else ""
                pa = [str(mr.iloc[j]) for j in range(1, 4) if pd.notna(mr.iloc[j]) and str(mr.iloc[j]).lower() != 'nan']
                pin = f"📍 {' > '.join(pa)}" + (f" ({pr})" if pr else "")
                cl_t, cl_d = st.columns([11, 1])
                with cl_t: st.markdown(f"### 📝 {nm} <span style='font-size:14px; color:gray; font-weight:normal;'>{pin}</span>", unsafe_allow_html=True)
                with cl_d:
                    if st.button("🗑️", key=f"da_{nm}"):
                        del st.session_state.his[nm]; sv_js(H_F, st.session_state.his); st.rerun()
                for rec in reversed(st.session_state.his[nm]):
                    with st.expander(f"📅 {rec['date']}"):
                        st.write(f"**정답:** {rec['correct']}\n\n**내 답변:** {rec['my_answer']}\n\n**보완:** {rec['feedback']}")
                st.divider()

    with t3:
        st.header("📑 전체 쟁점 정리")
        t3f = st.multiselect("편 선택:", pts, default=pts, key="t3f")
        for _, r in df[df.iloc[:, 1].isin(t3f)].iterrows():
            pr = str(r.iloc[4]) if pd.notna(r.iloc[4]) and str(r.iloc[4]).lower() != 'nan' else ""
            pa = [str(r.iloc[i]) for i in range(1, 4) if pd.notna(r.iloc[i]) and str(r.iloc[i]).lower() != 'nan']
            pin = f"📍 {' > '.join(pa)}" + (f" ({pr})" if pr else "")
            st.markdown(f"### 📌 {r.iloc[5]} <span style='font-size:14px; color:gray; font-weight:normal;'>{pin}</span>", unsafe_allow_html=True)
            st.write(f"**내용:** {r.iloc[6]}"); st.divider()

    with t4:
        st.header("📌 현재 체크 문제")
        for idx, r in df[df.iloc[:, 5].isin(st.session_state.chk)].iterrows():
            iss = r.iloc[5]
            pr = str(r.iloc[4]) if pd.notna(r.iloc[4]) and str(r.iloc[4]).lower() != 'nan' else ""
            pa = [str(r.iloc[p]) for p in range(1, 4) if pd.notna(r.iloc[p]) and str(r.iloc[p]).lower() != 'nan']
            pin = f"📍 {' > '.join(pa)}" + (f" ({pr})" if pr else "")
            cl_h, cl_b = st.columns([11, 1])
            with cl_h: st.markdown(f"#### ❓ {iss} <span style='font-size:14px; color:gray; font-weight:normal;'>{pin}</span>", unsafe_allow_html=True)
            with cl_b:
                if st.button("❌", key=f"tu_{iss}_{idx}"):
                    st.session_state.chk.remove(iss); sv_js(C_F, list(st.session_state.chk)); st.rerun()
            st.write(f"**판례:** {r.iloc[6]}"); st.divider()

    with t5:
        st.header("🕒 누적 체크 기록")
        cs, cf = st.columns([1, 2])
        so = cs.selectbox("정렬", ["횟수순", "이름순", "랜덤"])
        t5f = cf.multiselect("편 선택:", pts, default=pts, key="t5f")
        itm = [(k, v) for k, v in st.session_state.evr.items() if k in df[df.iloc[:, 1].isin(t5f)][df.columns[5]].unique()]
        if not itm: st.info("없음")
        else:
            if so == "횟수순": itm.sort(key=lambda x: x[1], reverse=True)
            elif so == "이름순": itm.sort(key=lambda x: x[0])
            else: random.shuffle(itm)
            for i, (is_nm, ct) in enumerate(itm):
                r_d = df[df.iloc[:, 5] == is_nm].iloc[0]
                pin = f"📍 {r_d.iloc[1]} > {r_d.iloc[2]}"
                ce, cb = st.columns([11, 1])
                with ce:
                    with st.expander(f"🚩 {is_nm} ({ct}회) | {pin}"): st.write(f"**판례:** {r_d.iloc[6]}")
                with cb:
                    if st.button("🗑️", key=f"ed_{i}"):
                        del st.session_state.evr[is_nm]; sv_js(E_F, st.session_state.evr); st.rerun()
    st.sidebar.divider(); st.sidebar.write(f"📊 체크: {len(st.session_state.chk)}개")
else: st.info("파일을 업로드하세요.")
