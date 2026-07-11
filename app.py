import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import random
import time
import gc  # 메모리 청소기를 위한 라이브러리 추가!

st.set_page_config(page_title="실시간 비행기 레이더", page_icon="✈️", layout="wide")

st.title("✈️ 한반도 실시간 비행기 레이더")
st.info("💡 **지도 조작 꿀팁:** `Shift` 키를 누른 상태로 **왼쪽 마우스**를 드래그하면 지도를 회전/기울일 수 있습니다!")

def get_access_token():
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
            timeout=3 # 💡 3초 만에 끊어서 서버 기절 방지!
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
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
        response = requests.get(url, params=params, headers=headers, timeout=3)
        if response.status_code == 200:
            data = response.json()
            states = data.get('states')
            
            if states is not None and len(states) > 0:
                columns = [
                    'icao24', 'callsign', 'origin_country', 'time_position', 
                    'last_contact', 'longitude', 'latitude', 'baro_altitude', 
                    'on_ground', 'velocity', 'true_track', 'vertical_rate', 
                    'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source'
                ]
                df = pd.DataFrame(states, columns=columns)
                df_clean = df[['callsign', 'longitude', 'latitude', 'baro_altitude', 'origin_country', 'true_track']]
                
                # 🛡️ NaN(빈 데이터) 완벽 방어 시스템
                df_clean = df_clean.dropna(subset=['longitude', 'latitude'])
                df_clean['baro_altitude'] = df_clean['baro_altitude'].fillna(0)
                
                # 💡 국가 이름이 빈칸일 때 "Unknown"으로 채워서 PyDeck 에러 방지
                df_clean['origin_country'] = df_clean['origin_country'].fillna("Unknown")
                
                # 방향(각도)이 빈칸일 때 랜덤 각도 부여
                df_clean['true_track'] = df_clean['true_track'].apply(lambda x: random.randint(0, 360) if pd.isna(x) else x)
                
                # 💡 이름이 없는 비행기는 "UNKNOWN"으로 채워서 PyDeck 에러 방지
                df_clean['callsign'] = df_clean['callsign'].fillna("UNKNOWN")
                df_clean['callsign'] = df_clean['callsign'].apply(lambda x: str(x).strip() if str(x).strip() else "UNKNOWN")

                return df_clean, None
            else:
                return get_mock_data(), "현재 한반도 상공에 잡히는 비행기가 없거나 서버가 데이터를 주지 않았습니다."
        else:
            return get_mock_data(), f"서버 거절 ({response.status_code})"
    except Exception as e:
        return get_mock_data(), f"통신 초과: {e}"

def radar_screen():
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.write("🚀 **레이더 업데이트:** 오른쪽 버튼을 눌러 최신 비행기 위치를 확인하세요.")
    with col2:
        if st.button("🔄 레이더 갱신", use_container_width=True):
            pass

    loading_text = st.empty()
    loading_text.caption("🔄 하늘에서 비행기 정보를 가져오는 중...")
    
    flight_data, error_msg = load_data()
    loading_text.empty() 

    if error_msg:
        if "timeout" in error_msg.lower() or "통신 에러" in error_msg or "통신 초과" in error_msg:
            st.warning("☁️ **클라우드 환경 감지:** OpenSky 보안 정책으로 인해 클라우드 서버에서의 접속이 차단되었습니다.")
            st.info("💡 **시연 모드(Demo) 작동 중:** 앱이 멈추지 않도록 [예시 데이터]를 띄웠습니다! 지도 회전 및 비행기 정보 등 모든 기능은 정상 작동합니다.")
            with st.expander("🛠️ 개발자용 에러 로그 확인"):
                st.code(error_msg)
        else:
            st.error(f"🚨 실시간 데이터 연결 실패: {error_msg}")
            st.warning("💡 대신 [시연용 예시 데이터]를 띄웠습니다!")

    if not flight_data.empty:
        if not error_msg:
            st.success(f"성공! 현재 {len(flight_data)}대의 비행기를 추적 중입니다.")
        
        # 1. 비행기 위치를 그리는 빨간색 점
        layer_dot = pdk.Layer(
            "ScatterplotLayer",
            data=flight_data,
            get_position="[longitude, latitude]",
            get_radius=12000, 
            get_fill_color="[255, 75, 75]",
            pickable=True,
        )
        
        # 2. 비행기 이름표(Callsign) 띄우기
        layer_text = pdk.Layer(
            "TextLayer",
            data=flight_data,
            get_position="[longitude, latitude]",
            get_text="callsign", 
            get_size=15,            
            get_color="[255, 255, 255]",
            get_pixel_offset="[0, -20]", 
            pickable=False,
        )
        
        view_state = pdk.ViewState(latitude=36.0, longitude=128.0, zoom=5.5, pitch=45)
        
        tooltip = {
            "html": "<b>비행기:</b> {callsign} <br/> <b>고도:</b> {baro_altitude} m <br/> <b>방향:</b> {true_track} 도 <br/> <b>국가:</b> {origin_country}",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }
        
        r = pdk.Deck(layers=[layer_dot, layer_text], initial_view_state=view_state, tooltip=tooltip)
        st.pydeck_chart(r)
        
    else:
        st.error("데이터를 화면에 그릴 수 없습니다.")

    # 🧹 메모리 누수 방지: 다 쓴 메모리를 청소하여 503 에러 예방
    gc.collect()

radar_screen()
