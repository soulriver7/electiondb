import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="지방선거 투표 현황 트래커", layout="wide")

ballot_types = [
    "부산시교육감", 
    "부산시장", 
    "해운대구청장", 
    "부산시의원", 
    "해운대구의원", 
    "(비례대표)부산시의원"
]

conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 사이드바: 관리자 사전 세팅
# ==========================================
with st.sidebar:
    st.header("⚙️ 관리자 사전 설정")
    
    settings_dict = {}
    try:
        # 🚨 수정: 설정값은 자주 안 바뀌므로 10분(600초) 동안 캐시 유지
        settings_df = conn.read(worksheet="설정", ttl=600)
        if not settings_df.empty and "항목" in settings_df.columns and "값" in settings_df.columns:
            settings_dict = dict(zip(settings_df["항목"], settings_df["값"]))
    except Exception:
        pass 
        
    def get_saved_val(key, default_val):
        try:
            return int(settings_dict.get(key, default_val))
        except:
            return default_val

    TOTAL_BALLOTS = st.number_input(
        "총 투표지 매수 (각 투표지별)", 
        min_value=1, 
        value=get_saved_val("총매수", 2400),
        step=100
    )
    st.success(f"현재 설정: 각 **{TOTAL_BALLOTS}**장")
    
    st.divider()
    
    st.subheader("📌 투표지별 시작번호 세팅")
    start_numbers = {} 
    
    for b_type in ballot_types:
        start_numbers[b_type] = st.number_input(
            f"{b_type} 시작번호", 
            min_value=1, 
            value=get_saved_val(b_type, 1000), 
            step=1, 
            key=f"side_start_{b_type}"
        )
        
    st.write("---")
    if st.button("💾 위 설정값을 DB에 영구 저장", type="primary"):
        new_settings = {
            "항목": ["총매수"] + ballot_types,
            "값": [TOTAL_BALLOTS] + list(start_numbers.values())
        }
        new_settings_df = pd.DataFrame(new_settings)
        
        try:
            conn.update(worksheet="설정", data=new_settings_df)
            st.cache_data.clear() # 저장 시 캐시 초기화
            st.success("✅ 설정이 구글 시트에 안전하게 저장되었습니다!")
        except Exception as e:
            st.error(f"저장 실패: ({e})")

# ==========================================
# 메인 화면
# ==========================================
st.subheader("🗳️ 반여1동 제7투 투표 현황")

tab1, tab2, tab3 = st.tabs(["📝 투표 현황 입력", "📊 직관적 투표 현황", "🛠️ 데이터 수정 및 초기화"])

# ==========================================
# 탭 1: 투표 현황 입력 및 DB 저장
# ==========================================
with tab1:
    st.write("각 투표지별 현황과 제외(오기/훼손) 번호를 입력해주세요.")
    
    latest_row = None
    try:
        # 🚨 수정: 입력 시 타이핑 횟수만큼 호출되는 것을 막기 위해 10초(ttl=10) 캐시 적용
        latest_data_df = conn.read(worksheet="Sheet1", ttl=10)
        if not latest_data_df.empty and "시간" in latest_data_df.columns:
            latest_row = latest_data_df.sort_values(by="시간").iloc[-1]
    except Exception:
        pass 

    results = {}
    exclusion_reasons = {}
    current_numbers_to_save = {} 
    
    with st.form("voting_form"):
        for i in range(0, len(ballot_types), 3):
            cols = st.columns(3)
            
            for j in range(3):
                if i + j < len(ballot_types):
                    b_type = ballot_types[i + j]
                    with cols[j]:
                        st.subheader(f"📄 {b_type}")
                        
                        start = start_numbers[b_type]
                        st.number_input(f"시작 번호 (수정불가)", value=start, disabled=True, key=f"main_start_{b_type}")
                        
                        default_current = start
                        current_key = f"{b_type}_현재번호"
                        if latest_row is not None and current_key in latest_row:
                            saved_val = latest_row[current_key]
                            if pd.notna(saved_val): 
                                default_current = int(saved_val)
                                
                        current = st.number_input(f"현재 맨 위 번호", min_value=1, value=default_current, key=f"{b_type}_current")
                        
                        ex_text = st.text_input(
                            f"제외 번호/사유 (쉼표 구분)", 
                            placeholder="ex: 1015, 1020(오기)", 
                            key=f"{b_type}_ex_text"
                        )
                        
                        if ex_text.strip():
                            excluded_list = [x.strip() for x in ex_text.split(',') if x.strip()]
                            excluded_count = len(excluded_list)
                        else:
                            excluded_count = 0
                        
                        if current >= start:
                            used_papers = current - start 
                            voter_count = used_papers - excluded_count 
                            remaining_papers = TOTAL_BALLOTS - used_papers 
                        else:
                            voter_count = 0
                            remaining_papers = TOTAL_BALLOTS
                            
                        st.info(f"""
                        👉 **투표자:** {voter_count}명 (제외 {excluded_count}장)  
                        📦 **남은 투표지:** {remaining_papers}장
                        """)
                        
                        results[b_type] = voter_count
                        exclusion_reasons[f"{b_type}_제외사유"] = ex_text
                        current_numbers_to_save[current_key] = current 
                        st.divider()

        submit_button = st.form_submit_button(label="💾 투표 현황 DB에 저장 (정합성 무관하게 저장됨)")

    if submit_button:
        KST = timezone(timedelta(hours=9))
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        
        new_data = {"시간": now}
        new_data.update(results)
        new_data.update(exclusion_reasons)
        new_data.update(current_numbers_to_save) 
        
        new_df = pd.DataFrame([new_data])
        
        try:
            # 🚨 주의: 버튼을 눌러서 실제 저장할 때는 데이터 충돌을 막기 위해 무조건 최신 데이터를 읽어야 하므로 ttl=0 유지
            existing_data = conn.read(worksheet="Sheet1", ttl=0)
            if existing_data.empty:
                updated_data = new_df
            else:
                updated_data = pd.concat([existing_data.dropna(how='all'), new_df], ignore_index=True)
            
            conn.update(worksheet="Sheet1", data=updated_data)
            st.cache_data.clear() # 저장 직후 모든 캐시 삭제하여 새로고침 시 새 데이터 반영되게 함
            
            voter_counts = list(results.values())
            if len(set(voter_counts)) == 1:
                st.balloons()
                st.success(f"✅ 데이터 저장 완료 및 정합성 완벽 일치! (현재 {voter_counts[0]}명)")
            else:
                st.warning("⚠️ 데이터는 정상적으로 저장되었습니다. (단, 현재 1교부처와 2교부처의 투표자 수가 다릅니다. 점검 시 확인하세요.)")
            
            st.rerun()
                
        except Exception as e:
            st.error(f"DB 저장 오류: {e}")

# ==========================================
# 탭 2: 시간별 투표 현황 (직관적 대시보드)
# ==========================================
with tab2:
    st.subheader("📈 시간별 누적 투표자 추이 (부산시장 기준)")
    if st.button("🔄 데이터 최신화", key="refresh_tab2"):
        st.cache_data.clear()
        
    try:
        # 🚨 수정: 10초 캐시 유지 (타이핑 시마다 호출 방지)
        df = conn.read(worksheet="Sheet1", ttl=10)
        if not df.empty and "부산시장" in df.columns:
            df['시간'] = pd.to_datetime(df['시간'])
            df = df.sort_values(by="시간", ascending=True) 
            
            latest_voters = df.iloc[-1]["부산시장"] 
            st.metric(label="현재 총 투표자 수", value=f"{latest_voters} 명")
            
            st.divider()
            
            df['시간_표시'] = df['시간'].dt.strftime('%H:%M')
            chart_data = df.set_index("시간_표시")[["부산시장"]]
            st.line_chart(chart_data)
        else:
            st.info("입력된 데이터가 없습니다.")
    except Exception as e:
        st.error(f"오류: {e}")

# ==========================================
# 탭 3: 데이터 수정 및 초기화 (관리자용)
# ==========================================
with tab3:
    st.subheader("🛠️ 구글 시트 데이터 수정")
    st.write("아래 표의 셀을 더블클릭하여 내용을 직접 수정하거나, 행을 선택해 지울 수 있습니다.")
    
    try:
        # 🚨 수정: 10초 캐시 유지
        edit_df = conn.read(worksheet="Sheet1", ttl=10)
        if not edit_df.empty and "시간" in edit_df.columns:
            edit_df = edit_df.sort_values(by="시간", ascending=False).reset_index(drop=True)
            edited_df = st.data_editor(edit_df, num_rows="dynamic", width="stretch", key="data_editor")
            
            if st.button("💾 수정된 데이터 DB에 반영하기"):
                conn.update(worksheet="Sheet1", data=edited_df)
                st.cache_data.clear()
                st.success("수정 사항이 성공적으로 구글 시트에 반영되었습니다!")
                st.rerun()
        else:
            st.info("수정할 데이터가 없습니다.")
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")

    st.divider()
    
    st.subheader("⚠️ 데이터 전체 초기화 (리셋)")
    st.warning("선거 전 테스트용으로 입력한 데이터를 모두 지울 때 사용하세요. 이 작업은 되돌릴 수 없습니다!")
    
    confirm_delete = st.checkbox("네, 모든 데이터를 삭제하는 것에 동의합니다.")
    
    if st.button("🗑️ 전체 데이터 삭제 (실행)", type="primary", disabled=not confirm_delete):
        try:
            empty_df = pd.DataFrame(columns=["시간"]) 
            conn.update(worksheet="Sheet1", data=empty_df)
            st.cache_data.clear()
            st.success("데이터가 완벽하게 초기화되었습니다. 새롭게 입력을 시작하세요!")
            st.rerun()
        except Exception as e:
            st.error(f"초기화 중 오류가 발생했습니다: {e}")