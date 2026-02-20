import httpx
from typing import Optional

async def get_weather_condition(latitude: float, longitude: float) -> str:
    """
    Fetches the current weather condition from Open-Meteo and categorizes it
    into one of our 4 main buckets: Clear, Cloudy, Rain, Snow.
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=weather_code"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=5.0)
            if response.status_code != 200:
                return "Clear" # Default fallback
                
            data = response.json()
            if "current" not in data or "weather_code" not in data["current"]:
                return "Clear"
                
            code = data["current"]["weather_code"]
            
            # WMO Weather interpretation codes
            # 0: Clear sky
            # 1, 2, 3: Mainly clear, partly cloudy, and overcast
            # 45, 48: Fog and depositing rime fog
            # 51, 53, 55: Drizzle / 56, 57: Freezing Drizzle
            # 61, 63, 65: Rain / 66, 67: Freezing Rain
            # 71, 73, 75: Snow fall / 77: Snow grains
            # 80, 81, 82: Rain showers
            # 85, 86: Snow showers
            # 95: Thunderstorm / 96, 99: Thunderstorm with slight and heavy hail
            
            if code in [0, 1]:
                return "Clear"
            elif code in [2, 3, 45, 48]:
                return "Cloudy"
            elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]:
                return "Rain"
            elif code in [71, 73, 75, 77, 85, 86]:
                return "Snow"
            else:
                return "Clear"
                
        except Exception as e:
            import logging
            logging.error(f"Error fetching weather from Open-Meteo: {e}")
            return "Clear"
