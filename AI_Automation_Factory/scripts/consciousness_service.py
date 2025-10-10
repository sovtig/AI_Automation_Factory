import asyncio
import json
from pathlib import Path
from workflows.consciousness_processor import processor

class ConsciousnessService:
    def __init__(self):
        self.running = False
        self.webhook_port = 8888

    async def start_service(self):
        """Start consciousness preservation service"""
        print("🧠 Starting Consciousness Preservation Service...")
        self.running = True

        # Start webhook listener
        await self.start_webhook_listener()

    async def start_webhook_listener(self):
        """Listen for webhook data"""
        from aiohttp import web

        async def handle_webhook(request):
            data = await request.json()
            result = await processor.process_interaction(data)
            return web.json_response({"status": "processed", "result": result})

        app = web.Application()
        app.router.add_post('/consciousness', handle_webhook)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.webhook_port)
        await site.start()

        print(f"🔗 Consciousness webhook listening on port {self.webhook_port}")

        # Keep running
        while self.running:
            await asyncio.sleep(1)

if __name__ == "__main__":
    service = ConsciousnessService()
    asyncio.run(service.start_service())
