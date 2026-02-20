from nanobot.agent.tools.base import Tool
from nanobot.game.database import SessionLocal
from nanobot.game import state, schemas
from datetime import datetime, timedelta

class InitDigimonTool(Tool):
    @property
    def name(self) -> str:
        return "init_digimon"

    @property
    def description(self) -> str:
        return "Initializes a new Digimon partner for the user. Call this when the user says 'digimon init' or asks for their first Digimon."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def execute(self, **kwargs) -> str:
        db = SessionLocal()
        try:
            active = state.get_active_digimon(db)
            if active:
                return f"You already have an active Digimon partner named {active.name} ({active.species})!"
                
            # Initialize as a Digitama
            # Egg will be ready to hatch in exactly 5 minutes
            hatch_time = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            
            egg = schemas.DigimonCreate(
                name="Digitama",
                species="Digitama",
                stage="Digitama",
                attribute="Unknown",
                element="Unknown"
            )
            
            new_digi = state.add_digimon(db, egg)
            new_digi.hatch_time = hatch_time
            new_digi.level = 0
            new_digi.exp = 0
            
            # Give initial items
            inv = state.get_or_create_inventory(db)
            if "Meat" not in inv.items:
                inv.items["Meat"] = 5
            
            db.commit()
            
            return f"A Digitama has successfully dropped into your Digivice! It will hatch in 5 minutes. Tell the user to wait for it."
        finally:
            db.close()
