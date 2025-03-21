import logging
from typing import Dict, Any, List, Optional
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.utils import exceptions

from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

class NotificationBot:
    """
    Система уведомлений через Telegram-бота.
    """
    
    def __init__(self):
        """Инициализация системы уведомлений."""
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher(self.bot)
        self._subscribed_users = {}  # user_id -> список типов уведомлений
    
    async def start(self):
        """Запуск бота для уведомлений."""
        # Регистрация обработчиков команд
        self.dp.register_message_handler(self._cmd_start, commands=["start"])
        self.dp.register_message_handler(self._cmd_help, commands=["help"])
        self.dp.register_message_handler(self._cmd_subscribe, commands=["subscribe"])
        self.dp.register_message_handler(self._cmd_unsubscribe, commands=["unsubscribe"])
        self.dp.register_message_handler(self._cmd_stats, commands=["stats"])
        
        # Запуск поллинга в фоновом режиме
        asyncio.create_task(self._start_polling())
        logger.info("Notification bot started")
    
    async def _start_polling(self):
        """Запуск поллинга сообщений бота."""
        try:
            await self.dp.start_polling()
        except Exception as e:
            logger.error(f"Error starting notification bot: {str(e)}")
    
    async def _cmd_start(self, message: types.Message):
        """Обработчик команды /start."""
        await message.answer(
            "👋 Привет! Я бот CryptxSpiderAI.\n\n"
            "Я могу отправлять уведомления о:\n"
            "- 🆕 Новых токенах, обнаруженных в Telegram\n"
            "- 🚨 Потенциальных скам-проектах на Memepad\n"
            "- 📡 Новых найденных каналах с обсуждением токенов\n\n"
            "Используйте /subscribe для подписки на уведомления."
        )
    
    async def _cmd_help(self, message: types.Message):
        """Обработчик команды /help."""
        await message.answer(
            "📚 Команды бота:\n\n"
            "/start - Начало работы с ботом\n"
            "/subscribe - Подписка на уведомления\n"
            "/unsubscribe - Отписка от уведомлений\n"
            "/stats - Статистика мониторинга каналов\n"
            "/help - Показать эту справку\n\n"
            "Типы уведомлений:\n"
            "- new_tokens - Новые токены из Telegram\n"
            "- scam_alerts - Предупреждения о скаме\n"
            "- new_channels - Новые найденные каналы\n\n"
            "Пример: /subscribe new_tokens scam_alerts new_channels"
        )
    
    async def _cmd_stats(self, message: types.Message):
        """Обработчик команды /stats для показа статистики по каналам."""
        from models.db import session, TelegramChannel
        
        try:
            # Получаем статистику по каналам
            total_channels = session.query(TelegramChannel).count()
            active_channels = session.query(TelegramChannel).filter(TelegramChannel.is_active == True).count()
            high_relevance = session.query(TelegramChannel).filter(
                TelegramChannel.is_active == True,
                TelegramChannel.relevance_score >= 0.7
            ).count()
            
            # Получаем топ-5 каналов
            top_channels = session.query(TelegramChannel).filter(
                TelegramChannel.is_active == True
            ).order_by(TelegramChannel.relevance_score.desc()).limit(5).all()
            
            # Формируем текст статистики
            stats_text = (
                f"📊 <b>Статистика мониторинга каналов</b>\n\n"
                f"Всего каналов: <b>{total_channels}</b>\n"
                f"Активных каналов: <b>{active_channels}</b>\n"
                f"Высокорелевантных: <b>{high_relevance}</b>\n\n"
            )
            
            if top_channels:
                stats_text += "<b>Топ-5 каналов по релевантности:</b>\n"
                for i, channel in enumerate(top_channels, 1):
                    stats_text += f"{i}. @{channel.username} - {channel.relevance_score:.2f} ({channel.token_mentions_count} упоминаний)\n"
            
            await message.answer(stats_text, parse_mode=types.ParseMode.HTML)
            
        except Exception as e:
            logger.error(f"Error generating stats: {e}")
            await message.answer("❌ Ошибка при получении статистики.")
    
    async def _cmd_subscribe(self, message: types.Message):
        """Обработчик команды /subscribe."""
        user_id = message.from_user.id
        args = message.get_args().split()
        
        if not args:
            await message.answer(
                "🔔 Укажите типы уведомлений:\n"
                "/subscribe new_tokens - для новых токенов\n"
                "/subscribe scam_alerts - для предупреждений о скаме\n"
                "/subscribe new_channels - для новых каналов\n"
                "/subscribe all - для всех уведомлений"
            )
            return
        
        valid_types = ["new_tokens", "scam_alerts", "new_channels", "all"]
        subscription_types = []
        
        for arg in args:
            if arg in valid_types:
                if arg == "all":
                    subscription_types = ["new_tokens", "scam_alerts", "new_channels"]
                    break
                subscription_types.append(arg)
        
        if not subscription_types:
            await message.answer("❌ Указаны неверные типы уведомлений. Используйте /help для справки.")
            return
        
        self._subscribed_users[user_id] = subscription_types
        
        await message.answer(
            f"✅ Вы подписались на следующие уведомления: {', '.join(subscription_types)}"
        )
    
    async def _cmd_unsubscribe(self, message: types.Message):
        """Обработчик команды /unsubscribe."""
        user_id = message.from_user.id
        args = message.get_args().split()
        
        if not args:
            if user_id in self._subscribed_users:
                del self._subscribed_users[user_id]
                await message.answer("🔕 Вы отписались от всех уведомлений.")
            else:
                await message.answer("ℹ️ Вы не подписаны на уведомления.")
            return
        
        if user_id not in self._subscribed_users:
            await message.answer("ℹ️ Вы не подписаны на уведомления.")
            return
        
        valid_types = ["new_tokens", "scam_alerts", "new_channels", "all"]
        unsubscribe_types = []
        
        for arg in args:
            if arg in valid_types:
                if arg == "all":
                    del self._subscribed_users[user_id]
                    await message.answer("🔕 Вы отписались от всех уведомлений.")
                    return
                unsubscribe_types.append(arg)
        
        if not unsubscribe_types:
            await message.answer("❌ Указаны неверные типы уведомлений. Используйте /help для справки.")
            return
        
        current_types = self._subscribed_users[user_id]
        new_types = [t for t in current_types if t not in unsubscribe_types]
        
        if new_types:
            self._subscribed_users[user_id] = new_types
            await message.answer(
                f"🔔 Вы отписались от: {', '.join(unsubscribe_types)}\n"
                f"Остались подписки на: {', '.join(new_types)}"
            )
        else:
            del self._subscribed_users[user_id]
            await message.answer("🔕 Вы отписались от всех уведомлений.")
    
    async def send_alert(self, notification_type: str, message: str, chat_id: Optional[int] = None) -> bool:
        """
        Отправка уведомления.
        
        Args:
            notification_type: Тип уведомления ("new_tokens", "scam_alerts" или "new_channels")
            message: Текст уведомления
            chat_id: ID чата для отправки. Если None, отправляется всем подписанным пользователям.
        
        Returns:
            Успешно ли отправлено уведомление
        """
        if chat_id:
            try:
                await self.bot.send_message(chat_id, message, parse_mode=types.ParseMode.HTML)
                return True
            except exceptions.BotBlocked:
                logger.error(f"Target [ID:{chat_id}]: blocked by user")
            except exceptions.ChatNotFound:
                logger.error(f"Target [ID:{chat_id}]: chat not found")
            except exceptions.RetryAfter as e:
                logger.error(f"Target [ID:{chat_id}]: Flood limit exceeded. Sleep {e.timeout} seconds.")
                await asyncio.sleep(e.timeout)
                return await self.send_alert(notification_type, message, chat_id)  # Retry
            except Exception as e:
                logger.error(f"Target [ID:{chat_id}]: {e}")
            return False
        
        # Отправка всем подписанным пользователям
        success_count = 0
        for user_id, types in self._subscribed_users.items():
            if notification_type in types:
                if await self.send_alert(notification_type, message, user_id):
                    success_count += 1
        
        return success_count > 0
    
    async def send_scam_alert(self, token_data: Dict[str, Any], confidence: float) -> bool:
        """
        Отправка уведомления о потенциальном скаме.
        
        Args:
            token_data: Данные о токене
            confidence: Уверенность в том, что это скам (0-1)
        
        Returns:
            Успешно ли отправлено уведомление
        """
        ticker = token_data.get("ticker", "Неизвестный тикер")
        name = token_data.get("name", "Неизвестный токен")
        score = confidence * 100
        risk_factors = token_data.get("risk_factors", [])
        
        message = (
            f"🚨 <b>Скам-предупреждение</b> 🚨\n\n"
            f"Токен: <b>{name}</b> ({ticker})\n"
            f"Вероятность скама: <b>{score:.1f}%</b>\n\n"
        )
        
        if risk_factors:
            message += "<b>Причины:</b>\n"
            for i, reason in enumerate(risk_factors[:5], 1):
                message += f"{i}. {reason}\n"
            
            if len(risk_factors) > 5:
                message += f"...и еще {len(risk_factors) - 5} причин\n"
        
        message += "\n⚠️ <b>Будьте осторожны при инвестировании!</b>"
        
        return await self.send_alert("scam_alerts", message)
    
    async def send_new_token_alert(self, token_data) -> bool:
        """
        Отправка уведомления о новом токене.
        
        Args:
            token_data: Объект PotentialToken
        
        Returns:
            Успешно ли отправлено уведомление
        """
        name = token_data.name
        description = token_data.description
        confidence = token_data.confidence_score
        
        # Обрезаем описание, если оно слишком длинное
        if description and len(description) > 200:
            description = description[:197] + "..."
        
        message = (
            f"🆕 <b>Новый потенциальный токен обнаружен!</b>\n\n"
            f"Название: <b>{name}</b>\n"
            f"Уверенность: {confidence:.2f}\n\n"
        )
        
        if description:
            message += f"<b>Информация:</b>\n{description}\n\n"
        
        message += f"🔍 <i>Этот токен еще не появился на Memepad, но активно обсуждается в Telegram.</i>"
        
        return await self.send_alert("new_tokens", message)
    
    async def send_new_channel_alert(self, channel) -> bool:
        """
        Отправка уведомления о новом релевантном канале.
        
        Args:
            channel: Объект TelegramChannel
        
        Returns:
            Успешно ли отправлено уведомление
        """
        username = channel.username
        title = channel.title or username
        description = channel.description
        relevance = channel.relevance_score
        members = channel.members_count or "Неизвестно"
        
        # Обрезаем описание, если оно слишком длинное
        if description and len(description) > 150:
            description = description[:147] + "..."
        
        message = (
            f"📡 <b>Обнаружен новый релевантный канал!</b>\n\n"
            f"Канал: <b>@{username}</b>\n"
            f"Название: {title}\n"
            f"Релевантность: {relevance:.2f}\n"
            f"Участников: {members}\n\n"
        )
        
        if description:
            message += f"<b>Описание:</b>\n{description}\n\n"
        
        message += f"🔍 <i>В этом канале часто обсуждаются крипто-токены.</i>"
        
        return await self.send_alert("new_channels", message)
    
    async def stop(self):
        """Закрытие бота."""
        await self.bot.close()
        await self.dp.storage.close()
        await self.dp.storage.wait_closed()
