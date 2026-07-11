import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import random
import time

st.set_page_config(page_title="실시간 비행기 레이더", page_icon="✈️", layout="wide")

st.title("✈️ 한반도 실시간 비행기 레이더")
st.write("현재 한반도 상공을 날아다니는 비행기들을 실시간으로 보여줍니다.")
st.info("💡 **지도 조작 꿀팁:** `Shift` 키를 누른 상태로 **왼쪽 마우스**를 드래그하면 지도를 회전/기울일 수 있습니다!")
st.write("🚀 **자동 업데이트:** 30초마다 자동으로 지도가 새로고침 됩니다.") 

# 💡 수정 1: 바보 같은 캐시를 없애고, '성공했을 때만' 세션(Session)에 토큰을 저장하도록 변경!
def get_access_token():
    # 이미 유효한 토큰이 지갑(session_state)에 있다면 그대로 꺼내 씁니다.
    if 'opensky_token' in st.session_state and 'token_expiry' in st.session_state:
        if time.time() < st.session_state['token_expiry']:
            return st.session_state['opensky_token'], None

    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    try:
        OPENSKY_CLIENT_ID = st.secrets["OPENSKY_CLIENT_ID"]
        OPENSKY_CLIENT_SECRET = st.secrets["OPENSKY_CLIENT_SECRET"]
    except KeyError:
        return None, "보안 키(Secrets)가 설정되지 않았습니다."

    try:
        response = requests.post(
            token_url, 
            data={"grant_type": "client_credentials", "client_id": OPENSKY_CLIENT_ID, "client_secret": OPENSKY_CLIENT_SECRET},
            timeout=10 
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            # 💡 발급 성공! 지갑에 30분(1800초) 동안 보관합니다.
            st.session_state['opensky_token'] = token
            st.session_state['token_expiry'] = time.time() + 1800 
            return token, None
        else:
            return None, f"토큰 발급 실패 ({response.status_code})"
    except Exception as e:
        return None, f"토큰 발급 통신 에러: {e}"

def get_mock_data():
    mock_flights = [
        {"callsign": "KOR123", "longitude": 126.9780, "latitude": 37.5665, "baro_altitude": 5000, "origin_country": "South Korea", "true_track": 45},
        {"callsign": "ASIANA45", "longitude": 129.0756, "latitude": 35.1795, "baro_altitude": 8000, "origin_country": "South Korea", "true_track": 120},
        {"callsign": "JEJU77", "longitude": 126.5219, "latitude": 33.4996, "baro_altitude": 3000, "origin_country": "South Korea", "true_track": 10},
        {"callsign": "JAPAN88", "longitude": 130.0, "latitude": 36.5, "baro_altitude": 10000, "origin_country": "Japan", "true_track": 270},
        {"callsign": "USA99", "longitude": 125.0, "latitude": 36.0, "baro_altitude": 12000, "origin_country": "United States", "true_track": 180}
    ]
    return pd.DataFrame(mock_flights)

def load_data():
    url = "https://opensky-network.org/api/states/all"
    params = {"lamin": 33.0, "lomin": 124.0, "lamax": 39.0, "lomax": 132.0}
    
    token, token_err = get_access_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if not token:
        return get_mock_data(), token_err
        
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            states = data.get('states')
            
            # 💡 수정 2: 데이터가 텅 비어있을 때(None) 시연용 데이터로 완벽하게 튕겨내기!
            if states is not None and len(states) > 0:
                columns = [
                    'icao24', 'callsign', 'origin_country', 'time_position', 
                    'last_contact', 'longitude', 'latitude', 'baro_altitude', 
                    'on_ground', 'velocity', 'true_track', 'vertical_rate', 
                    'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source'
                ]
                df = pd.DataFrame(states, columns=columns)
                df_clean = df[['callsign', 'longitude', 'latitude', 'baro_altitude', 'origin_country', 'true_track']]
                df_clean = df_clean.dropna(subset=['longitude', 'latitude'])
                df_clean['baro_altitude'] = df_clean['baro_altitude'].fillna(0)
                df_clean['true_track'] = df_clean['true_track'].apply(lambda x: random.randint(0, 360) if pd.isna(x) else x)
                return df_clean, None
            else:
                return get_mock_data(), "현재 한반도 상공에 잡히는 비행기가 없거나 서버가 데이터를 주지 않았습니다."
        else:
            return get_mock_data(), f"서버 거절 ({response.status_code})"
    except Exception as e:
        return get_mock_data(), f"통신 초과: {e}"

@st.fragment(run_every="30s")
def radar_screen():
    loading_text = st.empty()
    loading_text.caption("🔄 하늘에서 비행기 정보를 가져오는 중...")
    
    flight_data, error_msg = load_data()
    loading_text.empty() 

    if error_msg:
        st.error(f"🚨 실시간 데이터 연결 실패: {error_msg}")
        st.warning("💡 대신 [시연용 예시 데이터]를 띄웠습니다! 방향 지시 아이콘이 어떻게 작동하는지 확인해 보세요.")

    if not flight_data.empty:
        if not error_msg:
            st.success(f"성공! 현재 {len(flight_data)}대의 비행기를 추적 중입니다.")
        
        flight_data['icon'] = '▲' 
        flight_data['angle'] = flight_data['true_track']
        
        layer = pdk.Layer(
            "TextLayer",
            data=flight_data,
            get_position="[longitude, latitude]",
            get_text="icon",        
            get_size=25,            
            get_color="[255, 75, 75]", 
            get_angle="angle",      
            pickable=True,
        )
        
        view_state = pdk.ViewState(latitude=36.0, longitude=128.0, zoom=5.5, pitch=45)
        
        tooltip = {
            "html": "<b>비행기:</b> {callsign} <br/> <b>고도:</b> {baro_altitude} m <br/> <b>방향:</b> {true_track} 도 <br/> <b>국가:</b> {origin_country}",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }
        
        r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip)
        st.pydeck_chart(r)
        
    else:
        st.error("데이터를 화면에 그릴 수 없습니다.")

radar_screen()
