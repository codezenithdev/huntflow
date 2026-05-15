"""HuntFlow main entry point for running the complete system."""
import asyncio
from scheduler.scheduler import start_scheduler


async def main():
    """Start HuntFlow scheduler and crews."""
    print("Starting HuntFlow...")
    start_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
