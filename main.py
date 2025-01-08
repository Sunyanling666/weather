import aiohttp
import asyncio
import pandas as pd
from pydantic import BaseModel
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import tenacity
import logging

app = FastAPI()
templates = Jinja2Templates(directory='templates')

# 从 CSV 文件加载城市数据
df = pd.read_csv('europe.csv')

# 将城市数据转换为列表
cities = df.to_dict(orient='records')

# 设置日志记录
logging.basicConfig(level=logging.INFO)

# 重试机制
@tenacity.retry(wait=tenacity.wait_random_exponential(multiplier=1, max=10), stop=tenacity.stop_after_attempt(3))
async def fetch_temperature(session, city, latitude, longitude):
    logging.info(f"Fetching temperature for {city}")
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
        async with session.get(url) as response:
            data = await response.json()
            temperature = data['current_weather']['temperature']
            return {'city': city, 'temperature': temperature}
    except Exception as e:
        logging.error(f"Error fetching temperature for {city}: {e}")
        return None

@app.get('/', response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse('index.html', {'request': request, 'cities': cities})

@app.get('/weather')
async def get_weather():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        tasks = [asyncio.create_task(fetch_temperature(session, city['capital'], city['latitude'], city['longitude'])) for city in cities]
        city_temperatures = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                if result:
                    city_temperatures.append(result)
            except Exception as e:
                logging.error(f"Error in get_weather: {e}")
        sorted_cities = sorted(city_temperatures, key=lambda x: x['temperature'])
        return sorted_cities

@app.post('/add_city')
async def add_city(city: dict):
    cities.append(city)
    return JSONResponse(content={"message": "City added successfully"}, status_code=200)

@app.post('/remove_city')
async def remove_city(city_name: str):
    global cities
    cities = [city for city in cities if city['capital'] != city_name]
    return JSONResponse(content={"message": "City removed successfully"}, status_code=200)

@app.post('/reset_cities')
async def reset_cities():
    global cities
    cities = df.to_dict(orient='records')
    return JSONResponse(content={"message": "Cities reset successfully"}, status_code=200)