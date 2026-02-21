import json
import os
import asyncio

class Digipedia:
    _db: dict = {}
    _by_name: dict = {}
    _by_id: dict = {}
    
    @classmethod
    def load_db(cls):
        if cls._db:
            return
            
        db_path = os.path.join(os.path.dirname(__file__), "data", "digimon.db.json")
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                cls._db = json.load(f)
                
            for d in cls._db.get("digimons", []):
                cls._by_name[d["name"].lower()] = d
                cls._by_id[str(d["id"])] = d
        except Exception as e:
            print(f"Failed to load local Digimon DB: {e}")
            cls._db = {}

    @classmethod
    async def get_digimon_info(cls, name_or_id: str):
        cls.load_db()
        name_or_id = str(name_or_id).lower()
        if name_or_id in cls._by_name:
            return cls._by_name[name_or_id]
        if name_or_id in cls._by_id:
            return cls._by_id[name_or_id]
        return None

    @classmethod
    async def get_evolution_conditions(cls, current_name: str, target_name: str):
        data = await cls.get_digimon_info(current_name)
        if not data:
            return None
            
        target_name_lower = target_name.lower()
        for evo in data.get("evolvesTo", []):
            if evo.get("name", "").lower() == target_name_lower:
                return "canon" if evo.get("canon") else ""
                
        return None

