#!/usr/bin/env python3
"""
Security Enhancer - усиление безопасности проекта
Шифрование, контроль доступа, аудит безопасности
"""

import json
import hashlib
import secrets
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import re

class SecurityEnhancer:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.security_file = self.project_dir / ".security" / "security_config.json"
        self.security_file.parent.mkdir(exist_ok=True)
        
        # Загрузим конфигурацию безопасности
        self.load_security_config()
        
        # Опасные паттерны
        self.dangerous_patterns = [
            r'rm\s+-rf\s+/',           # Удаление системы
            r'drop\s+table',           # SQL инъекции
            r'eval\s*\(',             # Eval инъекции
            r'exec\s*\(',             # Exec инъекции
            r'system\s*\(',           # System вызовы
            r'__import__\s*\(',       # Динамический импорт
            r'open\s*\(\s*[\'"]/',    # Доступ к файловой системе
            r'subprocess\s*\.',       # Subprocess вызовы
            r'os\.system',            # OS системные вызовы
            r'<script',               # XSS атаки
            r'javascript:',           # JS инъекции
            r'data:text/html',        # HTML инъекции
        ]
        
        # Конфиденциальные данные
        self.sensitive_patterns = [
            r'password\s*=\s*[\'"][^\'"]+[\'"]',
            r'token\s*=\s*[\'"][^\'"]+[\'"]',
            r'secret\s*=\s*[\'"][^\'"]+[\'"]',
            r'api_key\s*=\s*[\'"][^\'"]+[\'"]',
            r'private_key\s*=\s*[\'"][^\'"]+[\'"]',
            r'ghp_[A-Za-z0-9]{36}',   # GitHub токены
        ]
    
    def load_security_config(self):
        """Загрузить конфигурацию безопасности"""
        if self.security_file.exists():
            with open(self.security_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "encryption_key": secrets.token_hex(32),
                "access_control": {
                    "allowed_users": ["developer"],
                    "restricted_files": [".env", "secrets.json", "keys/"],
                    "audit_enabled": True
                },
                "scan_results": {},
                "last_scan": None,
                "security_level": "high"
            }
            self.save_security_config()
    
    def save_security_config(self):
        """Сохранить конфигурацию безопасности"""
        with open(self.security_file, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def scan_file_security(self, file_path: Path) -> Dict[str, Any]:
        """Сканировать файл на уязвимости"""
        if not file_path.exists() or not file_path.is_file():
            return {"error": "File not found"}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            return {"error": "Cannot read file"}
        
        # Проверка опасных паттернов
        dangerous_found = []
        for pattern in self.dangerous_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                dangerous_found.append({
                    "pattern": pattern,
                    "matches": len(matches),
                    "severity": "high"
                })
        
        # Проверка конфиденциальных данных
        sensitive_found = []
        for pattern in self.sensitive_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                sensitive_found.append({
                    "pattern": pattern,
                    "matches": len(matches),
                    "severity": "critical"
                })
        
        # Проверка размера файла
        file_size = file_path.stat().st_size
        size_warning = file_size > 10 * 1024 * 1024  # 10MB
        
        # Проверка на подозрительные импорты
        suspicious_imports = re.findall(r'import\s+(?:subprocess|os|sys|socket|urllib|requests)', content, re.IGNORECASE)
        
        return {
            "file": str(file_path.relative_to(self.project_dir)),
            "size": file_size,
            "size_warning": size_warning,
            "dangerous_patterns": dangerous_found,
            "sensitive_data": sensitive_found,
            "suspicious_imports": suspicious_imports,
            "security_score": self.calculate_security_score(dangerous_found, sensitive_found, suspicious_imports),
            "scanned_at": datetime.now().isoformat()
        }
    
    def calculate_security_score(self, dangerous: List, sensitive: List, imports: List) -> int:
        """Рассчитать оценку безопасности (0-100)"""
        score = 100
        
        # Вычитаем за опасные паттерны
        for item in dangerous:
            score -= item["matches"] * 10
        
        # Вычитаем за конфиденциальные данные
        for item in sensitive:
            score -= item["matches"] * 20
        
        # Вычитаем за подозрительные импорты
        score -= len(imports) * 5
        
        return max(0, score)
    
    def scan_project_security(self) -> Dict[str, Any]:
        """Полное сканирование безопасности проекта"""
        print("Scanning project security...")
        
        # Файлы для сканирования
        scan_files = []
        for pattern in ["*.py", "*.js", "*.ts", "*.json", "*.env*", "*.md"]:
            scan_files.extend(self.project_dir.glob(pattern))
        
        # Исключаем системные папки
        scan_files = [f for f in scan_files if not any(skip in str(f) for skip in ["__pycache__", ".git", "node_modules"])]
        
        results = {}
        total_score = 0
        critical_issues = 0
        
        for file_path in scan_files:
            result = self.scan_file_security(file_path)
            if "error" not in result:
                results[str(file_path.relative_to(self.project_dir))] = result
                total_score += result["security_score"]
                
                # Считаем критические проблемы
                critical_issues += len(result["sensitive_data"])
        
        # Общая оценка
        avg_score = total_score // len(results) if results else 0
        
        scan_summary = {
            "scan_time": datetime.now().isoformat(),
            "files_scanned": len(results),
            "average_security_score": avg_score,
            "critical_issues": critical_issues,
            "total_dangerous_patterns": sum(len(r["dangerous_patterns"]) for r in results.values()),
            "total_sensitive_data": sum(len(r["sensitive_data"]) for r in results.values()),
            "security_level": self.get_security_level(avg_score),
            "files": results
        }
        
        # Сохраняем результаты
        self.config["scan_results"] = scan_summary
        self.config["last_scan"] = datetime.now().isoformat()
        self.save_security_config()
        
        return scan_summary
    
    def get_security_level(self, score: int) -> str:
        """Определить уровень безопасности"""
        if score >= 90:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 50:
            return "moderate"
        elif score >= 30:
            return "low"
        else:
            return "critical"
    
    def fix_security_issues(self, file_path: str) -> Dict[str, Any]:
        """Исправить проблемы безопасности в файле"""
        full_path = self.project_dir / file_path
        
        if not full_path.exists():
            return {"error": "File not found"}
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            return {"error": "Cannot read file"}
        
        original_content = content
        fixes_applied = []
        
        # Маскируем конфиденциальные данные
        for pattern in self.sensitive_patterns:
            content = re.sub(pattern, lambda m: f"{m.group().split('=')[0]}=***MASKED***", content, flags=re.IGNORECASE)
            if content != original_content:
                fixes_applied.append(f"Masked sensitive data: {pattern}")
        
        # Добавляем комментарии безопасности
        if "dangerous_patterns" in content:
            content = "# SECURITY WARNING: This file contains potentially dangerous patterns\n" + content
            fixes_applied.append("Added security warning")
        
        # Сохраняем исправленный файл
        if content != original_content:
            # Создаем бэкап
            backup_path = full_path.with_suffix(f"{full_path.suffix}.security_backup")
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "file": file_path,
                "fixes_applied": fixes_applied,
                "backup_created": str(backup_path),
                "security_improved": True
            }
        else:
            return {
                "file": file_path,
                "fixes_applied": [],
                "security_improved": False
            }
    
    def generate_security_report(self) -> str:
        """Сгенерировать отчет безопасности"""
        if not self.config["scan_results"]:
            return "No security scan results available"
        
        results = self.config["scan_results"]
        
        report = f"""
# 🔒 Security Report

**Scan Date:** {results['scan_time']}
**Files Scanned:** {results['files_scanned']}
**Average Security Score:** {results['average_security_score']}/100
**Security Level:** {results['security_level'].upper()}

## 📊 Summary
- **Critical Issues:** {results['critical_issues']}
- **Dangerous Patterns:** {results['total_dangerous_patterns']}
- **Sensitive Data Found:** {results['total_sensitive_data']}

## 🚨 Critical Files
"""
        
        # Добавляем файлы с низким рейтингом безопасности
        for file_path, file_result in results["files"].items():
            if file_result["security_score"] < 50:
                report += f"\n### {file_path}\n"
                report += f"- Security Score: {file_result['security_score']}/100\n"
                if file_result["sensitive_data"]:
                    report += f"- Sensitive Data: {len(file_result['sensitive_data'])} items\n"
                if file_result["dangerous_patterns"]:
                    report += f"- Dangerous Patterns: {len(file_result['dangerous_patterns'])} items\n"
        
        report += f"\n## 📋 Recommendations\n"
        
        if results['average_security_score'] < 70:
            report += "- Review and fix security issues in critical files\n"
            report += "- Remove or mask sensitive data\n"
            report += "- Add input validation\n"
        else:
            report += "- Security level is acceptable\n"
            report += "- Continue regular security scans\n"
        
        return report

# Использование
if __name__ == "__main__":
    enhancer = SecurityEnhancer()
    
    print("Security Enhancement System")
    print("=" * 50)
    
    # Сканируем безопасность
    results = enhancer.scan_project_security()
    
    print(f"\nSecurity Scan Results:")
    print(f"Files scanned: {results['files_scanned']}")
    print(f"Average score: {results['average_security_score']}/100")
    print(f"Security level: {results['security_level']}")
    print(f"Critical issues: {results['critical_issues']}")
    
    # Генерируем отчет
    report = enhancer.generate_security_report()
    
    # Сохраняем отчет
    report_file = Path("security_report.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nSecurity report saved: {report_file}")
    
    # Показываем критические файлы
    critical_files = [f for f, r in results['files'].items() if r['security_score'] < 50]
    if critical_files:
        print(f"\nWARNING Critical files ({len(critical_files)}):")
        for file_path in critical_files[:5]:  # Показываем первые 5
            print(f"  - {file_path}")
    else:
        print("\nOK No critical security issues found!")
