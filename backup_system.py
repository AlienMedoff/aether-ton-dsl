#!/usr/bin/env python3
"""
Backup System - создает бэкапы всей разработки
Автоматически сохраняет важные файлы и прогресс
"""

import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List

class BackupSystem:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.backup_dir = self.project_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Важные файлы для бэкапа
        self.important_files = [
            "*.py",
            "*.tact", 
            "*.ts",
            "*.md",
            "*.json",
            "*.env.example",
            "requirements.txt",
            "pytest.ini",
            "Dockerfile",
            "docker-compose.yml"
        ]
        
        # Папки для бэкапа
        self.important_dirs = [
            "common",
            "tests"
        ]
    
    def create_backup(self, description: str = None) -> str:
        """Создать полный бэкап проекта"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"aether_ton_backup_{timestamp}"
        backup_path = self.backup_dir / f"{backup_name}.zip"
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Добавляем файлы по паттернам
            for pattern in self.important_files:
                for file_path in self.project_dir.glob(pattern):
                    if file_path.is_file() and file_path.parent != self.backup_dir:
                        zipf.write(file_path, file_path.relative_to(self.project_dir))
            
            # Добавляем папки
            for dir_name in self.important_dirs:
                dir_path = self.project_dir / dir_name
                if dir_path.exists() and dir_path.is_dir():
                    for file_path in dir_path.rglob("*"):
                        if file_path.is_file():
                            zipf.write(file_path, file_path.relative_to(self.project_dir))
            
            # Добавляем прогресс
            progress_file = self.project_dir / ".progress" / "development_log.json"
            if progress_file.exists():
                zipf.write(progress_file, progress_file.relative_to(self.project_dir))
        
        # Создаем метаданные бэкапа
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "backup_name": backup_name,
            "description": description or "Automatic backup",
            "files_count": len([f for f in self.project_dir.rglob("*") if f.is_file()]),
            "project_status": "production_ready"
        }
        
        metadata_file = self.backup_dir / f"{backup_name}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return str(backup_path)
    
    def list_backups(self) -> List[dict]:
        """Показать все бэкапы"""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.zip"):
            metadata_file = backup_file.with_suffix('.zip_metadata.json')
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = {
                    "backup_name": backup_file.stem,
                    "timestamp": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat(),
                    "description": "Legacy backup"
                }
            
            backups.append({
                "file": str(backup_file),
                "size": backup_file.stat().st_size,
                **metadata
            })
        
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)
    
    def restore_backup(self, backup_name: str, target_dir: str = None):
        """Восстановить из бэкапа"""
        if target_dir is None:
            target_dir = self.project_dir / f"restored_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            target_dir = Path(target_dir)
        
        backup_file = self.backup_dir / f"{backup_name}.zip"
        
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup {backup_name} not found")
        
        with zipfile.ZipFile(backup_file, 'r') as zipf:
            zipf.extractall(target_dir)
        
        return str(target_dir)
    
    def auto_backup(self):
        """Автоматический бэкап при важных изменениях"""
        return self.create_backup("Auto backup after changes")

# Использование
if __name__ == "__main__":
    backup = BackupSystem()
    
    # Создадим бэкап
    backup_path = backup.create_backup("Full system backup - 100% ready")
    print(f"Backup created: {backup_path}")
    
    # Покажем все бэкапы
    backups = backup.list_backups()
    print(f"\nTotal backups: {len(backups)}")
    for i, b in enumerate(backups[:3]):  # Показываем последние 3
        print(f"{i+1}. {b['backup_name']} - {b['description']}")
        print(f"   Size: {b['size']:,} bytes")
        print(f"   Date: {b['timestamp']}")
    
    # Автоматический бэкап
    auto_backup_path = backup.auto_backup()
    print(f"\nAuto backup created: {auto_backup_path}")
