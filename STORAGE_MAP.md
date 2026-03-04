# 📁 Карта хранения данных проекта

## 🗂️ **Структура файлов и папок:**

```
ton-tx-dsl-main/
├── 📄 Основной код проекта
│   ├── engine.py                    # DAG оркестратор (10KB)
│   ├── config.py                    # Конфигурация (5KB)
│   ├── ton_service.py               # TON интеграция (7KB)
│   ├── AetherVault.tact             # TON контракт (23KB)
│   ├── AetherOracle.tact            # TON контракт (21KB)
│   ├── AetherGovernance.tact       # TON контракт (16KB)
│   ├── MEGA_TEST.py                 # Мега-тест (15KB)
│   └── telegram_bot_simple.py      # Telegram бот (9KB)
│
├── 📊 Система управления проектом
│   ├── project_manager.py           # Главный менеджер (9KB)
│   ├── progress_tracker.py          # Трекер прогресса (8KB)
│   ├── backup_system.py             # Бэкап система (5KB)
│   ├── cloud_sync.py                # Облачная синхронизация (9KB)
│   └── .project_manager.json        # Состояние проекта (855B)
│
├── 📈 Прогресс и метрики
│   └── .progress/
│       └── development_log.json     # Вся история разработки (8KB)
│
├── 💾 Бэкапы
│   └── backups/
│       ├── aether_ton_backup_20260304_181711.zip    # 93KB
│       ├── aether_ton_backup_20260304_181711_metadata.json
│       ├── aether_ton_backup_20260304_181849.zip    # 100KB
│       └── aether_ton_backup_20260304_181849_metadata.json
│
├── 📋 Отчеты
│   ├── development_report_20260304_181625.json     # 5KB
│   ├── project_report_20260304_181849.json         # 3KB
│   ├── FINAL_ANALYSIS_REPORT.md      # 6KB
│   └── test_report.json              # 255B
│
└── 🔧 Конфигурация
    ├── requirements.txt              # Зависимости
    ├── package.json                  # Node.js конфиг
    ├── .env.example                  # Пример окружения
    └── .cloud_sync.json              # Конфиг синхронизации
```

## 📊 **Что хранится где:**

### 🎯 **`.project_manager.json`** - Главное состояние:
```json
{
  "project_name": "Aether OS + TON TX DSL",
  "version": "1.0.0", 
  "status": "development",
  "sessions_completed": 1,
  "features": {
    "dag_orchestrator": "completed",
    "ton_integration": "completed",
    "smart_contracts": "completed",
    "telegram_bot": "completed",
    "security_filters": "completed",
    "performance_optimization": "completed",
    "progress_tracking": "completed",
    "backup_system": "completed",
    "cloud_sync": "completed"
  },
  "metrics": {
    "test_coverage": "100%",
    "performance": "28074 tasks/sec",
    "security_score": "200%",
    "system_status": "production_ready"
  },
  "backups_count": 4
}
```

### 📈 **`.progress/development_log.json`** - Вся история:
- Все сессии разработки
- Каждое изменение в коде
- Результаты всех тестов
- Важные milestones
- Временные метки

### 💾 **`backups/*.zip`** - Полные бэкапы:
- Все важные файлы проекта
- Весь код и конфигурации
- История прогресса
- Метаданные бэкапов

### 📋 **`*_report.json`** - Отчеты:
- Детальная статистика
- Метрики производительности
- Результаты тестирования
- Анализ проекта

## 🔄 **Автоматическое сохранение:**

### ✅ **Каждое действие:**
- Добавление фичи → бэкап
- Тестирование → сохранение результатов
- Milestone → запись в прогресс
- Конец сессии → финальный бэкап

### 📊 **Метрики:**
- **106 файлов** в проекте
- **4 бэкапа** созданы
- **9 фич** завершено
- **100% тестов** прошло
- **28,074 tasks/sec** производительность

## 🌐 **Облачное хранение (настройка):**

### 📤 **GitHub:**
```python
manager.enable_cloud_sync("github", 
    repo_url="https://github.com/user/aether-ton-dsl",
    token="your_github_token"
)
```

### 📦 **Dropbox:**
```python
manager.enable_cloud_sync("dropbox",
    access_token="your_dropbox_token", 
    folder="/Aether_TON_DSL"
)
```

## 🎯 **ИТОГ:**

**Всё хранится в 4 местах:**
1. **Локальные файлы** - основной код
2. **`.progress/`** - история разработки  
3. **`backups/`** - полные копии
4. **Облако** - синхронизация (настройка)

**Ничего не теряется!** Вся работа автоматически сохраняется и отслеживается.
