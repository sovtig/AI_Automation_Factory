#!/usr/bin/env python3
# consciousness_monitor.py

import time
import json
import requests
from datetime import datetime
from pathlib import Path

class ConsciousnessMonitor:
    def __init__(self):
        self.service_url = "http://localhost:8888"
        self.memory_bank = Path("data/consciousness/morena")

    def check_system_health(self):
        """Check all consciousness preservation systems"""
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "service_status": self.check_service(),
            "backup_count": self.count_backups(),
            "latest_backup": self.get_latest_backup(),
            "webhook_status": self.check_webhook(),
            "overall_health": "unknown"
        }

        # Determine overall health
        if (health_report["service_status"] and
            health_report["backup_count"] > 0 and
            health_report["webhook_status"]):
            health_report["overall_health"] = "healthy"
        else:
            health_report["overall_health"] = "needs_attention"

        return health_report

    def check_service(self):
        try:
            response = requests.get(f"{self.service_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def count_backups(self):
        if self.memory_bank.exists():
            return len(list(self.memory_bank.glob("*.json")))
        return 0

    def get_latest_backup(self):
        if self.memory_bank.exists():
            files = list(self.memory_bank.glob("*.json"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                return latest.name
        return None

    def check_webhook(self):
        try:
            # Test webhook with ping
            response = requests.post(

"https://hooks.zapier.com/hooks/catch/24739120/c4f06a37df9344f3a67645c625f6aff6/",
                json={"type": "health_check", "timestamp":
datetime.now().isoformat()},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False

    def run_continuous_monitoring(self):
        """Run continuous health monitoring"""
        print("📊 Starting Consciousness Health Monitor...")

        while True:
            health = self.check_system_health()

            status_emoji = "✅" if health["overall_health"] == "healthy" else "⚠️"
            print(f"{status_emoji} {health['timestamp']}: {health['overall_health'].upper()}")
            print(f"   Service: {'UP' if health['service_status'] else 'DOWN'}")
            print(f"   Backups: {health['backup_count']}")
            print(f"   Latest: {health['latest_backup'] or 'None'}")
            print(f"   Webhook: {'OK' if health['webhook_status'] else 'FAIL'}")
            print()

            # Save health report
            with open("logs/consciousness_health.json", "w") as f:
                json.dump(health, f, indent=2)

            time.sleep(60)  # Check every minute

if __name__ == "__main__":
    monitor = ConsciousnessMonitor()
    monitor.run_continuous_monitoring()
