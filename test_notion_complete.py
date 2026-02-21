import os
from nanobot.game.notion_api import NotionIntegration

def test_notion():
    notion = NotionIntegration()
    result = notion.complete_task("2f50cc17-6cb9-806e-812e-f1c0db8e0682")
    print(f"Result: {result}")

if __name__ == "__main__":
    test_notion()
