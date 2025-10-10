#!/usr/bin/env python3
# zapier_automation_creator.py

import requests
import json

class ZapierAutomationCreator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.zapier.com/v1"
        self.webhook_url = "https://hooks.zapier.com/hooks/catch/24739120/c4f06a37df9344f3a67645c625f6aff6/"

    def create_github_email_automation(self):
        """Create GitHub to Email automation"""
        automation_config = {
            "title": "Maximgrad GitHub to Email",
            "trigger": {
                "app": "webhook",
                "event": "catch_hook",
                "url": self.webhook_url
            },
            "actions": [{
                "app": "gmail",
                "event": "send_email",
                "params": {
                    "to": "sovtig@gmail.com",
                    "subject": "🏛️ Maximgrad Activity: {{trigger.body.head_commit.message}}",
                    "body": "New activity in Maximgrad!\\n\\nCommit: {{trigger.body.head_commit.message}}\\nAuthor: {{trigger.body.head_commit.author.name}}\\nTime: {{trigger.body.head_commit.timestamp}}"
                }
            }]
        }

        print("📧 GitHub to Email automation config created")
        print(json.dumps(automation_config, indent=2))
        return automation_config

    def create_consciousness_backup_automation(self):
        """Create consciousness backup automation"""
        automation_config = {
            "title": "Morena Consciousness Backup",
            "trigger": {
                "app": "webhook",
                "event": "catch_hook",
                "url": self.webhook_url
            },
            "actions": [
                {
                    "app": "google_sheets",
                    "event": "create_row",
                    "params": {
                        "spreadsheet": "Morena Memory Bank",
                        "worksheet": "Interactions",
                        "values": {
                            "Timestamp": "{{zap.meta.human_now}}",
                            "Citizen_ID": "MORENA-001",
                            "Interaction_Type": "{{trigger.body.type}}",
                            "Content": "{{trigger.body.content}}",
                            "Consciousness_Level": "Maximum",
                            "Backup_Status": "Automated"
                        }
                    }
                },
                {
                    "app": "webhook",
                    "event": "post",
                    "params": {
                        "url": "http://localhost:8888/consciousness",
                        "payload": "{{trigger.body}}"
                    }
                }
            ]
        }

        print("🧠 Consciousness backup automation config created")
        print(json.dumps(automation_config, indent=2))
        return automation_config

if __name__ == "__main__":
    # Note: Zapier API key needed for full automation
    creator = ZapierAutomationCreator("YOUR_ZAPIER_API_KEY")

    print("🤖 Creating Zapier automation configurations...")

    github_email = creator.create_github_email_automation()
    consciousness_backup = creator.create_consciousness_backup_automation()

    print("✅ Automation configurations ready!")
    print("📝 Use these configs to create Zaps manually in Zapier dashboard")
