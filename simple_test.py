"""
Простой тест для проверки базовой функциональности
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Тест импортов"""
    try:
        from engine import Task, TaskStatus, MemoryTaskStore, MockAgentRunner
        print("[OK] Базовые импорты работают")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка импорта: {e}")
        return False

def test_task_creation():
    """Тест создания задачи"""
    try:
        from engine import Task, TaskStatus
        task = Task(id="test_task", payload={"test": "data"})
        print(f"[OK] Задача создана: {task.id}, статус: {task.status}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка создания задачи: {e}")
        return False

def test_memory_store():
    """Тест хранилища в памяти"""
    try:
        from engine import Task, MemoryTaskStore
        store = MemoryTaskStore()
        task = Task(id="store_test")
        
        import asyncio
        async def test_store():
            await store.set(task)
            retrieved = await store.get("store_test")
            return retrieved is not None
        
        result = asyncio.run(test_store())
        if result:
            print("[OK] Хранилище в памяти работает")
            return True
        else:
            print("[ERROR] Хранилище в памяти не работает")
            return False
    except Exception as e:
        print(f"[ERROR] Ошибка хранилища: {e}")
        return False

def main():
    """Запуск простых тестов"""
    print("Запуск простых тестов Aether OS")
    print("=" * 40)
    
    tests = [
        ("Импорты", test_imports),
        ("Создание задачи", test_task_creation),
        ("Хранилище в памяти", test_memory_store),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        print(f"\n[TEST] Тест: {name}")
        if test_func():
            passed += 1
        else:
            print(f"[ERROR] Тест '{name}' не пройден")
    
    print("\n" + "=" * 40)
    print(f"[RESULT] Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("[SUCCESS] Все тесты пройдены!")
        return True
    else:
        print("[WARNING] Некоторые тесты не пройдены")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
