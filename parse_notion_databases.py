from nanobot.game.notion_api import NotionIntegration
import requests

n = NotionIntegration()
if not n.is_authenticated():
    print("Not authenticated!")
    exit(1)

url = "https://api.notion.com/v1/search"
payload = {"filter": {"value": "database", "property": "object"}}
try:
    response = requests.post(url, json=payload, headers=n.headers)
    response.raise_for_status()
    results = response.json().get("results", [])
    
    print(f"Found {len(results)} databases.")
    for db in results:
        title = db.get("title", [])
        if title:
            name = title[0].get("plain_text", "Untitled")
            print(f"DB Name: {name} | ID: {db['id']}")
            # print schema keys
            props = list(db.get("properties", {}).keys())
            print(f"   -> Columns: {props}")
except Exception as e:
    print(f"Error: {e}")
