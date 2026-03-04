#!/usr/bin/env python3
"""
Session Manager - управление сессиями с безопасностью и синхронизацией
Автоматически сохраняет и синхронизирует всю работу
"""

import json
import atexit
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from security_enhancer import SecurityEnhancer
from git_sync_manager import GitSyncManager
from project_manager import ProjectManager

class SessionManager:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.session_file = self.project_dir / ".session" / "current_session.json"
        self.session_file.parent.mkdir(exist_ok=True)
        
        # Инициализируем подсистемы
        self.security = SecurityEnhancer(project_dir)
        self.git_sync = GitSyncManager(project_dir)
        self.project = ProjectManager(project_dir)
        
        # Загружаем текущую сессию
        self.load_session()
        
        # Регистрируем обработчики выхода
        self.register_exit_handlers()
        
        print(f"🚀 Session Manager initialized")
        print(f"📁 Project: {self.project_dir}")
        print(f"🔒 Security: Enabled")
        print(f"🔄 Git Sync: {self.git_sync.get_sync_status()['github_configured']}")
    
    def load_session(self):
        """Загрузить текущую сессию"""
        if self.session_file.exists():
            with open(self.session_file, 'r') as f:
                self.session = json.load(f)
        else:
            self.session = {
                "id": self.generate_session_id(),
                "started_at": datetime.now().isoformat(),
                "activities": [],
                "security_scans": 0,
                "sync_count": 0,
                "files_modified": set(),
                "status": "active"
            }
            self.save_session()
    
    def save_session(self):
        """Сохранить сессию"""
        self.session["last_activity"] = datetime.now().isoformat()
        if isinstance(self.session["files_modified"], set):
            self.session["files_modified"] = list(self.session["files_modified"])
        
        with open(self.session_file, 'w') as f:
            json.dump(self.session, f, indent=2, ensure_ascii=False)
    
    def generate_session_id(self) -> str:
        """Сгенерировать ID сессии"""
        import hashlib
        import time
        return hashlib.md5(f"{time.time()}".encode()).hexdigest()[:8]
    
    def register_exit_handlers(self):
        """Зарегистрировать обработчики выхода"""
        atexit.register(self.on_exit)
        
        # Обработчики сигналов
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, self.signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов"""
        print(f"\n📡 Received signal {signum}")
        self.on_exit()
        sys.exit(0)
    
    def on_exit(self):
        """Действия при выходе"""
        print("\n🔄 Session ending - performing cleanup...")
        
        try:
            # 1. Сканирование безопасности
            print("🔒 Running security scan...")
            security_results = self.security.scan_project_security()
            self.session["security_scans"] += 1
            self.session["last_security_scan"] = datetime.now().isoformat()
            
            # 2. Синхронизация с GitHub
            print("📤 Syncing to GitHub...")
            sync_result = self.git_sync.auto_sync_on_exit()
            if sync_result:
                self.session["sync_count"] += 1
            
            # 3. Сохранение прогресса
            print("💾 Saving project progress...")
            self.project.end_work_session("session_completed")
            
            # 4. Обновление статуса сессии
            self.session["status"] = "completed"
            self.session["ended_at"] = datetime.now().isoformat()
            self.save_session()
            
            # 5. Создание отчета
            self.create_session_report()
            
            print("✅ Session cleanup completed!")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
    
    def track_activity(self, activity_type: str, description: str, files: list = None):
        """Отследить активность в сессии"""
        activity = {
            "timestamp": datetime.now().isoformat(),
            "type": activity_type,  # code_change, test_run, security_scan, sync
            "description": description,
            "files": files or []
        }
        
        self.session["activities"].append(activity)
        
        # Добавляем файлы в список измененных
        if files:
            self.session["files_modified"].update(files)
        
        self.save_session()
        
        print(f"📝 Activity tracked: {activity_type} - {description}")
    
    def run_security_scan(self) -> Dict[str, Any]:
        """Запустить сканирование безопасности"""
        print("🔒 Running security scan...")
        
        results = self.security.scan_project_security()
        
        # Сохраняем результаты
        self.session["security_scans"] += 1
        self.session["last_security_result"] = {
            "score": results["average_security_score"],
            "level": results["security_level"],
            "critical_issues": results["critical_issues"]
        }
        
        self.track_activity("security_scan", f"Security scan - score: {results['average_security_score']}")
        
        return results
    
    def sync_to_github(self, message: str = None) -> Dict[str, Any]:
        """Синхронизировать с GitHub"""
        print("📤 Syncing to GitHub...")
        
        result = self.git_sync.sync_to_github(message)
        
        if result["success"]:
            self.session["sync_count"] += 1
            self.track_activity("sync", f"GitHub sync - {result.get('files_synced', 0)} files")
        
        return result
    
    def create_session_report(self) -> str:
        """Создать отчет о сессии"""
        duration = None
        if "ended_at" in self.session:
            start = datetime.fromisoformat(self.session["started_at"])
            end = datetime.fromisoformat(self.session["ended_at"])
            duration = str(end - start)
        
        report = f"""
# 📊 Session Report

**Session ID:** {self.session['id']}
**Status:** {self.session['status']}
**Started:** {self.session['started_at']}
**Ended:** {self.session.get('ended_at', 'N/A')}
**Duration:** {duration or 'N/A'}

## 📈 Activity Summary
- **Total Activities:** {len(self.session['activities'])}
- **Security Scans:** {self.session['security_scans']}
- **GitHub Syncs:** {self.session['sync_count']}
- **Files Modified:** {len(self.session['files_modified'])}

## 🔒 Security Summary
"""
        
        if "last_security_result" in self.session:
            sec = self.session["last_security_result"]
            report += f"- **Security Score:** {sec['score']}/100\n"
            report += f"- **Security Level:** {sec['level']}\n"
            report += f"- **Critical Issues:** {sec['critical_issues']}\n"
        
        report += "\n## 📝 Recent Activities\n"
        
        for activity in self.session["activities"][-5:]:  # Последние 5 активностей
            report += f"- **{activity['timestamp'][:19]}** {activity['type']}: {activity['description']}\n"
        
        report += f"\n## 📁 Modified Files\n"
        
        for file_path in list(self.session["files_modified"])[:10]:  # Первые 10 файлов
            report += f"- {file_path}\n"
        
        # Сохраняем отчет
        report_file = self.project_dir / f"session_report_{self.session['id']}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return str(report_file)
    
    def get_session_status(self) -> Dict[str, Any]:
        """Получить статус сессии"""
        return {
            "session_id": self.session["id"],
            "status": self.session["status"],
            "started_at": self.session["started_at"],
            "activities_count": len(self.session["activities"]),
            "security_scans": self.session["security_scans"],
            "sync_count": self.session["sync_count"],
            "files_modified": len(self.session["files_modified"]),
            "git_sync_status": self.git_sync.get_sync_status(),
            "last_activity": self.session.get("last_activity")
        }

# Глобальный менеджер сессии
_session_manager = None

def init_session_manager(project_dir: str = ".") -> SessionManager:
    """Инициализировать глобальный менеджер сессии"""
    global _session_manager
    _session_manager = SessionManager(project_dir)
    return _session_manager

def get_session_manager() -> Optional[SessionManager]:
    """Получить глобальный менеджер сессии"""
    return _session_manager

def track_activity(activity_type: str, description: str, files: list = None):
    """Отследить активность (удобная функция)"""
    if _session_manager:
        _session_manager.track_activity(activity_type, description, files)

# Использование
if __name__ == "__main__":
    # Инициализация
    session = init_session_manager()
    
    print("🚀 Session Manager Demo")
    print("=" * 40)
    
    # Показываем статус
    status = session.get_session_status()
    print(f"Session ID: {status['session_id']}")
    print(f"Status: {status['status']}")
    print(f"Activities: {status['activities_count']}")
    
    # Тестовая активность
    track_activity("code_change", "Added session manager", ["session_manager.py"])
    
    # Тестовое сканирование безопасности
    security_results = session.run_security_scan()
    print(f"Security score: {security_results['average_security_score']}")
    
    # Тестовая синхронизация
    sync_result = session.sync_to_github("Test sync from session manager")
    print(f"Sync result: {sync_result['success']}")
    
    print("\n✅ Session manager is active!")
    print("🔄 All changes will be automatically saved on exit")
    print("🔒 Security scans will run automatically")
    print("📤 GitHub sync will happen automatically")
