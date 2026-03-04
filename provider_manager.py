# provider_manager.py
import logging

class ProviderManager:
    def __init__(self, providers: list):
        self.providers = providers
        self.current_index = 0

    async def call(self, method: str, params: dict):
        """Tries providers until one succeeds."""
        for _ in range(len(self.providers)):
            provider = self.providers[self.current_index]
            try:
                return await provider.request(method, params)
            except Exception as e:
                logging.error(f"Provider {provider.__class__.__name__} failed: {e}")
                # Switch to next
                self.current_index = (self.current_index + 1) % len(self.providers)
        
        raise Exception("All providers failed")
