# 🐍 Установка Python для Windows

## 🚨 Проблема
Python установлен некорректно - файл python.exe имеет нулевой размер.

## ✅ Решение: Переустановка Python

### 1. Скачайте Python
Перейдите на https://www.python.org/downloads/

### 2. Запустите установщик
- Скачайте Python 3.11 или 3.12
- Запустите установщик от имени администратора

### 3. ВАЖНО: Настройте установку
- ✅ **Обязательно** отметьте "Add Python to PATH"
- ✅ Отметьте "Install for all users"
- ✅ Выберите "Customize installation"

### 4. Дополнительные опции
- ✅ Documentation
- ✅ pip
- ✅ tcl/tk and IDLE
- ✅ Python test suite
- ✅ py launcher
- ✅ for all users

### 5. Проверка установки
После установки откройте **НОВЫЙ** терминал и выполните:

```cmd
python --version
pip --version
```

Должны показать версии Python и pip.

## 🔄 Альтернативный способ: Microsoft Store

1. Откройте Microsoft Store
2. Поиск: "Python 3.11" или "Python 3.12"
3. Установите официальное приложение
4. Перезапустите терминал

## 🐳 Docker альтернатива

Если Python не устанавливается:

```cmd
docker-compose up --build
```

## 📱 Google Colab альтернатива

1. Откройте `aether_os_colab.ipynb`
2. Нажмите "Open in Colab"
3. Runtime → Run all

---

**После правильной установки Python:**
```cmd
cd c:/Users/imedoff/Documents/Project/githab/ton-tx-dsl-main
python run_full_test.py
```
