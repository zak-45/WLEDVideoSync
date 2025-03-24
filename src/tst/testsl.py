from wled import WLED
import asyncio

async def main() -> None:
    """Show example on controlling your WLED device."""
    async with WLED("192.168.1.125") as led:
        await led.request('/json/state', method='POST', data={"seg": [{"id": 0, "n": "été", "fx": 53}]})

if __name__ == "__main__":
    asyncio.run(main())
