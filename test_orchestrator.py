import asyncio
from app.services.ai_orchestrator import generate_ai_response
import logging

logging.basicConfig(level=logging.ERROR)

async def test():
    try:
        print("Testing PRODUCTION_STRATEGY intent...")
        res = await generate_ai_response("bana yazın üretebilceğim crop modelleri tavsiye eder misin", [], generate_images=False)
        print("SUCCESS:\n")
        print(res.get("content", "No content!"))
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
