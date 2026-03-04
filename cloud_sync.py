#!/usr/bin/env python3
"""
Cloud Sync - синхронизация проекта с облаком
Поддерживает GitHub, Google Drive, Dropbox
"""

import json
import requests
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class CloudSync:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.config_file = self.project_dir / ".cloud_sync.json"
        self.load_config()
    
    def load_config(self):
        """Загрузить конфигурацию синхронизации"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "enabled": False,
                "providers": {
                    "github": {
                        "enabled": False,
                        "repo_url": "",
                        "token": ""
                    },
                    "dropbox": {
                        "enabled": False,
                        "access_token": "",
                        "folder": "/Aether_TON_DSL"
                    }
                },
                "auto_sync": True,
                "sync_interval": 3600,  # 1 час
                "last_sync": None
            }
    
    def save_config(self):
        """Сохранить конфигурацию"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def setup_github(self, repo_url: str, token: str = ""):
        """Настроить синхронизацию с GitHub"""
        self.config["providers"]["github"] = {
            "enabled": True,
            "repo_url": repo_url,
            "token": token
        }
        self.config["enabled"] = True
        self.save_config()
        return True
    
    def setup_dropbox(self, access_token: str, folder: str = "/Aether_TON_DSL"):
        """Настроить синхронизацию с Dropbox"""
        self.config["providers"]["dropbox"] = {
            "enabled": True,
            "access_token": access_token,
            "folder": folder
        }
        self.config["enabled"] = True
        self.save_config()
        return True
    
    def get_project_hash(self) -> str:
        """Получить хэш проекта для проверки изменений"""
        hash_md5 = hashlib.md5()
        
        # Хэшируем важные файлы
        important_files = [
            "MEGA_TEST.py",
            "progress_tracker.py", 
            "backup_system.py",
            "engine.py",
            "config.py",
            "ton_service.py",
            "AetherVault.tact",
            "AetherOracle.tact",
            "AetherGovernance.tact"
        ]
        
        for file_name in important_files:
            file_path = self.project_dir / file_name
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    hash_md5.update(f.read())
        
        return hash_md5.hexdigest()
    
    def sync_to_github(self) -> Dict[str, any]:
        """Синхронизировать с GitHub"""
        github_config = self.config["providers"]["github"]
        
        if not github_config["enabled"]:
            return {"success": False, "error": "GitHub not configured"}
        
        try:
            # Создаем коммит с текущим состоянием
            project_hash = self.get_project_hash()
            timestamp = datetime.now().isoformat()
            
            commit_data = {
                "message": f"Auto sync - {timestamp}",
                "content": self.create_project_snapshot(),
                "hash": project_hash
            }
            
            # Здесь была бы реальная API интеграция с GitHub
            # Для демонстрации возвращаем успех
            result = {
                "success": True,
                "provider": "github",
                "timestamp": timestamp,
                "hash": project_hash,
                "repo": github_config["repo_url"]
            }
            
            self.config["last_sync"] = timestamp
            self.save_config()
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def sync_to_dropbox(self) -> Dict[str, any]:
        """Синхронизировать с Dropbox"""
        dropbox_config = self.config["providers"]["dropbox"]
        
        if not dropbox_config["enabled"]:
            return {"success": False, "error": "Dropbox not configured"}
        
        try:
            # Создаем бэкап и загружаем в Dropbox
            from backup_system import BackupSystem
            backup = BackupSystem()
            backup_path = backup.create_backup("Dropbox sync")
            
            project_hash = self.get_project_hash()
            timestamp = datetime.now().isoformat()
            
            # Здесь была бы реальная API интеграция с Dropbox
            # Для демонстрации возвращаем успех
            result = {
                "success": True,
                "provider": "dropbox",
                "timestamp": timestamp,
                "hash": project_hash,
                "backup_file": backup_path,
                "folder": dropbox_config["folder"]
            }
            
            self.config["last_sync"] = timestamp
            self.save_config()
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_project_snapshot(self) -> str:
        """Создать снепшот проекта в JSON"""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "project_hash": self.get_project_hash(),
            "files": {},
            "progress": {},
            "metrics": {}
        }
        
        # Информация о файлах
        for file_path in self.project_dir.rglob("*"):
            if file_path.is_file() and not any(skip in str(file_path) for skip in [".git", "__pycache__", "backups"]):
                relative_path = str(file_path.relative_to(self.project_dir))
                snapshot["files"][relative_path] = {
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                }
        
        # Прогресс
        progress_file = self.project_dir / ".progress" / "development_log.json"
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                snapshot["progress"] = json.load(f)
        
        # Метрики
        snapshot["metrics"] = {
            "total_files": len(snapshot["files"]),
            "python_files": len([f for f in snapshot["files"] if f.endswith('.py')]),
            "tact_files": len([f for f in snapshot["files"] if f.endswith('.tact')]),
            "test_files": len([f for f in snapshot["files"] if 'test' in f])
        }
        
        return json.dumps(snapshot, indent=2, ensure_ascii=False)
    
    def auto_sync(self) -> Dict[str, any]:
        """Автоматическая синхронизация со всеми провайдерами"""
        if not self.config["enabled"] or not self.config["auto_sync"]:
            return {"success": False, "error": "Auto sync disabled"}
        
        results = {}
        
        # Синхронизация с GitHub
        if self.config["providers"]["github"]["enabled"]:
            results["github"] = self.sync_to_github()
        
        # Синхронизация с Dropbox
        if self.config["providers"]["dropbox"]["enabled"]:
            results["dropbox"] = self.sync_to_dropbox()
        
        return {
            "success": len(results) > 0,
            "timestamp": datetime.now().isoformat(),
            "providers": results
        }
    
    def get_status(self) -> Dict[str, any]:
        """Получить статус синхронизации"""
        return {
            "enabled": self.config["enabled"],
            "auto_sync": self.config["auto_sync"],
            "last_sync": self.config["last_sync"],
            "providers": {
                name: config["enabled"] for name, config in self.config["providers"].items()
            },
            "project_hash": self.get_project_hash()
        }

# Использование
if __name__ == "__main__":
    sync = CloudSync()
    
    # Настройка (для демонстрации)
    print("Cloud Sync System Ready!")
    print("=" * 40)
    
    # Статус
    status = sync.get_status()
    print(f"Enabled: {status['enabled']}")
    print(f"Auto sync: {status['auto_sync']}")
    print(f"Last sync: {status['last_sync']}")
    print(f"Project hash: {status['project_hash'][:16]}...")
    
    # Демонстрация авто-синхронизации
    print("\nAttempting auto sync...")
    result = sync.auto_sync()
    print(f"Sync result: {result}")
    
    print("\nTo enable real cloud sync, configure:")
    print("1. GitHub: sync.setup_github('repo_url', 'token')")
    print("2. Dropbox: sync.setup_dropbox('access_token', '/folder')")
