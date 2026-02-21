import os
import httpx
from pathlib import Path
from nanobot.game.encyclopedia import Digipedia

class AssetManager:
    BASE_RAW_URL = "https://raw.githubusercontent.com/furudbat/digimon-partner-kit/main/public"
    
    @classmethod
    def get_cache_dir(cls) -> Path:
        cache_dir = Path.home() / ".nanobot" / "cache" / "sprites"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir
        
    @classmethod
    async def get_sprite_path(cls, digimon_name: str) -> str | None:
        """
        Returns the local absolute path to the Digimon's 2D sprite.
        If it does not exist locally, it downloads it on the fly.
        """
        info = await Digipedia.get_digimon_info(digimon_name)
        if not info or not info.get("img"):
            return None
            
        img_rel_path = info["img"] # e.g. "img/Agumon.png"
        file_name = os.path.basename(img_rel_path)
        
        cache_dir = cls.get_cache_dir()
        local_path = cache_dir / file_name
        
        if local_path.exists():
            return str(local_path)
            
        # Download on demand
        target_url = f"{cls.BASE_RAW_URL}/{img_rel_path}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(target_url)
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)
            return str(local_path)
        except Exception as e:
            print(f"AssetManager: Failed to fetch sprite {target_url}: {e}")
            return None
