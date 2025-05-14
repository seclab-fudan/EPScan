# openai_helper.py -- OpenAI 相关的调用
#
# Copyright (C) 2024 KAAAsS
import json
from pathlib import Path

from openai import OpenAI

from utils.log import log_funcs

MODEL_NAME = "gpt-4o"
with (Path(__file__).parent.parent / 'openai.key').open('r') as f:
    API_KEY = f.read().strip()

client = OpenAI(
    api_key=API_KEY,
)

debug, info, warn, error, fatal = log_funcs(from_file=__file__)


def completion(history: list[dict], temperature=0.3) -> str:
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=history,
        temperature=temperature,
    )
    return resp.choices[0].message.content


def completion_with_type(history: list[dict], temperature=0.9, resp_type=list, max_attempts=3):
    for attempt in range(max_attempts):
        resp = None
        try:
            resp = completion(history, temperature)
            resp = resp.replace('```json\n', '').replace('```', '')
            result = json.loads(resp)
            assert isinstance(result, resp_type), "response must be a " + str(resp_type)
            return result
        except Exception as e:
            warn("failed to request OpenAI", exc_info=e, attempt=attempt, response=resp)
    return None


def _test():
    print(completion([{"role": "system", "content": "Hello, how are you?"}]))


if __name__ == '__main__':
    _test()
