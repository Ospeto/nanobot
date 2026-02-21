import asyncio
import os
from nanobot.game.database import SessionLocal
from nanobot.game import state, models, encyclopedia

async def main():
    db = SessionLocal()
    # 1. Reset state to Botamon level 1
    db.query(models.DigimonState).delete()
    db.commit()
    
    botamon = models.DigimonState(
        species="Botamon",
        name="Botamon",
        stage="Baby I",
        level=1,
        is_active=True,
        exp=0,
        bond=0
    )
    db.add(botamon)
    db.commit()
    
    # Check tree for Botamon (Should be False)
    from nanobot.game.evolution import verify_evolution_requirements
    
    info = await encyclopedia.Digipedia.get_digimon_info("Koromon")
    target_stage = info.get("levels", [])[0]
    
    res1 = await verify_evolution_requirements(db, botamon, "Koromon", target_stage)
    print("Test 1 (Botamon Lvl 1 -> Koromon):", res1)
    
    # Pump Level
    botamon.level = 4
    db.commit()
    res2 = await verify_evolution_requirements(db, botamon, "Koromon", target_stage)
    print("Test 2 (Botamon Lvl 4 -> Koromon):", res2)
    
    # Now simulate Koromon -> Agumon (Rookie)
    koromon = botamon
    koromon.species = "Koromon"
    koromon.name = "Koromon"
    koromon.stage = "Baby II"
    db.commit()
    
    info2 = await encyclopedia.Digipedia.get_digimon_info("Agumon")
    target_stage2 = info2.get("levels", [])[0]
    
    res3 = await verify_evolution_requirements(db, koromon, "Agumon", target_stage2)
    print("Test 3 (Koromon Lvl 4 -> Agumon):", res3)
    
    koromon.level = 11
    koromon.bond = 25
    db.commit()
    res4 = await verify_evolution_requirements(db, koromon, "Agumon", target_stage2)
    print("Test 4 (Koromon Lvl 11, Bond 25 -> Agumon):", res4)
    
    # Test hidden X-Antibody logic
    inv = state.get_or_create_inventory(db)
    inv.items = {"X-Antibody": 1} # Simulated drop
    db.commit()
    
    res5 = await verify_evolution_requirements(db, koromon, "Agumon X", "Rookie")
    print("Test 5 (Agumon X w/ Antibody):", res5)

if __name__ == "__main__":
    asyncio.run(main())
