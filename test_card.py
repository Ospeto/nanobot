import asyncio
from nanobot.game.draw_id_card import render_id_card
from nanobot.game.database import SessionLocal
from nanobot.game.models import DigimonState

async def _verify():
    db = SessionLocal()
    try:
        # Create a mock digimon temporarily without committing
        digi = DigimonState(name="Agumon", species="Agumon", stage="Rookie", bond=100, current_hp=100, max_hp=100, energy=80, hunger=70, attribute="Vaccine", element="Fire", min_weight=15, level=1)
        path = await render_id_card(digi)
        print(f"Generated image at: {path}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(_verify())
