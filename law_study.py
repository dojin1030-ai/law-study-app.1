import streamlit as st
import pandas as pd
import random, json, os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="법학암기카드", layout="wide")
st.title("⚖️ 법학암기카드")

# 파일 경로
H_F = "study_history.json"
C_F = "checked_issues.json"
E_F = "ever_checked_issues.json"

def ld_js(p, d):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return d

def sv_js(p, d):
    with open(p, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=4)

# 세션 초기화
if 'his' not in st.session_state: st.session_state.his = ld_js(H_F, {})
if 'chk' not in st.session_state: st.session_state.chk = set(ld_js(C_F, []))
if 'evr' not in st.session_state:
    raw = ld_js(E_F, {})
    st.session_state.evr = {i: 1 for i in raw} if isinstance(raw, list) else raw
if 'pos' not in st.session_state: st.session_state.pos = 0
if 'ans' not in st.session_state: st.session_state.ans = False
if 'rec' not in st.session_state: st.session_state.rec = []

# 핀 주소 생성 함수 (코드 길이 압축용)
def get_pin(r_d):
    pr = str(r_d.iloc[4]) if pd.notna(r_d.iloc[4]) and str(r_d.iloc[4]).lower() != 'nan' else ""
    pa = [str(r_d.iloc[j]) for j in range(1, 4) if pd.notna(r_d.iloc[j]) and str(r_d.iloc[j]).lower() != 'nan']
    return f"📍 {' > '.join(pa)}" + (f" ({pr})" if pr else "")

pin_css = "<span style='font-size:14px; color:gray; font-weight:normal;'>"

# 탭 구성
t1, t2, t3, t4, t5 = st.tabs(["📖 문제 풀기", "📊 학습 리포트", "📑 전체 쟁점 정리", "📌 현재 체크 문제", "🕒 누적 체크 기록"])
up = st.sidebar.file_uploader("엑셀 파일 업로드", type=["csv", "xlsx"])

if up:
    try:
        # 클라우드 배포 시 openpyxl 명시
        if up.name.endswith('.csv'): df = pd.read_csv(up, header=1)
        else: df = pd.read_excel(up, header=1, engine='openpyxl')
        
        df = df.dropna(subset=[df.columns[5], df.columns[6]])
        df[df.columns[5]] = df[df.columns[5]].astype(str).str.strip()
        df.iloc[:, 1] = df.iloc[:, 1].fillna("미분류")
        pts = df.iloc[:, 1].unique()
    except Exception as e:
        st.error(f"오류: {e}")
        st.stop()

    # --- TAB 1: 문제 풀기 ---
    with t1:
        st.sidebar.header("🎯 학습 설정")
        md = st.sidebar.radio("범위", ["전체", "✅ 체크만"])
        sc = st.sidebar.multiselect("편 선택", pts, default=pts)
        fdf = df[df.iloc[:, 1].isin(sc)]
        if md == "✅ 체크만": fdf = fdf[fdf.iloc[:, 5].isin(st.session_state.chk)]
        idx_l = fdf.index.tolist()

        if not idx_l: st.info("해당 조건에 맞는 문제가 없습니다.")
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
            st.caption(get_pin(r))

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
                fb = st.text_input("보완할 점:", key=f"fb_{iss}")
                if st.button("💾 기록 저장"):
                    if iss not in st.session_state.his: st.session_state.his[iss] = []
                    st.session_state.his[iss].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "correct": ans_txt, "my_answer": u_i, "feedback": fb})
                    sv_js(H_F, st.session_state.his); st.success("저장 완료!")

    # --- TAB 2: 학습 리포트 ---
    with t2:
        st.header("📊 누적 학습 리포트")
        t2f = st.multiselect("편 선택 (리포트):", pts, default=pts, key="t2f")
        v_i = [i for i in st.session_state.his.keys() if i in df[df.iloc[:, 1].isin(t2f)][df.columns[5]].unique()]
        if not v_i: st.info("기록이 없습니다.")
        else:
            for nm in v_i:
                mr = df[df.iloc[:, 5] == nm].iloc[0]
                pin = get_pin(mr)
                cl_t, cl_d = st.columns([10, 1])
                with cl_t: st.markdown(f"### 📝 {nm} {pin_css}{pin}</span>", unsafe_allow_html=True)
                with cl_d:
                    if st.button("🗑️", key=f"da_{nm}"):
                        del st.session_state.his[nm]; sv_js(H_F, st.session_state.his); st.rerun()
                for rec in reversed(st.session_state.his[nm]):
                    with st.expander(f"📅 {rec['date']}"):
                        st.write(f"**정답:** {rec['correct']}\n\n**내 답변:** {rec['my_answer']}\n\n**보완:** {rec['feedback']}")
                st.divider()

    # --- TAB 3: 전체 쟁점 정리 ---
    with t3:
        st.header("📑 전체 쟁점 정리")
        t3f = st.multiselect("편 선택 (전체):", pts, default=pts, key="t3f")
        for _, r in df[df.iloc[:, 1].isin(t3f)].iterrows():
            pin = get_pin(r)
            st.markdown(f"### 📌 {r.iloc[5]} {pin_css}{pin}</span>", unsafe_allow_html=True)
            st.write(f"**내용:** {r.iloc[6]}"); st.divider()

    # --- TAB 4: 현재 체크 문제 ---
    with t4:
        st.header("📌 현재 체크 문제")
        for idx, r in df[df.iloc[:, 5].isin(st.session_state.chk)].iterrows():
            iss = r.iloc[5]
            pin = get_pin(r)
            cl_h, cl_b = st.columns([10, 1])
            with cl_h: st.markdown(f"#### ❓ {iss} {pin_css}{pin}</span>", unsafe_allow_html=True)
            with cl_b:
                if st.button("❌", key=f"tu_{iss}_{idx}"):
                    st.session_state.chk.remove(iss); sv_js(C_F, list(st.session_state.chk)); st.rerun()
            st.write(f"**판례:** {r.iloc[6]}"); st.divider()

    # --- TAB 5: 누적 체크 기록 ---
    with t5:
        st.header("🕒 누적 체크 기록")
        cs, cf = st.columns([1, 2])
        so = cs.selectbox("정렬", ["횟수순", "이름순", "랜덤"])
        t5f = cf.multiselect("편 선택 (누적):", pts, default=pts, key="t5f")
        itm = [(k, v) for k, v in st.session_state.evr.items() if k in df[df.iloc[:, 1].isin(t5f)][df.columns[5]].unique()]
        if not itm: st.info("기록이 없습니다.")
        else:
            if so == "횟수순": itm.sort(key=lambda x: x[1], reverse=True)
            elif so == "이름순": itm.sort(key=lambda x: x[0])
            else: random.shuffle(itm)
            for i, (is_nm, ct) in enumerate(itm):
                mr = df[df.iloc[:, 5] == is_nm].iloc[0]
                pin = get_pin(mr)
                ce, cb = st.columns([10, 1])
                with ce:
                    with st.expander(f"🚩 {is_nm} ({ct}회) | {pin}"): st.write(f"**판례:** {mr.iloc[6]}")
                with cb:
                    if st.button("🗑️", key=f"ed_{i}"):
                        del st.session_state.evr[is_nm]; sv_js(E_F, st.session_state.evr); st.rerun()

    st.sidebar.divider()
    st.sidebar.write(f"📊 체크 중: **{len(st.session_state.chk)}개**")
else:
    st.info("좌측 사이드바에서 파일을 업로드하세요.")
