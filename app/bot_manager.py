import asyncio
import logging
from typing import Any, Dict, Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from app.bot_handlers import notify_admins_new_order, notify_client_status, router
from app.config import IS_VERCEL
from app.database import get_setting

logger = logging.getLogger("ustabor.bot_manager")


class BotManager:
    def __init__(self) -> None:
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.task: Optional[asyncio.Task] = None
        self.running: bool = False
        self.webhook_mode: bool = False
        self.bot_username: str = ""
        self.last_error: str = ""

    def _ensure_dispatcher(self) -> Dispatcher:
        if self.dp is None:
            self.dp = Dispatcher(storage=MemoryStorage())
            self.dp.include_router(router)
        return self.dp

    async def init_webhook_mode(self, token: Optional[str] = None, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        tok = (token if token is not None else get_setting("telegram_bot_token", "")).strip()
        if not tok:
            self.last_error = "Telegram bot token kiritilmagan"
            return self.status()
        try:
            if self.bot:
                await self.bot.session.close()
            self.bot = Bot(token=tok, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            self._ensure_dispatcher()
            me = await self.bot.get_me()
            self.bot_username = f"@{me.username}" if me.username else me.full_name
            if webhook_url:
                await self.bot.set_webhook(webhook_url)
            self.webhook_mode = True
            self.running = True
            self.last_error = ""
        except Exception as exc:
            self.last_error = str(exc)
            self.running = False
            logger.warning("Failed to init webhook mode: %s", exc)
        return self.status()

    async def feed_webhook_update(self, payload: Dict[str, Any]) -> None:
        tok = get_setting("telegram_bot_token", "").strip()
        if not tok:
            return
        if self.bot is None:
            self.bot = Bot(token=tok, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = self._ensure_dispatcher()
        update = Update.model_validate(payload, context={"bot": self.bot})
        await dp.feed_update(self.bot, update)

    async def start(self, token: Optional[str] = None) -> Dict[str, Any]:
        if IS_VERCEL:
            return await self.init_webhook_mode(token)

        await self.stop()
        tok = (token if token is not None else get_setting("telegram_bot_token", "")).strip()
        if not tok:
            self.last_error = "Telegram bot token kiritilmagan"
            return self.status()

        try:
            bot = Bot(token=tok, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            me = await bot.get_me()
            self.bot = bot
            self.bot_username = f"@{me.username}" if me.username else me.full_name
            self.dp = Dispatcher(storage=MemoryStorage())
            self.dp.include_router(router)
            self.last_error = ""
            self.webhook_mode = False
            self.running = True
            self.task = asyncio.create_task(self._poll_loop())
            logger.info("Telegram bot started as %s", self.bot_username)
        except Exception as exc:
            self.last_error = str(exc)
            self.running = False
            self.bot_username = ""
            if self.bot:
                try:
                    await self.bot.session.close()
                except Exception:
                    pass
                self.bot = None
            logger.warning("Failed to start Telegram bot: %s", exc)
        return self.status()

    async def _poll_loop(self) -> None:
        assert self.dp is not None and self.bot is not None
        try:
            await self.bot.delete_webhook(drop_pending_updates=False)
            await self.dp.start_polling(self.bot, handle_signals=False)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("Telegram bot polling stopped with error: %s", exc)
        finally:
            self.running = False

    async def stop(self) -> None:
        if self.dp:
            try:
                await self.dp.stop_polling()
            except Exception:
                pass
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.bot:
            try:
                await self.bot.session.close()
            except Exception:
                pass
        self.task = None
        self.dp = None
        self.bot = None
        self.running = False
        self.webhook_mode = False

    async def notify_new_order(self, order: Dict[str, Any]) -> None:
        tok = get_setting("telegram_bot_token", "").strip()
        if not tok:
            return
        if self.bot and self.running:
            await notify_admins_new_order(self.bot, order)
        elif IS_VERCEL:
            bot = Bot(token=tok, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                await notify_admins_new_order(bot, order)
            finally:
                await bot.session.close()

    async def notify_order_status(self, order: Dict[str, Any]) -> None:
        tok = get_setting("telegram_bot_token", "").strip()
        if not tok:
            return
        if self.bot and self.running:
            await notify_client_status(self.bot, order)
        elif IS_VERCEL:
            bot = Bot(token=tok, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                await notify_client_status(bot, order)
            finally:
                await bot.session.close()

    def status(self) -> Dict[str, Any]:
        tok = get_setting("telegram_bot_token", "").strip()
        return {
            "running": self.running,
            "webhook_mode": self.webhook_mode,
            "token_configured": bool(tok),
            "bot_username": self.bot_username,
            "last_error": self.last_error,
        }


bot_manager = BotManager()
