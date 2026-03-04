# 🐳 Docker Setup для Aether OS

## 📦 Установка Docker

### 1. Docker Desktop (рекомендуется)
- Скачай: https://www.docker.com/products/docker-desktop/
- Установи (не требует прав админа)
- Перезапусти терминал

### 2. Проверка установки
```cmd
docker --version
docker-compose --version
```

## 🚀 Запуск Aether OS

### Шаг 1: Создай .env файл
Создай файл `.env` в корне проекта:
```env
TON_MODE=MOCK
TON_API_ENDPOINT=https://testnet.toncenter.com/api/v2
TON_API_KEY=mock_key_for_testing
REDIS_HOST=localhost
REDIS_PORT=6379
AGENT_ID=TransactionExecutorAgent
```

### Шаг 2: Запуск
```cmd
# Из папки проекта
docker-compose up --build
```

### Шаг 3: Тестирование
```cmd
# Запуск тестов в контейнере
docker-compose exec transaction-executor python -m pytest tests/test_engine.py -v

# Запуск демонстрации
docker-compose exec transaction-executor python main.py
```

## 📊 Что запустится:

1. **Redis** - база данных для состояния
2. **Transaction Executor Agent** - исполнитель транзакций
3. **Rollback Agent** - агент отката
4. **State Validator Agent** - валидатор состояния

## 🔍 Полезные команды

```cmd
# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Удаление всех данных
docker-compose down -v
```

## 🎯 Ожидаемый результат

После запуска увидите:
- ✅ Redis запущен на порту 6379
- ✅ 3 агента работают
- ✅ Тесты проходят
- ✅ DAG оркестрация функционирует

---

**Если Docker не устанавливается:** используй Google Colab с `aether_os_colab.ipynb`
