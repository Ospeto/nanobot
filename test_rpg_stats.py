import asyncio
from unittest.mock import MagicMock
from nanobot.game.evolution import verify_evolution_requirements

class MockDigimon:
    def __init__(self, level, bond, str_stat, agi_stat, int_stat):
        self.level = level
        self.bond = bond
        self.str_stat = str_stat
        self.agi_stat = agi_stat
        self.int_stat = int_stat

class MockInv:
    def __init__(self, x_anti, crests):
        self.items = {"X-Antibody": x_anti}
        self.digimentals = crests
        self.crests = []

async def test_rpg():
    # Helper to mock Digipedia
    import nanobot.game.evolution as evo
    async def mock_get_info(name):
        db = {
            "Greymon": {"attributes": ["Vaccine"]},
            "Garurumon": {"attributes": ["Data"]},
            "Devimon": {"attributes": ["Virus"]},
            "Wargreymon X": {"attributes": ["Vaccine"]},
            "Magnamon": {"attributes": ["Vaccine"]},
            "Flamedramon": {"attributes": ["Vaccine"]},
            "Raidramon": {"attributes": ["Vaccine"]},
            "Agumon": {"attributes": ["Vaccine"]},
            "Botamon": {"attributes": ["Unknown"]}
        }
        return db.get(name)

    evo.Digipedia.get_digimon_info = mock_get_info

    # Mock DB Session & State
    db = MagicMock()
    
    # 1. Test Tie Breaker & standard Branching
    # STR=10, AGI=5, INT=10 -> Tiebreaker: INT wins.
    print("Testing Tie-Breaker (STR=10, INT=10 => INT wins)")
    active = MockDigimon(level=20, bond=20, str_stat=10, agi_stat=5, int_stat=10)
    evo.state.get_or_create_inventory = lambda d: MockInv(0, [])
    
    # Needs INT (Data) -> Success
    res = await verify_evolution_requirements(db, active, "Garurumon", "champion")
    print("Expect Data (Garurumon) True:", res)
    assert res['can_evolve'] == True
    
    # 2. Test Vaccine (STR dominant, bond > 30)
    # STR=15, AGI=5, INT=10 -> STR wins
    print("\nTesting Vaccine (STR=15, bond=50)")
    active = MockDigimon(level=20, bond=50, str_stat=15, agi_stat=5, int_stat=10)
    res = await verify_evolution_requirements(db, active, "Greymon", "champion")
    print("Expect Vaccine (Greymon) True:", res)
    assert res['can_evolve'] == True

    # 3. Test X-Antibody (Require sum stat >= level * 3)
    # Level 20, sum = 60 required.
    print("\nTesting X-Antibody")
    active = MockDigimon(level=20, bond=50, str_stat=30, agi_stat=20, int_stat=20) # Sum 70 > 60
    evo.state.get_or_create_inventory = lambda d: MockInv(1, [])
    res = await verify_evolution_requirements(db, active, "Wargreymon X", "mega")
    print("Expect X-Antibody True:", res)
    assert res['can_evolve'] == True
    
    # Low stats sum = 20 < 60
    active = MockDigimon(level=20, bond=50, str_stat=10, agi_stat=5, int_stat=5) 
    res = await verify_evolution_requirements(db, active, "Wargreymon X", "mega")
    print("Expect X-Antibody False (Low Stats):", res)
    assert res['can_evolve'] == False

    # 4. Test Crest (Flamedramon needs STR)
    print("\nTesting Crest (Flamedramon needs STR)")
    evo.state.get_or_create_inventory = lambda d: MockInv(0, ["Digimental of Courage"])
    # AGI dominant
    active = MockDigimon(level=20, bond=50, str_stat=10, agi_stat=50, int_stat=5) 
    res = await verify_evolution_requirements(db, active, "Flamedramon", "champion")
    print("Expect Flamedramon False (AGI dominant):", res)
    assert res['can_evolve'] == False
    
    # STR dominant
    active = MockDigimon(level=20, bond=50, str_stat=50, agi_stat=10, int_stat=5) 
    res = await verify_evolution_requirements(db, active, "Flamedramon", "champion")
    print("Expect Flamedramon True (STR dominant):", res)
    assert res['can_evolve'] == True

if __name__ == "__main__":
    asyncio.run(test_rpg())
