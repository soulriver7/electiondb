import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="🗳️ 반여1동 제7투 투표 현황", layout="wide")

# 투표지 6종류 정의
ballot_types = ["부산시교육감", "부산시장", "해운대구청장", "부산시의원", "해운대구의원", "(비례대표)부산시의원"]

# ==========================================
# 사이드바: 관리자 사전 세팅
# ==========================================
with st.sidebar:
    st.header("⚙️ 관리자 사전 설정")
    
    # 1. 총 투표지 매수
    TOTAL_BALLOTS = st.number_input("총 투표지 매수 (각 투표지별)", min_value=1, value=2400, step=100)
    st.success(f"현재 설정: 각 **{TOTAL_BALLOTS}**장")
    
    st.divider()
    
    # 2. 투표지별 시작 번호 세팅
    st.subheader("📌 투표지별 시작번호 세팅")
    start_numbers = {} # 세팅된 시작 번호를 저장할 딕셔너리
    
    for b_type in ballot_types:
        # 사이드바에서 입력받은 값을 start_numbers 딕셔너리에 저장
        start_numbers[b_type] = st.number_input(
            f"{b_type} 시작번호", 
            min_value=1, 
            value=1000, 
            step=1, 
            key=f"side_start_{b_type}"
        )

# 메인 타이틀 (글씨 크기 축소를 위해 st.header 사용)
st.header("🗳️ 반여1동 제7투 투표 현황")

# 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 탭 3개로 분리
tab1, tab2, tab3 = st.tabs(["📝 투표 현황 입력", "📊 시간별 투표 현황", "🛠️ 데이터 수정 및 초기화"])

# ==========================================
# 탭 1: 투표 현황 입력 및 DB 저장
# ==========================================
with tab1:
    st.write("각 투표지별 현황과 제외(오기/훼손) 번호를 입력해주세요.")
    
    results = {}
    exclusion_reasons = {}
    
    with st.form("voting_form"):
        cols = st.columns(3)
        
        for i, b_type in enumerate(ballot_types):
            with cols[i % 3]:
                st.subheader(f"📄 {b_type}")
                
                # 사이드바에서 설정한 시작 번호를 가져옴
                start = start_numbers[b_type]
                
                # disabled=True 를 사용하여 메인화면에서는 수정 불가(읽기 전용)로 만듦
                st.number_input(f"시작 번호 (수정불가)", value=start, disabled=True, key=f"main_start_{b_type}")
                
                # 현재 맨 위 번호 입력 (이것만 사무원들이 입력)
                current = st.number_input(f"현재 맨 위 번호", min_value=1, value=start, key=f"{b_type}_current")
                
                ex_text = st.text_input(
                    f"제외 번호/사유 (쉼표 구분)", 
                    placeholder="ex: 1015, 1020(오기)", 
                    key=f"{b_type}_ex_text"
                )
                
                # 제외 매수 계산
                if ex_text.strip():
                    excluded_list = [x.strip() for x in ex_text.split(',') if x.strip()]
                    excluded_count = len(excluded_list)
                else:
                    excluded_count = 0
                
                # 투표자 수 및 남은 투표지 계산
                if current >= start:
                    used_papers = current - start # 배부된 총 투표지(오기 포함)
                    voter_count = used_papers - excluded_count # 순수 투표자 수
                    remaining_papers = TOTAL_BALLOTS - used_papers # 남은 투표지 수
                else:
                    voter_count = 0
                    remaining_papers = TOTAL_BALLOTS
                    
                # 추산 정보 표시
                st.info(f"""
                👉 **투표자:** {voter_count}명 (제외 {excluded_count}장)  
                📦 **남은 투표지:** {remaining_papers}장
                """)
                
                results[b_type] = voter_count
                exclusion_reasons[f"{b_type}_제외사유"] = ex_text
                st.divider()

        submit_button = st.form_submit_button(label="정합성 검사 및 DB에 저장")

    if submit_button:
        voter_counts = list(results.values())
        if len(set(voter_counts)) == 1:
            st.success(f"✅ 정합성 통과! (현재 투표자 {voter_counts[0]}명)")
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_data = {"시간": now}
            new_data.update(results)
            new_data.update(exclusion_reasons)
            
            new_df = pd.DataFrame([new_data])
            
            try:
                existing_data = conn.read(worksheet="Sheet1", ttl=0)
                if existing_data.empty:
                    updated_data = new_df
                else:
                    updated_data = pd.concat([existing_data.dropna(how='all'), new_df], ignore_index=True)
                
                conn.update(worksheet="Sheet1", data=updated_data)
                st.cache_data.clear()
                st.balloons()
                st.success("데이터가 저장되었습니다!")
            except Exception as e:
                st.error(f"DB 저장 오류: {e}")
        else:
            st.error("❌ 정합성 오류: 투표지별 인원수가 다릅니다.")
            for k, v in results.items():
                st.write(f"- {k}: {v}명")

# ==========================================
# 탭 2: 시간별 투표 현황 (대시보드)
# ==========================================
with tab2:
    st.subheader("📈 시간별 투표 진행 현황")
    if st.button("🔄 데이터 최신화", key="refresh_tab2"):
        st.cache_data.clear()
        
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        if not df.empty and "시간" in df.columns:
            chart_data = df.set_index("시간")[ballot_types]
            st.line_chart(chart_data)
            
            st.markdown("##### 📋 상세 집계 내역")
            display_df = df.sort_values(by="시간", ascending=False).reset_index(drop=True)
            st.dataframe(display_df, width="stretch")
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
        edit_df = conn.read(worksheet="Sheet1", ttl=0)
        if not edit_df.empty and "시간" in edit_df.columns:
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