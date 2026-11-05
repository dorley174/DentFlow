"""Small synchronous provider boundary; no DB permissions or autonomous tool execution.

Patient text is never forwarded by this module's safe_intent helper unless every
word is in a closed administrative vocabulary. Arbitrary completion() is for
developer-controlled, non-personal text (connection check), not patient histories.
"""
from __future__ import annotations
import json
import os
import re
import ssl
import time
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse
import httpx


class ProviderUnavailable(RuntimeError):
    """Public-safe error without raw provider response, headers or credentials."""


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0


class AIProvider(Protocol):
    name: str
    def complete(self, system: str, prompt: str) -> Completion: ...


def _enabled() -> bool:
    return os.getenv('AI_EXTERNAL_ENABLED', 'false').lower() == 'true'


def _require(value: str, label: str) -> str:
    if not value or value.startswith('CHANGE_ME'):
        raise ProviderUnavailable(f'Не настроен {label}')
    return value


def _request(client: httpx.Client, url: str, **kwargs) -> dict:
    try:
        response = client.post(url, **kwargs)
        response.raise_for_status()
        if len(response.content) > 1_000_000:
            raise ProviderUnavailable('Ответ AI-провайдера слишком большой')
        data = response.json()
        if not isinstance(data, dict):
            raise ProviderUnavailable('Некорректный ответ AI-провайдера')
        return data
    except (httpx.HTTPError, ValueError) as exc:
        # Do not propagate request URLs, bodies, API keys, or raw error messages.
        raise ProviderUnavailable('AI-провайдер недоступен. Работает базовый режим.') from None


class DemoProvider:
    name = 'demo'
    def complete(self, system: str, prompt: str) -> Completion:
        return Completion('Демонстрационный режим работает без внешней нейросети.', self.name)


class YandexProvider:
    name = 'yandex'
    def complete(self, system: str, prompt: str) -> Completion:
        key = _require(os.getenv('YANDEX_API_KEY', ''), 'YANDEX_API_KEY')
        folder = _require(os.getenv('YANDEX_FOLDER_ID', ''), 'YANDEX_FOLDER_ID')
        model = os.getenv('YANDEX_MODEL', 'yandexgpt-5.1')
        uri = model if model.startswith('gpt://') else f'gpt://{folder}/{model}'
        with httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False) as client:
            data = _request(client, 'https://ai.api.cloud.yandex.net/foundationModels/v1/completion',
                headers={'Authorization': f'Api-Key {key}', 'x-data-logging-enabled': 'false'},
                json={'modelUri': uri, 'completionOptions': {'stream': False, 'temperature': 0, 'maxTokens': '256'},
                      'messages': [{'role': 'system', 'text': system}, {'role': 'user', 'text': prompt}]})
        try:
            result = data.get('result', data)
            usage = result.get('usage', {})
            return Completion(result['alternatives'][0]['message']['text'][:4000], self.name,
                              int(usage.get('inputTextTokens', 0)), int(usage.get('completionTokens', 0)))
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderUnavailable('Не удалось прочитать ответ Yandex AI Studio') from None


class GigaChatProvider:
    name = 'gigachat'
    def __init__(self):
        self._token = ''
        self._expires = 0.0

    def _ssl_context(self):
        ca = os.getenv('GIGACHAT_CA_BUNDLE') or None
        return ssl.create_default_context(cafile=ca)

    def complete(self, system: str, prompt: str) -> Completion:
        key = _require(os.getenv('GIGACHAT_AUTH_KEY', ''), 'GIGACHAT_AUTH_KEY')
        base = os.getenv('GIGACHAT_BASE_URL', 'https://api.giga.chat/v1').rstrip('/')
        if base not in {'https://api.giga.chat/v1', 'https://gigachat.devices.sberbank.ru/api/v1'}:
            raise ProviderUnavailable('GIGACHAT_BASE_URL должен быть официальным HTTPS endpoint')
        try:
            with httpx.Client(timeout=httpx.Timeout(20, connect=5), verify=self._ssl_context(), follow_redirects=False) as client:
                if self._expires <= time.time() + 60:
                    token = _request(client, 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                        headers={'Authorization': f'Basic {key}', 'RqUID': str(uuid.uuid4()), 'Accept': 'application/json'},
                        data={'scope': os.getenv('GIGACHAT_SCOPE', 'GIGACHAT_API_B2B')})
                    self._token = token['access_token']
                    expiry = float(token['expires_at'])
                    self._expires = expiry / 1000 if expiry > 10_000_000_000 else expiry
                data = _request(client, base + '/chat/completions',
                    headers={'Authorization': f'Bearer {self._token}'},
                    json={'model': os.getenv('GIGACHAT_MODEL', 'GigaChat'), 'stream': False,
                          'temperature': 0.01, 'max_tokens': 256,
                          'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]})
            usage = data.get('usage', {})
            return Completion(data['choices'][0]['message']['content'][:4000], self.name,
                              int(usage.get('prompt_tokens', 0)), int(usage.get('completion_tokens', 0)))
        except (KeyError, IndexError, TypeError, ValueError, OSError):
            raise ProviderUnavailable('Не удалось получить ответ GigaChat. Проверьте доступ и сертификаты.') from None


class LocalProvider:
    name = 'local'
    def complete(self, system: str, prompt: str) -> Completion:
        base = _require(os.getenv('LOCAL_LLM_URL', ''), 'LOCAL_LLM_URL').rstrip('/')
        parsed = urlparse(base)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ProviderUnavailable('Некорректный LOCAL_LLM_URL')
        # This is a server operator setting, never a patient-supplied URL.
        model = _require(os.getenv('LOCAL_LLM_MODEL', ''), 'LOCAL_LLM_MODEL')
        headers = {}
        if os.getenv('LOCAL_LLM_API_KEY'):
            headers['Authorization'] = 'Bearer ' + os.environ['LOCAL_LLM_API_KEY']
        with httpx.Client(timeout=httpx.Timeout(25, connect=5), follow_redirects=False) as client:
            data = _request(client, base + '/chat/completions', headers=headers,
                json={'model': model, 'temperature': 0, 'max_tokens': 128, 'stream': False,
                      'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]})
        try:
            usage = data.get('usage', {})
            return Completion(data['choices'][0]['message']['content'][:4000], self.name,
                              int(usage.get('prompt_tokens', 0)), int(usage.get('completion_tokens', 0)))
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderUnavailable('Не удалось прочитать ответ локальной модели') from None


_PROVIDERS: dict[str, AIProvider] = {}

def get_provider(name: str | None = None) -> AIProvider:
    name = name or os.getenv('AI_PROVIDER', 'demo')
    choices = {'demo': DemoProvider, 'yandex': YandexProvider, 'gigachat': GigaChatProvider, 'local': LocalProvider}
    if name not in choices:
        raise ProviderUnavailable('Неизвестный AI-провайдер')
    if name != 'demo' and not _enabled():
        raise ProviderUnavailable('Внешние и локальные LLM-вызовы выключены: AI_EXTERNAL_ENABLED=false')
    if name not in _PROVIDERS:
        _PROVIDERS[name] = choices[name]()
    return _PROVIDERS[name]


SAFE_WORDS = frozenset('''здравствуйте привет добрый день вечер утро пожалуйста спасибо
какие какая какой какое есть услуги услуга услуг стоимость стоит цены цена прайс сколько
врачи врач доктор доктора врачей расписание когда работает работаете открыты часы работы
адрес где находится находитесь филиал филиалы клиника клиники как к вам добраться
хочу можно записаться запись запишите приём прием свободное время свободные окна
оператор человек администратор позовите переведите связаться мне нужен нужна нужно
я меня у вас и в на по с о бы сегодня завтра'''.split())
INTENTS = {'services', 'doctors', 'hours', 'book', 'human', 'greeting', 'unknown'}

def safe_intent(message: str, provider_name: str) -> tuple[str | None, Completion | None]:
    """Conservative opt-in classifier. Unknown words, names, numbers -> local logic.

    It does not forward prices, slots, names, phone numbers, messages history or
    health information. Returned intent cannot mutate any record on its own.
    """
    if provider_name == 'demo' or not _enabled():
        return None, None
    if len(message) > 240 or re.search(r'[0-9@+:/]', message):
        return None, None
    words = re.findall(r'[а-яёa-z]+', message.casefold())
    if not words or any(word not in SAFE_WORDS for word in words):
        return None, None
    try:
        result = get_provider(provider_name).complete(
            'Ты классификатор административных запросов. Верни только одно слово: services, doctors, hours, book, human, greeting, unknown. Никаких действий и рекомендаций.',
            ' '.join(words))
        intent = result.text.strip().lower().strip('"\'`. \n')
        return (intent if intent in INTENTS else None), result
    except ProviderUnavailable:
        return None, None


def connection_check(name: str | None = None) -> dict:
    provider = get_provider(name)
    completion = provider.complete('Ты выполняешь техническую проверку API. Ответь одним словом: готово.', 'Техническая проверка подключения без данных пациентов.')
    return {'provider': completion.provider, 'status': 'ok', 'input_tokens': completion.input_tokens,
            'output_tokens': completion.output_tokens, 'note': 'Проверка соединения; не юридическая оценка и не проверка клинического применения.'}


if __name__ == '__main__':
    try:
        print(json.dumps(connection_check(), ensure_ascii=False))
    except ProviderUnavailable as exc:
        print(json.dumps({'status': 'error', 'message': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
