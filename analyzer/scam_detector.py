import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from transformers import pipeline

import openai

from cryptxspider.config import (
    SCAM_PATTERNS, 
    MIN_CHANNEL_AGE_DAYS, 
    SCAM_THRESHOLD,
    OPENAI_API_KEY
)

logger = logging.getLogger(__name__)
openai.api_key = OPENAI_API_KEY

class ScamAnalyzer:
    """
    Анализатор для выявления скам-проектов на основе данных токенов.
    """
    
    def __init__(self):
        """Инициализация анализатора скам-проектов."""
        try:
            # Инициализация ML-модели
            self.model = GradientBoostingClassifier()
            
            # Для MVP используем предобученную модель, в полной версии нужно обучить на реальных данных
            # Пока что просто заглушка для демонстрации
            self._init_dummy_model()
            
            # Инициализация NLP-модели
            self.nlp_pipeline = None
            try:
                self.nlp_pipeline = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")
                logger.info("NLP pipeline initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize NLP pipeline: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to initialize ScamAnalyzer: {str(e)}")
    
    def _init_dummy_model(self):
        """Инициализация заглушки модели для MVP."""
        # Создаем фиктивные данные для демонстрации
        X = np.array([
            [0.1, 0.2, 0.1, 0.3, 0.1],  # Не скам
            [0.9, 0.8, 0.7, 0.9, 0.8],  # Скам
            [0.2, 0.3, 0.2, 0.2, 0.1],  # Не скам
            [0.8, 0.7, 0.9, 0.8, 0.9],  # Скам
        ])
        y = np.array([0, 1, 0, 1])  # 0 - не скам, 1 - скам
        
        # Обучаем модель на фиктивных данных
        self.model.fit(X, y)
        logger.info("Dummy model initialized for MVP")
    
    def check_fake_channel(self, socials: List[Dict[str, str]]) -> Tuple[bool, List[str]]:
        """
        Проверка Telegram-каналов на фейки.
        
        Args:
            socials: Список социальных сетей токена
        
        Returns:
            Кортеж (является_ли_фейком, список_причин)
        """
        risk_factors = []
        
        for social in socials:
            if social.get("type") == "TELEGRAM":
                # В MVP проверяем только наличие ключевых слов в названии/описании
                if social.get("description"):
                    for pattern in SCAM_PATTERNS:
                        if pattern.lower() in social.get("description", "").lower():
                            risk_factors.append(f"Подозрительное описание канала: содержит '{pattern}'")
                
                # Проверка даты создания (в MVP это заглушка)
                if social.get("created_at"):
                    try:
                        created_at = datetime.fromisoformat(social.get("created_at"))
                        days_old = (datetime.utcnow() - created_at).days
                        if days_old < MIN_CHANNEL_AGE_DAYS:
                            risk_factors.append(f"Канал создан недавно ({days_old} дней назад)")
                    except (ValueError, TypeError):
                        pass
        
        return len(risk_factors) > 0, risk_factors
    
    def analyze_holders(self, holders: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
        """
        Анализ распределения холдеров для выявления риска скама.
        
        Args:
            holders: Список холдеров токена
        
        Returns:
            Кортеж (риск_скама, список_причин)
        """
        risk_score = 0.0
        risk_factors = []
        
        if not holders:
            risk_factors.append("Нет данных о холдерах")
            return 0.5, risk_factors
        
        # Проверка на концентрацию токенов
        if holders[0].get("percent", 0) > 50:
            risk_score = 0.95
            risk_factors.append(f"Один адрес владеет более 50% токенов ({holders[0].get('percent')}%)")
        elif holders[0].get("percent", 0) > 30:
            risk_score = 0.7
            risk_factors.append(f"Один адрес владеет более 30% токенов ({holders[0].get('percent')}%)")
        
        # Проверка на количество холдеров
        if len(holders) < 10:
            risk_score = max(risk_score, 0.6)
            risk_factors.append(f"Маленькое количество холдеров ({len(holders)})")
        
        # Проверка на равномерность распределения (Топ-5 холдеров)
        top5_percent = sum(holder.get("percent", 0) for holder in holders[:5])
        if top5_percent > 90:
            risk_score = max(risk_score, 0.8)
            risk_factors.append(f"Топ-5 холдеров владеют {top5_percent}% токенов")
        
        return risk_score, risk_factors
    
    def analyze_liquidity(self, stonfi_data: Dict[str, Any]) -> Tuple[float, List[str]]:
        """
        Анализ ликвидности токена на Ston.fi.
        
        Args:
            stonfi_data: Данные о токене с Ston.fi
        
        Returns:
            Кортеж (риск_скама, список_причин)
        """
        risk_score = 0.0
        risk_factors = []
        
        if not stonfi_data:
            risk_factors.append("Нет данных о ликвидности")
            return 0.5, risk_factors
        
        # Проверка на минимальную ликвидность
        # В MVP используем заглушки, в реальном проекте нужно анализировать реальные данные
        liquidity = stonfi_data.get("liquidity", {}).get("usd", 0)
        if liquidity < 1000:
            risk_score = 0.8
            risk_factors.append(f"Крайне низкая ликвидность: ${liquidity}")
        elif liquidity < 5000:
            risk_score = 0.5
            risk_factors.append(f"Низкая ликвидность: ${liquidity}")
        
        return risk_score, risk_factors
    
    def analyze_transactions(self, transactions: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
        """
        Анализ транзакций токена для выявления подозрительной активности.
        
        Args:
            transactions: Список транзакций токена
        
        Returns:
            Кортеж (риск_скама, список_причин)
        """
        risk_score = 0.0
        risk_factors = []
        
        if not transactions:
            risk_factors.append("Нет данных о транзакциях")
            return 0.5, risk_factors
        
        # Проверка на количество транзакций
        if len(transactions) < 5:
            risk_score = 0.6
            risk_factors.append(f"Очень мало транзакций ({len(transactions)})")
        
        # В MVP используем упрощенный анализ, в реальном проекте нужно анализировать паттерны транзакций
        return risk_score, risk_factors
    
    def analyze_description(self, description: str) -> Tuple[float, List[str]]:
        """
        Анализ описания токена для выявления признаков скама.
        
        Args:
            description: Описание токена
        
        Returns:
            Кортеж (риск_скама, список_причин)
        """
        risk_score = 0.0
        risk_factors = []
        
        if not description:
            risk_factors.append("Отсутствует описание токена")
            return 0.5, risk_factors
        
        # Проверка на ключевые слова скама
        for pattern in SCAM_PATTERNS:
            if pattern.lower() in description.lower():
                risk_score = 0.7
                risk_factors.append(f"Описание содержит подозрительный паттерн: '{pattern}'")
                break
        
        # Анализ настроения с помощью NLP, если доступен
        if self.nlp_pipeline:
            try:
                sentiment = self.nlp_pipeline(description[:512])[0]  # Ограничиваем длину для анализа
                if sentiment['label'] == '1 star' and sentiment['score'] > 0.7:
                    risk_score = max(risk_score, 0.6)
                    risk_factors.append("Крайне негативное описание по анализу настроения")
            except Exception as e:
                logger.error(f"Failed to analyze sentiment: {str(e)}")
        
        return risk_score, risk_factors
    
    def analyze_jetton(self, jetton_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Полный анализ токена для выявления рисков скама.
        
        Args:
            jetton_data: Полные данные о токене
        
        Returns:
            Результат анализа с риском скама и причинами
        """
        details = jetton_data.get("details", {})
        reactions = jetton_data.get("reactions", {})
        transactions = jetton_data.get("transactions", [])
        stonfi_data = jetton_data.get("stonfi_data", {})
        
        # Собираем все фичи для анализа
        risk_factors = []
        risk_scores = []
        
        # Проверка на фейковые каналы
        is_fake, channel_risks = self.check_fake_channel(details.get("socials", []))
        if is_fake:
            risk_scores.append(0.8)
            risk_factors.extend(channel_risks)
        
        # Анализ холдеров
        holders_risk, holders_factors = self.analyze_holders(details.get("holders", []))
        risk_scores.append(holders_risk)
        risk_factors.extend(holders_factors)
        
        # Анализ ликвидности
        liquidity_risk, liquidity_factors = self.analyze_liquidity(stonfi_data)
        risk_scores.append(liquidity_risk)
        risk_factors.extend(liquidity_factors)
        
        # Анализ транзакций
        tx_risk, tx_factors = self.analyze_transactions(transactions)
        risk_scores.append(tx_risk)
        risk_factors.extend(tx_factors)
        
        # Анализ описания
        desc_risk, desc_factors = self.analyze_description(details.get("description", ""))
        risk_scores.append(desc_risk)
        risk_factors.extend(desc_factors)
        
        # Итоговый скор (среднее взвешенное)
        if risk_scores:
            final_score = sum(risk_scores) / len(risk_scores)
        else:
            final_score = 0.5  # Недостаточно данных
        
        # Результат
        is_scam = final_score >= SCAM_THRESHOLD
        
        return {
            "is_scam": is_scam,
            "scam_score": final_score,
            "risk_factors": risk_factors,
            "ticker": details.get("ticker", ""),
            "name": details.get("name", ""),
            "short_name": details.get("short_name", "")
        }
    
    async def generate_scam_report(self, jetton_data: Dict[str, Any], analysis_result: Dict[str, Any]) -> str:
        """
        Генерация отчета о скам-анализе с использованием GPT-4.
        
        Args:
            jetton_data: Полные данные о токене
            analysis_result: Результат анализа скама
        
        Returns:
            Текстовый отчет
        """
        try:
            # Подготовка контекста для GPT-4
            details = jetton_data.get("details", {})
            prompt = f"""
            Сгенерируй краткий отчет по токену {details.get('name', 'Неизвестный токен')} ({details.get('ticker', 'Неизвестный тикер')}).
            
            Информация о токене:
            - Адрес: {details.get('address', 'Неизвестно')}
            - Описание: {details.get('description', 'Отсутствует')}
            - Дата создания: {details.get('created_at', 'Неизвестно')}
            - Количество холдеров: {len(details.get('holders', []))}
            
            Результат анализа:
            - Вероятность скама: {analysis_result['scam_score']:.2f}
            - Статус: {"СКАМ" if analysis_result['is_scam'] else "Вероятно легитимный"}
            
            Факторы риска:
            {chr(10).join([f"- {factor}" for factor in analysis_result['risk_factors']])}
            
            Сгенерируй краткий профессиональный отчет (2-3 абзаца) о том, почему этот токен может быть или не быть скамом, 
            и какие действия следует предпринять инвесторам. Не используй технические термины.
            """
            
            # Вызов OpenAI API
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Ты - эксперт по криптовалютам и безопасности инвестиций."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            report = response.choices[0].message.content
            return report
        except Exception as e:
            logger.error(f"Failed to generate scam report: {str(e)}")
            return f"Не удалось сгенерировать отчет: {str(e)}"
