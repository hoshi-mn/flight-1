import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import time # [추가] 기다리는 시간을 설정하기 위해 필요해요

# 1. 스트림릿 웹앱 기본 설정 (가장 위에 있어야 합니다)
st.set_page_config(page_title="실시간 비행기 레이더", page_icon="✈️", layout="wide")

st.title("✈️ 한반도 실시간 비행기 레이더")
st.write("현재 한반도 상공을 날아다니는 비행기들을 실시간으로 보여줍니다.")

@st.cache_data(ttl=3000, show_spinner=False)
def get_access_token():
    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    try:
        response = requests.post(
            token_url, 
            data={
                "grant_type": "client_credentials",
                "client_id": "skyhoshi-api-client",
                "client_secret": "jTZFKzgXnNXOglF7F8FCnlDTW6Nxx0rz"
            },
            timeout=10 
        )
        if response.status_code == 200:
            return response.json().get("access_token"), None
        else:
            return None, f"토큰 발급 실패 (코드: {response.status_code})"
    except Exception as e:
        return None, f"토큰 발급 통신 에러: {e}"

# 2. 실시간 데이터를 위해 캐시(cache)를 제거합니다. 
def load_data():
    url = "https://opensky-network.org/api/states/all"
    params = {
        "lamin": 33.0, "lomin": 124.0, 
        "lamax": 39.0, "lomax": 132.0
    }
    
    token, token_err = get_access_token()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        return pd.DataFrame(), token_err
        
    try:
        # 15초 동안 끈기 있게 기다립니다.
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            states = data.get('states')
            if states:
                columns = [
                    'icao24', 'callsign', 'origin_country', 'time_position', 
                    'last_contact', 'longitude', 'latitude', 'baro_altitude', 
                    'on_ground', 'velocity', 'true_track', 'vertical_rate', 
                    'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source'
                ]
                df = pd.DataFrame(states, columns=columns)
                
                df_clean = df[['callsign', 'longitude', 'latitude', 'baro_altitude', 'origin_country']]
                df_clean = df_clean.dropna(subset=['longitude', 'latitude'])
                return df_clean, None
            else:
                return pd.DataFrame(), "현재 한반도 상공에 잡히는 비행기가 없습니다."
        else:
            return pd.DataFrame(), f"서버 거절 (상태 코드: {response.status_code})"
    except Exception as e:
        return pd.DataFrame(), f"통신 차단 또는 시간 초과 (구글 코랩 환경 차단 의심): {e}"

# 3. 화면 UI 및 자동 새로고침(루프) 로직
col1, col2 = st.columns([3, 1])
with col1:
    st.write("🚀 **자동 업데이트 모드**가 켜져 있으면, 연결될 때까지 끈기 있게 계속 시도합니다!")
with col2:
    # 토글 스위치로 자동 새로고침 켜고 끄기
    auto_refresh = st.toggle("자동 업데이트", value=True)

with st.spinner("하늘에서 비행기 정보를 가져오는 중..."):
    flight_data, error_msg = load_data()

# [중요] 중복 에러 해결: 버튼마다 고유한 'key' 이름을 붙여줍니다.
if st.button("🔄 즉시 새로고침", key="refresh_top"):
    st.rerun()

# 4. 지도 출력 로직
if not flight_data.empty:
    st.success(f"성공! 현재 {len(flight_data)}대의 비행기가 날고 있어요.")
    
    # [Pydeck] 1. 지도 위에 그릴 비행기 점(Layer) 설정
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=flight_data,
        get_position="[longitude, latitude]",
        get_radius=3000,             # 점의 크기 (반경 3000m)
        get_fill_color="[255, 75, 75]",  # 점의 색깔 (빨간색, RGB 형태)
        pickable=True,               # 마우스를 올렸을 때 상호작용 가능하게 설정
    )
    
    # [Pydeck] 2. 지도를 처음 켰을 때 바라볼 위치와 각도 설정
    view_state = pdk.ViewState(
        latitude=36.0, 
        longitude=128.0, 
        zoom=5.5, 
        pitch=45 # 지도를 45도 기울여서 입체감(3D)을 줍니다.
    )
    
    # [Pydeck] 3. 마우스를 비행기에 올렸을 때 나타날 말풍선(Tooltip) 설정
    tooltip = {
        "html": "<b>비행기 이름:</b> {callsign} <br/> <b>고도:</b> {baro_altitude} m <br/> <b>출발 국가:</b> {origin_country}",
        "style": {"backgroundColor": "steelblue", "color": "white", "font-family": "sans-serif"}
    }
    
    # 위에서 설정한 3가지를 조립해서 지도를 완성합니다.
    r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip)
    
    # 스트림릿 화면에 지도를 짠! 하고 출력
    st.pydeck_chart(r)
    
    # 하단에 데이터 표도 같이 보여주기
    st.subheader("📋 상세 비행기 데이터")
    st.dataframe(flight_data)
    
    # 데이터 불러오기 성공 후 지속 업데이트
    if auto_refresh:
        time.sleep(15) # 15초 동안 지도를 볼 수 있게 대기
        st.rerun() # 15초 뒤에 알아서 새로고침!
    
else:
    st.warning("데이터를 가져오지 못했습니다. 아래 상세 원인을 확인해주세요.")
    st.error(f"🚨 에러 상세 내용: {error_msg}")
    
    # 데이터 불러오기 실패 시 계속 재시도
    if auto_refresh:
        st.info("5초 뒤에 자동으로 다시 시도합니다...")
        time.sleep(5) # 5초 대기
        st.rerun() # 5초 뒤에 다시 시도!
    
# 화면 하단 새로고침 버튼 (위 버튼과 다른 key를 사용해야 에러가 안 납니다)
st.write("---")
if st.button("🔄 즉시 새로고침", key="refresh_bottom"):
    st.rerun()
