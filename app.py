import streamlit as st
import pandas as pd
import pydeck as pdk
import requests

# 1. 스트림릿 웹앱 기본 설정
st.set_page_config(page_title="실시간 비행기 레이더", page_icon="✈️", layout="wide")

st.title("✈️ 한반도 실시간 비행기 레이더")
st.write("현재 한반도 상공을 날아다니는 비행기들을 실시간으로 보여줍니다.")

def get_access_token():
    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    
    try:
        OPENSKY_CLIENT_ID = st.secrets["OPENSKY_CLIENT_ID"]
        OPENSKY_CLIENT_SECRET = st.secrets["OPENSKY_CLIENT_SECRET"]
    except KeyError:
        return None, "보안 키(Secrets)가 설정되지 않았습니다."

    try:
        response = requests.post(
            token_url, 
            data={
                "grant_type": "client_credentials",
                "client_id": OPENSKY_CLIENT_ID,
                "client_secret": OPENSKY_CLIENT_SECRET
            },
            timeout=10 
        )
        if response.status_code == 200:
            return response.json().get("access_token"), None
        else:
            return None, f"토큰 발급 실패 (코드: {response.status_code})"
    except Exception as e:
        return None, f"토큰 발급 통신 에러: {e}"

# 가짜 시연용 데이터를 만드는 함수
def get_mock_data():
    mock_flights = [
        {"callsign": "KOR123", "longitude": 126.9780, "latitude": 37.5665, "baro_altitude": 5000, "origin_country": "South Korea"},
        {"callsign": "ASIANA45", "longitude": 129.0756, "latitude": 35.1795, "baro_altitude": 8000, "origin_country": "South Korea"},
        {"callsign": "JEJU77", "longitude": 126.5219, "latitude": 33.4996, "baro_altitude": 3000, "origin_country": "South Korea"},
        {"callsign": "JAPAN88", "longitude": 130.0, "latitude": 36.5, "baro_altitude": 10000, "origin_country": "Japan"},
        {"callsign": "USA99", "longitude": 125.0, "latitude": 36.0, "baro_altitude": 12000, "origin_country": "United States"}
    ]
    return pd.DataFrame(mock_flights)

# 에러의 원인이었던 @st.cache_data 삭제! 실시간 데이터는 어차피 계속 바뀌므로 저장할 필요가 없어!
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
        return get_mock_data(), token_err
        
    try:
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
            return get_mock_data(), f"서버 거절 (상태 코드: {response.status_code})"
    except Exception as e:
        return get_mock_data(), f"통신 차단 또는 시간 초과: {e}"

st.info("💡 **지도 조작 꿀팁:** `Shift` 키를 누른 상태로 **왼쪽 마우스**를 드래그하면 우클릭 메뉴 없이 지도를 회전/기울일 수 있습니다!")
st.write("🚀 **자동 업데이트:** 15초마다 자동으로 지도가 새로고침 됩니다.")

# 핵심 마법: 15초마다 서버에 무리를 주지 않고 이 구역만 자동으로 새로고침!
@st.fragment(run_every="15s")
def radar_screen():
    loading_text = st.empty()
    loading_text.caption("🔄 하늘에서 비행기 정보를 가져오는 중...")
    
    flight_data, error_msg = load_data()
    loading_text.empty() 

    if error_msg:
        st.error("🚨 실시간 데이터를 받아오지 못했습니다. (서버 통신 차단)")
        st.warning("💡 대신 [시연용 예시 데이터]를 띄웠습니다! 기능이 어떻게 작동하는지 테스트해 보세요.")

    if not flight_data.empty:
        if not error_msg:
            st.success(f"성공! 현재 {len(flight_data)}대의 실시간 비행기가 날고 있어요.")
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=flight_data,
            get_position="[longitude, latitude]",
            get_radius=10000, 
            get_fill_color="[255, 75, 75]",
            pickable=True,
        )
        
        view_state = pdk.ViewState(
            latitude=36.0, longitude=128.0, zoom=5.5, pitch=45
        )
        
        tooltip = {
            "html": "<b>비행기 이름:</b> {callsign} <br/> <b>고도:</b> {baro_altitude} m <br/> <b>출발 국가:</b> {origin_country}",
            "style": {"backgroundColor": "steelblue", "color": "white", "font-family": "sans-serif"}
        }
        
        r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip)
        st.pydeck_chart(r)

        st.subheader("📋 상세 비행기 데이터")
        st.dataframe(flight_data)
        
    else:
        st.error("데이터를 가져오지 못했습니다.")

# 앱 실행!
radar_screen()
