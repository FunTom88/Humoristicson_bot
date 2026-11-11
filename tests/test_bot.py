import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
from bot import Bot, Store, daily_score, menu, winner
from content import CATEGORIES, PROMPTS

class LogicTests(unittest.TestCase):
    def test_win_and_draw(self):
        self.assertEqual(winner(list('XXXOO····')),'X')
        self.assertEqual(winner(list('XOXXOOOXX')),'draw')
        self.assertIsNone(winner(['·']*9))
    def test_stable_daily(self):
        self.assertEqual(daily_score(1,2,'rating'),daily_score(1,2,'rating'))
        self.assertTrue(0<=daily_score(1,2,'rating')<=100)
    def test_all_buttons_fit_telegram(self):
        for category in [None,*CATEGORIES]:
            for row in menu(category)['inline_keyboard']:
                for button in row:
                    self.assertLessEqual(len(button['callback_data'].encode()),64)
    def test_persistence_and_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(d+'/db'); s.put('game:x',{'expires':time.time()-1}); s.put('offset',42)
            s.prune(); self.assertIsNone(s.get('game:x')); s.db.close()
            s=Store(d+'/db'); self.assertEqual(s.get('offset'),42); s.db.close()

class FlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(self.tmp.name+'/db')
        with patch.dict(os.environ,{'BOT_TOKEN':'test','ALLOWED_CHAT_IDS':''}): self.bot=Bot(None,self.store)
        self.bot.me={'id':99,'username':'test_goose_bot'}
        self.bot.api=AsyncMock(return_value=True)
        self.bot.send=AsyncMock(return_value={'message_id':100})
        self.bot.ai=AsyncMock(return_value='Шутка!')
    def tearDown(self): self.store.db.close(); self.tmp.cleanup()
    def message(self,text,uid=1):
        return {'chat':{'id':-10,'type':'group'},'from':{'id':uid,'first_name':'Павел'},'text':text,'message_id':50}
    def callback(self,data,uid=1):
        return {'id':'cb','from':{'id':uid,'first_name':'Павел'},'message':{'chat':{'id':-10},'message_id':100},'data':data}
    async def test_silent_until_addressed(self):
        await self.bot.message(self.message('Привет всем'))
        self.bot.ai.assert_not_awaited()
        await self.bot.message(self.message('@test_goose_bot привет'))
        self.bot.ai.assert_awaited_once()
    async def test_prompt_belongs_to_user_and_message(self):
        await self.bot.prompt(-10,1,'number',None)
        m=self.message('1 5',2); m['reply_to_message']={'message_id':100}
        await self.bot.message(m)
        self.assertIsNotNone(self.store.get('input:-10:1:0'))
        m=self.message('1 5'); m['reply_to_message']={'message_id':100}
        await self.bot.message(m)
        self.assertIsNone(self.store.get('input:-10:1:0'))
        self.assertTrue(self.bot.send.call_args.args[1].startswith('🔢'))
    async def test_invalid_ranges_and_poll(self):
        self.assertIn('Нужны',await self.bot.input(-10,1,'number','10 1',None))
        self.assertIn('Нужно',await self.bot.input(-10,1,'choose','одно',None))
        await self.bot.input(-10,1,'poll','Еда? | Пицца | Суши',None)
        self.assertEqual(self.bot.api.call_args.args[0],'sendPoll')
    async def test_quiz_only_one_winner(self):
        await self.bot.quiz(-10,1,'fast',None)
        key=self.store.db.execute("SELECT k FROM kv WHERE k LIKE 'quiz:%'").fetchone()[0]
        q=self.store.get(key); index=q['options'].index(q['right']); data='q:'+key[5:]+':'+str(index)
        await self.bot.callback(self.callback(data))
        await self.bot.callback(self.callback(data,2))
        scores=self.store.get('scores:-10')
        self.assertEqual(scores['1']['points'],1); self.assertNotIn('2',scores)
    async def test_games_owner_and_stale_click(self):
        await self.bot.new_game(-10,1,'ttt',{'board':['·']*9},None)
        key=self.store.db.execute("SELECT k FROM kv WHERE k LIKE 'game:%'").fetchone()[0]
        data='g:'+key[5:]+':0'
        await self.bot.callback(self.callback(data,2))
        self.assertEqual(self.store.get(key)['board'],['·']*9)
        await self.bot.callback(self.callback(data))
        self.assertEqual(self.store.get(key)['board'].count('X'),1)
        await self.bot.callback(self.callback(data))
        self.assertEqual(self.store.get(key)['board'].count('X'),1)
    async def test_all_actions_dispatch(self):
        for _,items in CATEGORIES.values():
            for action,_ in items:
                await self.bot.action(-10,1,'Павел',action,None)
    async def test_allowlist(self):
        self.bot.allowed={-20}
        await self.bot.message(self.message('@test_goose_bot привет'))
        self.bot.ai.assert_not_awaited()
    async def test_other_bots_commands_ignored(self):
        await self.bot.message(self.message('/menu@otherbot'))
        self.bot.send.assert_not_awaited()
    async def test_forget(self):
        self.bot.history[(-10,1,0)].append({'role':'user','content':'секрет'})
        await self.bot.action(-10,1,'Павел','forget',None)
        self.assertNotIn((-10,1,0),self.bot.history)

class AITests(unittest.IsolatedAsyncioTestCase):
    async def test_global_budget_prevents_network(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'BOT_TOKEN':'test','AI_API_KEY':'','AI_DAILY_LIMIT':'0'}):
            s=Store(d+'/db'); bot=Bot(None,s)
            self.assertIn('исчерпан',await bot.ai(1,1,'привет')); s.db.close()

if __name__=='__main__': unittest.main()

class LocalAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_local_generation_and_reasoning_filter(self):
        import aiohttp
        from aiohttp import web
        received=[]
        async def handler(request):
            received.append((await request.json(),dict(request.headers)))
            return web.json_response({'output':[{'type':'reasoning','content':'Секретные мысли'},{'type':'message','content':'Гусь на связи!'}]})
        app=web.Application(); app.router.add_post('/api/v1/chat',handler)
        runner=web.AppRunner(app); await runner.setup()
        site=web.TCPSite(runner,'127.0.0.1',0); await site.start()
        port=site._server.sockets[0].getsockname()[1]
        try:
            with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'BOT_TOKEN':'test','AI_BASE_URL':f'http://127.0.0.1:{port}/v1','AI_API_KEY':'','AI_DAILY_LIMIT':'-1','AI_MODEL':'qwen/qwen3.5-9b'}):
                s=Store(d+'/db')
                async with aiohttp.ClientSession() as session:
                    bot=Bot(session,s)
                    answer=await bot.ai(1,2,'Привет')
                    self.assertEqual(answer,'Гусь на связи!')
                    payload,headers=received[0]
                    self.assertEqual(payload['model'],'qwen/qwen3.5-9b')
                    self.assertEqual(payload['max_output_tokens'],512)
                    self.assertEqual(payload['reasoning'],'off')
                    self.assertFalse(payload['store'])
                    self.assertEqual(__import__('json').loads(payload['input'])['current'],'Привет')
                    self.assertNotIn('Authorization',headers)
                    self.assertEqual(len(bot.history[(1,2,0)]),2)
                    self.assertIn('несколько секунд',await bot.ai(1,2,'Ещё'))
                s.db.close()
        finally: await runner.cleanup()
    async def test_api_error_keeps_history_empty(self):
        import aiohttp
        from aiohttp import web
        async def handler(request): return web.Response(status=503)
        app=web.Application(); app.router.add_post('/api/v1/chat',handler)
        runner=web.AppRunner(app); await runner.setup()
        site=web.TCPSite(runner,'127.0.0.1',0); await site.start()
        port=site._server.sockets[0].getsockname()[1]
        try:
            with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'BOT_TOKEN':'test','AI_BASE_URL':f'http://127.0.0.1:{port}/v1','AI_DAILY_LIMIT':'-1'}):
                s=Store(d+'/db')
                async with aiohttp.ClientSession() as session:
                    bot=Bot(session,s)
                    from content import FALLBACK
                    self.assertIn(await bot.ai(1,2,'Привет'),FALLBACK)
                    self.assertEqual(len(bot.history[(1,2,0)]),0)
                s.db.close()
        finally: await runner.cleanup()

class NativeFormatTests(unittest.TestCase):
    def test_endpoint_accepts_old_env(self):
        from local_model import chat_endpoint
        for suffix in ('','/v1','/api/v1','/api/v1/chat'):
            self.assertEqual(chat_endpoint('http://localhost:1235'+suffix),'http://localhost:1235/api/v1/chat')
        with self.assertRaises(ValueError): chat_endpoint('http://localhost:1235/wrong')
    def test_no_reasoning_as_answer(self):
        from local_model import extract_answer
        with self.assertRaises(ValueError): extract_answer({'output':[{'type':'reasoning','content':'private'}]})
        self.assertEqual(extract_answer({'output':[{'type':'message','content':'one'},{'type':'reasoning','content':'private'},{'type':'message','content':'two'}]}),'one\ntwo')
    def test_history_separates_current_turn(self):
        import json
        from local_model import native_payload
        turns=[{'role':'system','content':'system'},{'role':'user','content':'first'},{'role':'assistant','content':'answer'},{'role':'user','content':'next'}]
        p=native_payload('model',turns)
        data=json.loads(p['input'])
        self.assertEqual(data['history'],turns[1:3])
        self.assertEqual(data['current'],'next')
        self.assertFalse(p['store'])
        self.assertNotIn('previous_response_id',p)
