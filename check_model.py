"""Проверяет тот же API, который использует бот, без токена Telegram."""
import asyncio
import os
from pathlib import Path
import aiohttp
from dotenv import load_dotenv
from model_api import ModelAPI

async def main():
    load_dotenv(Path(__file__).with_name('.env'))
    try:
        api = ModelAPI()
        messages=[{'role':'system','content':'Отвечай по-русски, одной короткой шуткой.'},
                  {'role':'user','content':'Пошути про системного администратора и понедельник.'}]
        print(f'Testing {api.provider}: {api.model}...')
        async with aiohttp.ClientSession(headers=api.headers,timeout=aiohttp.ClientTimeout(total=float(os.getenv('AI_TIMEOUT_SECONDS','180')))) as s:
            async with s.post(api.url, json=api.payload(messages), allow_redirects=False) as r:
                if r.status!=200: raise RuntimeError(f'Model API HTTP {r.status}')
                data=await r.json()
        print(api.answer(data))
        if api.provider == 'lmstudio':
            print('Reasoning tokens:',data.get('stats',{}).get('reasoning_output_tokens','not reported'))
    except (aiohttp.ClientError,asyncio.TimeoutError,RuntimeError,KeyError,ValueError) as e:
        print('Check failed:',str(e) if isinstance(e,(RuntimeError,ValueError)) else type(e).__name__)
        raise SystemExit(1)

if __name__=='__main__': asyncio.run(main())
