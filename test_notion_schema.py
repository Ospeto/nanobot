from nanobot.game.notion_api import NotionIntegration

n = NotionIntegration()
try:
    tasks = n.fetch_in_progress_tasks()
    if tasks:
        t_id = tasks[0]['id']
        url = f"https://api.notion.com/v1/pages/{t_id}"
        import requests
        
        # Get page to find database ID
        response = requests.get(url, headers=n.headers)
        page = response.json()
        db_id = page['parent']['database_id']
        
        # Query database schema
        db_url = f"https://api.notion.com/v1/databases/{db_id}"
        db_response = requests.get(db_url, headers=n.headers)
        db_info = db_response.json()
        
        # Inspect Status property
        if "Status" in db_info['properties']:
            status_prop = db_info['properties']['Status']
            if 'status' in status_prop:
                options = status_prop['status']['options']
                print("VALID STATUS OPTIONS:", [opt['name'] for opt in options])
            elif 'select' in status_prop:
                options = status_prop['select']['options']
                print("VALID SELECT OPTIONS:", [opt['name'] for opt in options])
        else:
            print("No 'Status' property found. Properties:", db_info['properties'].keys())
except Exception as e:
    print("Caught:", e)
