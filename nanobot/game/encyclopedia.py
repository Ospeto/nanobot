import httpx

class Digipedia:
    BASE_URL = "https://digi-api.com/api/v1/digimon"
    
    @classmethod
    async def get_digimon_info(cls, name_or_id: str):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{cls.BASE_URL}/{name_or_id.lower()}")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            print(f"Digipedia Error: {e}")
            return None
            
    @classmethod
    async def get_evolution_conditions(cls, current_name: str, target_name: str):
        data = await cls.get_digimon_info(current_name)
        if not data:
            return None
            
        next_evos = data.get("nextEvolutions", [])
        for evo in next_evos:
            if evo.get("digimon", "").lower() == target_name.lower():
                return evo.get("condition")
                
        return None
