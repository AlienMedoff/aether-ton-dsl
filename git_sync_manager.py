#!/usr/bin/env python3
"""
Git Sync Manager - автоматическая синхронизация с GitHub
Сохраняет все изменения в конце сессии
"""

import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

class GitSyncManager:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.git_config = self.project_dir / ".git_sync_config.json"
        
        # Загрузим конфигурацию
        self.load_config()
        
        # GitHub токен и репозиторий
        self.github_token = self.config.get("github_token", "")
        self.github_username = self.config.get("github_username", "AlienMedoff")
        self.repo_name = "aether-ton-dsl"
        
    def load_config(self):
        """Загрузить конфигурацию"""
        if self.git_config.exists():
            with open(self.git_config, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "auto_sync": True,
                "sync_on_exit": True,
                "commit_message_template": "Auto sync - {timestamp}",
                "github_token": "",
                "github_username": "AlienMedoff",
                "last_sync": None,
                "sync_count": 0
            }
    
    def save_config(self):
        """Сохранить конфигурацию"""
        with open(self.git_config, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def setup_git_repository(self) -> bool:
        """Настроить Git репозиторий"""
        try:
            # Инициализируем Git если нужно
            if not (self.project_dir / ".git").exists():
                result = subprocess.run(["git", "init"], cwd=self.project_dir, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Git init failed: {result.stderr}")
                    return False
                print("Git repository initialized")
            
            # Настраиваем user info
            subprocess.run(["git", "config", "user.name", "Aether OS Bot"], cwd=self.project_dir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "bot@aether-os.com"], cwd=self.project_dir, capture_output=True)
            
            # Добавляем remote
            remote_url = f"https://{self.github_username}:{self.github_token}@github.com/{self.github_username}/{self.repo_name}.git"
            
            # Проверяем существует ли remote
            result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=self.project_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=self.project_dir, capture_output=True)
                print("GitHub remote added")
            else:
                # Обновляем URL remote
                subprocess.run(["git", "remote", "set-url", "origin", remote_url], cwd=self.project_dir, capture_output=True)
                print("GitHub remote updated")
            
            return True
            
        except Exception as e:
            print(f"Git setup error: {e}")
            return False
    
    def get_changed_files(self) -> List[str]:
        """Получить список измененных файлов"""
        try:
            # Проверяем статус
            result = subprocess.run(["git", "status", "--porcelain"], cwd=self.project_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                return []
            
            changed_files = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    # Формат: XY filename
                    if len(line) > 3:
                        filename = line[3:]
                        changed_files.append(filename)
            
            return changed_files
            
        except Exception as e:
            print(f"Error getting changed files: {e}")
            return []
    
    def add_and_commit(self, message: str = None) -> bool:
        """Добавить изменения и закоммитить"""
        try:
            # Добавляем все файлы
            result = subprocess.run(["git", "add", "."], cwd=self.project_dir, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Git add failed: {result.stderr}")
                return False
            
            # Проверяем есть ли изменения для коммита
            result = subprocess.run(["git", "status", "--porcelain"], cwd=self.project_dir, capture_output=True, text=True)
            if not result.stdout.strip():
                print("No changes to commit")
                return True
            
            # Создаем коммит
            if not message:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = f"Auto sync - {timestamp}"
            
            result = subprocess.run(["git", "commit", "-m", message], cwd=self.project_dir, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Git commit failed: {result.stderr}")
                return False
            
            print(f"Changes committed: {message}")
            return True
            
        except Exception as e:
            print(f"Commit error: {e}")
            return False
    
    def push_to_github(self, branch: str = "main") -> bool:
        """Отправить изменения на GitHub"""
        try:
            # Отправляем на GitHub
            result = subprocess.run(["git", "push", "origin", branch], cwd=self.project_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Git push failed: {result.stderr}")
                return False
            
            print(f"Changes pushed to GitHub: {branch}")
            return True
            
        except Exception as e:
            print(f"Push error: {e}")
            return False
    
    def pull_from_github(self, branch: str = "main") -> bool:
        """Получить изменения с GitHub"""
        try:
            result = subprocess.run(["git", "pull", "origin", branch], cwd=self.project_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Git pull failed: {result.stderr}")
                return False
            
            print(f"Changes pulled from GitHub: {branch}")
            return True
            
        except Exception as e:
            print(f"Pull error: {e}")
            return False
    
    def sync_to_github(self, message: str = None) -> Dict[str, Any]:
        """Полная синхронизация с GitHub"""
        if not self.github_token:
            return {"success": False, "error": "No GitHub token configured"}
        
        # Настраиваем Git
        if not self.setup_git_repository():
            return {"success": False, "error": "Git setup failed"}
        
        # Получаем изменения
        changed_files = self.get_changed_files()
        
        if not changed_files:
            return {"success": True, "message": "No changes to sync"}
        
        # Коммитим и пушим
        if self.add_and_commit(message):
            if self.push_to_github():
                # Обновляем статистику
                self.config["last_sync"] = datetime.now().isoformat()
                self.config["sync_count"] += 1
                self.save_config()
                
                return {
                    "success": True,
                    "message": "Successfully synced to GitHub",
                    "files_synced": len(changed_files),
                    "sync_count": self.config["sync_count"]
                }
            else:
                return {"success": False, "error": "Push to GitHub failed"}
        else:
            return {"success": False, "error": "Commit failed"}
    
    def auto_sync_on_exit(self) -> bool:
        """Автоматическая синхронизация при выходе"""
        if not self.config.get("sync_on_exit", True):
            return True
        
        print("🔄 Auto-syncing to GitHub before exit...")
        
        result = self.sync_to_github("Auto sync on session end")
        
        if result["success"]:
            print(f"✅ {result['message']}")
            return True
        else:
            print(f"❌ Sync failed: {result['error']}")
            return False
    
    def setup_github_token(self, token: str, username: str = None):
        """Настроить GitHub токен"""
        self.config["github_token"] = token
        if username:
            self.config["github_username"] = username
        self.github_token = token
        if username:
            self.github_username = username
        self.save_config()
        print("GitHub token configured")
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Получить статус синхронизации"""
        changed_files = self.get_changed_files()
        
        return {
            "github_configured": bool(self.github_token),
            "github_username": self.github_username,
            "repo_url": f"https://github.com/{self.github_username}/{self.repo_name}",
            "last_sync": self.config.get("last_sync"),
            "sync_count": self.config.get("sync_count", 0),
            "auto_sync_enabled": self.config.get("auto_sync", True),
            "sync_on_exit": self.config.get("sync_on_exit", True),
            "changed_files": len(changed_files),
            "git_initialized": (self.project_dir / ".git").exists()
        }

# Использование
if __name__ == "__main__":
    sync_manager = GitSyncManager()
    
    print("🔄 Git Sync Manager")
    print("=" * 40)
    
    # Показываем статус
    status = sync_manager.get_sync_status()
    print(f"GitHub configured: {status['github_configured']}")
    print(f"Repository: {status['repo_url']}")
    print(f"Last sync: {status['last_sync']}")
    print(f"Sync count: {status['sync_count']}")
    print(f"Changed files: {status['changed_files']}")
    
    # Настраиваем токен если нужно
    if not status["github_configured"]:
        print("\nTo configure GitHub sync:")
        print("sync_manager.setup_github_token('your_token', 'your_username')")
    else:
        # Тестовая синхронизация
        print("\nTesting sync...")
        result = sync_manager.sync_to_github("Test sync from Git manager")
        if result["success"]:
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['error']}")
    
    print("\nGit sync system ready!")
