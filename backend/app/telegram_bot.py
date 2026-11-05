"""Optional aiogram polling worker using exactly the web chat engine.

No token => no outbound API calls. Use one token for one clinic per process.
Only private chats; opaque expiring callbacks; updates persisted before replies.
"""
import asyncio
import logging
import os
import secrets
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select, func
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from aiogram.exceptions import TelegramAPIError
from . import models as m
from .db import SessionLocal, utcnow
from .security import token_hash
from .services.common import tenant_by_slug
from .services.chat import get_or_create_conversation, handle_message, append_message, payload
from .telegram_links import consume_link

log = logging.getLogger('dentflow.telegram')
dispatcher = Dispatcher()


def _context(db, chat_id):
    tenant = tenant_by_slug(db, os.getenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue'))
    conv = db.scalar(select(m.Conversation).where(m.Conversation.tenant_id == tenant.id,
        m.Conversation.channel == 'telegram', m.Conversation.external_id == str(chat_id)))
    visitor = db.get(m.AuthSession, conv.session_id) if conv and conv.session_id else None
    if visitor is None:
        visitor = m.AuthSession(token_hash=token_hash(secrets.token_urlsafe(48)), kind='visitor',
                               expires_at=utcnow() + timedelta(days=3650))
        db.add(visitor)
        db.flush()
    conv = get_or_create_conversation(db, tenant, visitor=visitor, channel='telegram', external_id=str(chat_id))
    if not conv.session_id:
        conv.session_id = visitor.id
    return tenant, conv, visitor


def process_update(chat_id: int, update_id: int, text: str = '', callback: str | None = None):
    """Sync transactional boundary, called in a thread from aiogram and unit tests."""
    # Read provider/budget, close the read-only transaction, then call the model.
    # No conversation or booking lock is held during external network I/O.
    preclassification = None
    if not callback and text and not text.startswith('/'):
        provider = None
        with SessionLocal() as pre:
            tenant = tenant_by_slug(pre, os.getenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue'))
            ai = pre.scalar(select(m.AISettings).where(m.AISettings.tenant_id == tenant.id))
            conv = pre.scalar(select(m.Conversation).where(m.Conversation.tenant_id == tenant.id,
                m.Conversation.channel == 'telegram', m.Conversation.external_id == str(chat_id)))
            if conv and update_id <= int((conv.context or {}).get('telegram_last_update', -1)):
                return None
            subscription = pre.scalar(select(m.Subscription).where(m.Subscription.tenant_id == tenant.id))
            plan = pre.scalar(select(m.Plan).where(m.Plan.code == subscription.plan_code)) if subscription else None
            month = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            usage = pre.scalar(select(func.count(m.AIUsage.id)).where(m.AIUsage.tenant_id == tenant.id,
                m.AIUsage.provider != 'demo', m.AIUsage.created_at >= month)) or 0
            if ai and ai.enabled and ai.provider != 'demo' and (not conv or conv.mode == 'ai') and plan and usage < plan.ai_limit:
                provider = ai.provider
        if provider:
            from .adapters.ai import safe_intent
            preclassification = safe_intent(text, provider)
    with SessionLocal() as db:
        tenant, conv, visitor = _context(db, chat_id)
        db.scalar(select(m.Conversation).where(m.Conversation.id == conv.id).with_for_update())
        context = dict(conv.context or {})
        if update_id <= int(context.get('telegram_last_update', -1)):
            return None
        if text.startswith('/start link_'):
            token = text.split('link_', 1)[1].strip()
            consume_link(db, tenant, conv, token)
            append_message(db, conv, 'assistant', 'Профиль сайта и Telegram безопасно связан. Теперь команда /appointments покажет ваши записи. Телефон не использовался для сопоставления.')
            result = payload(db, conv)
        else:
            action, data = None, None
            if callback:
                parts = callback.split(':')
                if len(parts) != 3 or parts[0] != 'df' or parts[1] != context.get('telegram_nonce'):
                    raise HTTPException(409, 'Эта кнопка устарела. Отправьте /book или /appointments заново.')
                try:
                    selected = context.get('options', [])[int(parts[2])]
                    action, data = selected['action'], selected.get('data', {})
                    text = selected['label']
                except (ValueError, IndexError, KeyError):
                    raise HTTPException(400, 'Кнопка не найдена')
            result = handle_message(db, tenant, conv, text, action=action, data=data, visitor=visitor,
                                    classify_external=False, preclassification=preclassification)
        nonce = secrets.token_hex(5)
        conv.context = {**(conv.context or {}), 'telegram_last_update': update_id, 'telegram_nonce': nonce}
        db.commit()
        return {'text': result['messages'][-1]['text'][:4000], 'options': result.get('options', [])[:30], 'nonce': nonce}


def _keyboard(result):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=x['label'][:60], callback_data=f"df:{result['nonce']}:{i}")]
        for i, x in enumerate(result['options'])]) if result.get('options') else None


@dispatcher.message(F.chat.type == 'private', F.text)
async def on_message(message: Message, event_update: Update):
    try:
        result = await asyncio.to_thread(process_update, message.chat.id, event_update.update_id, message.text or '')
        if result:
            await message.answer(result['text'], reply_markup=_keyboard(result))
    except HTTPException as exc:
        await message.answer(str(exc.detail))
    except TelegramAPIError:
        log.warning('telegram_reply_failed')
    except Exception:
        log.error('telegram_processing_failed')
        await message.answer('Не удалось завершить действие. Попробуйте снова или откройте сайт клиники. Запись не подтверждена, пока вы не получили подтверждение.')


@dispatcher.callback_query(F.data.startswith('df:'))
async def on_callback(callback: CallbackQuery, event_update: Update):
    if not callback.message or callback.message.chat.type != 'private' or callback.from_user.id != callback.message.chat.id:
        await callback.answer('Работаем только в личном чате', show_alert=True)
        return
    try:
        result = await asyncio.to_thread(process_update, callback.message.chat.id, event_update.update_id, callback=callback.data)
        await callback.answer()
        if result:
            await callback.message.answer(result['text'], reply_markup=_keyboard(result))
    except HTTPException as exc:
        await callback.answer(str(exc.detail)[:180], show_alert=True)
    except TelegramAPIError:
        log.warning('telegram_callback_reply_failed')
    except Exception:
        log.error('telegram_callback_processing_failed')
        await callback.answer('Не удалось обработать запрос. Попробуйте /book.', show_alert=True)


@dispatcher.message()
async def unsupported(message: Message):
    if message.chat.type == 'private':
        await message.answer('Для записи напишите текст или используйте /book. Медицинские документы, фотографии и голосовые сообщения здесь не обрабатываются.')


async def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    if os.getenv('TELEGRAM_ENABLED', 'false').lower() != 'true' or not token:
        raise SystemExit('Telegram отключён. Задайте TELEGRAM_ENABLED=true и TELEGRAM_BOT_TOKEN в .env.')
    async with Bot(token) as bot:
        webhook = await bot.get_webhook_info()
        if webhook.url:
            raise SystemExit('У бота уже настроен webhook. Не запускайте polling параллельно; отключите webhook по инструкции после проверки владельца.')
        await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in [
            ('start', 'Начать'), ('book', 'Записаться на приём'), ('appointments', 'Мои записи'),
            ('help', 'Помощь'), ('human', 'Позвать администратора')]])
        # Sequential handling plus persisted update IDs make replay harmless.
        await dispatcher.start_polling(bot, handle_as_tasks=False, allowed_updates=['message', 'callback_query'])


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s %(message)s')
    asyncio.run(main())
