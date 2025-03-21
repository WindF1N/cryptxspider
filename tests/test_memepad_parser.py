import sys
import os
import unittest
import asyncio
from unittest.mock import patch, MagicMock

# Добавляем родительский каталог в пути импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptxspider.memepad.parser import MemepadParser


class TestMemepadParser(unittest.TestCase):
    """Тесты для MemepadParser."""

    def setUp(self):
        """Настройка перед каждым тестом."""
        self.parser = MemepadParser()
        
        # Мок-данные для тестирования
        self.jettons_mock_data = {
            "jettons": [
                {
                    "address": "EQA_test1",
                    "ticker": "TEST1",
                    "short_name": "test1",
                    "name": "Test Token 1"
                },
                {
                    "address": "EQA_test2",
                    "ticker": "TEST2",
                    "short_name": "test2",
                    "name": "Test Token 2"
                }
            ]
        }
        
        self.jetton_details_mock = {
            "address": "EQA_test1",
            "ticker": "TEST1",
            "short_name": "test1",
            "name": "Test Token 1",
            "description": "This is a test token",
            "holders": [
                {"address": "EQA_holder1", "percent": 60},
                {"address": "EQA_holder2", "percent": 40}
            ],
            "socials": [
                {"type": "TELEGRAM", "url": "https://t.me/test_token"}
            ]
        }
        
        self.reactions_mock = {"fire": 10, "rocket": 5}
        
        self.transactions_mock = {
            "transactions": [
                {
                    "hash": "tx1",
                    "from": "EQA_holder1",
                    "to": "EQA_holder2",
                    "amount": 100
                }
            ]
        }
        
        self.stonfi_mock = {
            "liquidity": {"usd": 5000},
            "price": {"usd": 0.1}
        }

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_jettons(self, mock_get):
        """Тест получения списка токенов."""
        # Настраиваем мок
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json.return_value = self.jettons_mock_data
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Вызываем тестируемый метод
        result = await self.parser.fetch_jettons("jetton/spotlight")
        
        # Проверяем результаты
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["ticker"], "TEST1")
        self.assertEqual(result[1]["ticker"], "TEST2")

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_jetton_details(self, mock_get):
        """Тест получения деталей токена."""
        # Настраиваем мок
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json.return_value = self.jetton_details_mock
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Вызываем тестируемый метод
        result = await self.parser.fetch_jetton_details("test1")
        
        # Проверяем результаты
        self.assertEqual(result["ticker"], "TEST1")
        self.assertEqual(result["name"], "Test Token 1")
        self.assertEqual(len(result["holders"]), 2)

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_reactions(self, mock_get):
        """Тест получения реакций токена."""
        # Настраиваем мок
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json.return_value = self.reactions_mock
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Вызываем тестируемый метод
        result = await self.parser.fetch_reactions("test1")
        
        # Проверяем результаты
        self.assertEqual(result["fire"], 10)
        self.assertEqual(result["rocket"], 5)

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_transactions(self, mock_get):
        """Тест получения транзакций токена."""
        # Настраиваем мок
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json.return_value = self.transactions_mock
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Вызываем тестируемый метод
        result = await self.parser.fetch_transactions("test1")
        
        # Проверяем результаты
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["hash"], "tx1")

    @patch('aiohttp.ClientSession.get')
    async def test_fetch_stonfi_data(self, mock_get):
        """Тест получения данных Ston.fi."""
        # Настраиваем мок
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json.return_value = self.stonfi_mock
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Вызываем тестируемый метод
        result = await self.parser.fetch_stonfi_data("EQA_test1")
        
        # Проверяем результаты
        self.assertEqual(result["liquidity"]["usd"], 5000)
        self.assertEqual(result["price"]["usd"], 0.1)

    @patch('cryptxspider.memepad.parser.MemepadParser.fetch_jetton_details')
    @patch('cryptxspider.memepad.parser.MemepadParser.fetch_reactions')
    @patch('cryptxspider.memepad.parser.MemepadParser.fetch_transactions')
    @patch('cryptxspider.memepad.parser.MemepadParser.fetch_stonfi_data')
    async def test_get_complete_jetton_data(self, mock_stonfi, mock_tx, mock_reactions, mock_details):
        """Тест получения полных данных о токене."""
        # Настраиваем моки
        mock_details.return_value = self.jetton_details_mock
        mock_reactions.return_value = self.reactions_mock
        mock_tx.return_value = self.transactions_mock["transactions"]
        mock_stonfi.return_value = self.stonfi_mock
        
        # Вызываем тестируемый метод
        result = await self.parser.get_complete_jetton_data("test1", "EQA_test1")
        
        # Проверяем результаты
        self.assertEqual(result["details"], self.jetton_details_mock)
        self.assertEqual(result["reactions"], self.reactions_mock)
        self.assertEqual(result["transactions"], self.transactions_mock["transactions"])
        self.assertEqual(result["stonfi_data"], self.stonfi_mock)


def run_tests():
    """Запуск тестов."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMemepadParser)
    runner = unittest.TextTestRunner()
    runner.run(suite)


if __name__ == "__main__":
    # В Python 3.8+ можно использовать следующее:
    asyncio.run(unittest.main()) 