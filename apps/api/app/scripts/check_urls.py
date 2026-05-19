"""One-shot URL verification script for all unchecked opportunities."""
import asyncio
from app.services.url_checker import verify_all_urls


async def main() -> None:
    print("Checking all source URLs...")
    results = await verify_all_urls()
    for slug, ok in results.items():
        status = "OK     " if ok else "BROKEN " if ok is not None else "TIMEOUT"
        print(f"  {status} {slug}")
    ok_count = sum(1 for v in results.values() if v)
    broken_count = sum(1 for v in results.values() if v is False)
    print(f"\nTotal: {len(results)} | OK: {ok_count} | Broken: {broken_count}")


if __name__ == "__main__":
    asyncio.run(main())
