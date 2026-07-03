"""Standalone test of do_crawl — writes output to a temp file."""
import asyncio, sys, json
sys.path.insert(0, r"D:\trae\projects\answerresume\job_seeker")
from crawler_server import do_crawl

async def main():
    with open(r"D:\trae\projects\answerresume\job_seeker\crawl_debug.log", "w", encoding="utf-8") as f:
        f.write("Starting do_crawl...\n")
        try:
            result = await do_crawl("产品经理", "杭州", "time", 3)
            f.write(f"Result: {json.dumps(result, ensure_ascii=False)}\n")
        except Exception as e:
            f.write(f"ERROR: {e}\n")
            import traceback
            traceback.print_exc(file=f)

if __name__ == "__main__":
    asyncio.run(main())
