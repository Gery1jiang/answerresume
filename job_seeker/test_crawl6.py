"""Test do_crawl directly with logging."""
import asyncio, sys, json
sys.path.insert(0, r"D:\trae\projects\answerresume\job_seeker")
from crawler_server import do_crawl

async def main():
    with open(r"D:\trae\projects\answerresume\job_seeker\crawl_debug6.log", "w", encoding="utf-8") as f:
        f.write("Starting do_crawl...\n")
        try:
            result = await do_crawl("产品经理", "杭州", "time", 3)
            f.write(f"Count: {len(result)}\n")
            for j in result:
                f.write(f"  Title: {j.get('title')}\n")
                f.write(f"  Company: {j.get('company')}\n")
                f.write(f"  URL: {j.get('jd_url')}\n")
                f.write(f"  JD len: {len(j.get('jd_text',''))}\n")
                f.write("---\n")
        except Exception as e:
            f.write(f"ERROR: {e}\n")
            import traceback
            traceback.print_exc(file=f)

if __name__ == "__main__":
    asyncio.run(main())
