"""Bounded conversation memory, shared only inside one chat and topic."""
import time

MAX_TURNS = 12
TTL = 86400


def load_turns(store, key):
    state = store.get(key, {})
    if state.get('expires', 0) <= time.time():
        return []
    return state['turns']


def save_turns(store, key, turns):
    if turns:
        store.put(key, {'expires': time.time() + TTL, 'turns': turns[-MAX_TURNS:]})
    else:
        store.delete(key)


def forget_participant(store, chat, uid):
    prefixes = (f'conversation:{chat}:', f'debate-history:{chat}:')
    for prefix in prefixes:
        rows = store.db.execute('SELECT k FROM kv WHERE k LIKE ?', (prefix + '%',)).fetchall()
        for (key,) in rows:
            turns = load_turns(store, key)
            save_turns(store, key, [turn for turn in turns if turn['uid'] != uid])
