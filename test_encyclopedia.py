import pytest
import asyncio
from nanobot.game.encyclopedia import Digipedia
from nanobot.game.evolution import check_evolution_ready
from nanobot.game.database import SessionLocal
from nanobot.game.models import DigimonState

async def _verify():
    # 1. Simple lookup
    agumon = await Digipedia.get_digimon_info("Agumon")
    assert agumon, "FAIL: Could not find Agumon"
    print(f"SUCCESS: Found {agumon['name']}")
        
    # 2. Check Evolutions
    evos = agumon.get("evolvesTo", [])
    print(f"Agumon has {len(evos)} evolvesTo entries.")
    canon_count = sum(1 for e in evos if e.get("canon"))
    print(f"Of those, {canon_count} are canon.")

    # 3. Test check_evolution_ready
    db = SessionLocal()
    try:
        # Create a mock digimon
        digi = DigimonState(name="Agumon", species="Agumon", stage="Rookie", bond=100)
        db.add(digi)
        db.commit()
        db.refresh(digi)
        
        # We need it active
        digi.is_active = True
        db.commit()

        res = await check_evolution_ready(db)
        print("Evolutions for Agumon (filtered):", res)

        db.delete(digi)
        db.commit()
    finally:
        db.close()

def test_verification():
    asyncio.run(_verify())

