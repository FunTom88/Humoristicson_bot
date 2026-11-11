"""Проверяет тот же native API, который использует бот, без токена Telegram."""
import asyncio
import os
from pathlib import Path
import aiohttp
from dotenv import load_dotenv
from local_model import chat_endpoint, native_payload, extract_answer

async def main():
    load_dotenv(Path(__file__).with_name('.env'))
    try:
        url=chat_endpoint(os.getenv('AI_BASE_URL','http://localhost:1235/v1'))
        model=os.getenv('AI_MODEL','qwen/qwen3.5-9b')
        key=os.getenv('AI_API_KEY','')
        headers={'Authorization':'Bearer '+key} if key else {}
        messages=[{'role':'system','content':'Отвечай по-русски, одной короткой шуткой.'},
                  {'role':'user','content':'Пошути про системного администратора и понедельник.'}]
        print('Testing Bionic native API, reasoning=off...')
        async with aiohttp.ClientSession(headers=headers,timeout=aiohttp.ClientTimeout(total=float(os.getenv('AI_TIMEOUT_SECONDS','180')))) as s:
            async with s.post(url,json=native_payload(model,messages,int(os.getenv('AI_MAX_TOKENS','512')))) as r:
                if r.status!=200: raise RuntimeError(f'Native API HTTP {r.status}')
                data=await r.json()
        print(extract_answer(data))
        print('Reasoning tokens:',data.get('stats',{}).get('reasoning_output_tokens','not reported'))
    except (aiohttp.ClientError,asyncio.TimeoutError,RuntimeError,KeyError,ValueError) as e:
        print('Check failed:',str(e) if isinstance(e,(RuntimeError,ValueError)) else type(e).__name__)
        raise SystemExit(1)

if __name__=='__main__': asyncio.run(main())
