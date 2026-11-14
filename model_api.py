"""Configuration and response handling shared by the bot and its API check."""
import os

from local_model import chat_endpoint, extract_answer, native_payload


class ModelAPI:
    def __init__(self):
        self.provider = os.getenv('AI_PROVIDER', 'lmstudio').strip().lower()
        self.key = os.getenv('AI_API_KEY', '').strip()
        if self.provider == 'gemini':
            if not self.key:
                raise ValueError('Set AI_API_KEY for Gemini')
            self.url = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
            default_model = 'gemini-3.8-flash'
        elif self.provider == 'lmstudio':
            self.url = chat_endpoint(os.getenv('AI_BASE_URL', 'http://localhost:1235/v1'))
            default_model = 'qwen/qwen3.5-9b'
        else:
            raise ValueError('AI_PROVIDER must be lmstudio or gemini')
        self.model = os.getenv('AI_MODEL', '').strip() or default_model

    @property
    def headers(self):
        return {'Authorization': 'Bearer ' + self.key} if self.key else {}

    def payload(self, messages):
        limit = int(os.getenv('AI_MAX_TOKENS', '512'))
        if self.provider == 'lmstudio':
            return native_payload(self.model, messages, limit)
        return {'model': self.model, 'messages': messages, 'max_tokens': limit,
                'reasoning_effort': 'low', 'stream': False}

    def answer(self, data):
        if self.provider == 'lmstudio':
            return extract_answer(data)
        answer = data['choices'][0]['message'].get('content')
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError('Gemini returned no text')
        return answer.strip()
