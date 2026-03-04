import sys
import os
from pathlib import Path

print("🔍 Поиск Python...")
print(f"Current Python: {sys.executable}")
print(f"Python version: {sys.version}")
print()

# Поиск в стандартных местах
search_paths = [
    r"C:\Python39\python.exe",
    r"C:\Python310\python.exe", 
    r"C:\Python311\python.exe",
    r"C:\Python312\python.exe",
    r"C:\Program Files\Python39\python.exe",
    r"C:\Program Files\Python310\python.exe",
    r"C:\Program Files\Python311\python.exe",
    r"C:\Program Files\Python312\python.exe",
    r"C:\Program Files (x86)\Python39\python.exe",
    r"C:\Program Files (x86)\Python310\python.exe",
    r"C:\Program Files (x86)\Python311\python.exe",
    r"C:\Program Files (x86)\Python312\python.exe",
]

found = []
for path in search_paths:
    if os.path.exists(path):
        found.append(path)
        print(f"✅ Найден: {path}")

if not found:
    print("❌ Python не найден в стандартных местах")
    
    # Проверка PATH
    print("\n📁 Проверка PATH...")
    env_path = os.environ.get('PATH', '').split(os.pathsep)
    for p in env_path:
        if 'python' in p.lower():
            print(f"📂 {p}")
            python_exe = os.path.join(p, 'python.exe')
            if os.path.exists(python_exe):
                print(f"  ✅ {python_exe}")
                found.append(python_exe)

if found:
    print(f"\n🎯 Найдено версий Python: {len(found)}")
    print("Используйте полный путь для запуска:")
    for i, path in enumerate(found, 1):
        print(f"  {i}. {path}")
else:
    print("\n❌ Python не найден. Пожалуйста, установите Python с https://python.org")
    print("Убедитесь что 'Add Python to PATH' отмечено при установке.")
