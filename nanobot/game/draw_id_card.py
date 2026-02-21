from io import BytesIO
import os
from PIL import Image, ImageDraw, ImageFont, ImageColor
from pathlib import Path
from tempfile import NamedTemporaryFile
from nanobot.game.assets import AssetManager
from nanobot.game.models import DigimonState

async def render_id_card(state: DigimonState) -> str | None:
    """
    Renders an ID card for the given Digimon and returns the path to the resulting image file.
    """
    sprite_path = await AssetManager.get_sprite_path(state.species)
    if not sprite_path or not os.path.exists(sprite_path):
        print(f"Sprite not found for {state.species}")
        return None

    # Constants
    CANVAS_WIDTH = 450
    CANVAS_HEIGHT = 280
    PADDING = 20
    
    # Colors
    BG_COLOR = (10, 15, 24)
    CYAN = (0, 243, 255)
    MAGENTA = (255, 0, 255)
    YELLOW = (255, 240, 0)
    DARK_CYAN = (0, 80, 90)
    TEXT_MAIN = (230, 240, 255)
    TEXT_DIM = (120, 140, 160)

    # Base Canvas
    img = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Draw Grid (Cyberpunk background)
    for x in range(0, CANVAS_WIDTH, 20):
        draw.line([(x, 0), (x, CANVAS_HEIGHT)], fill=(15, 25, 40), width=1)
    for y in range(0, CANVAS_HEIGHT, 20):
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(15, 25, 40), width=1)

    # Frame/Borders (Angled)
    draw.polygon([
        (5, 5), (CANVAS_WIDTH - 25, 5), (CANVAS_WIDTH - 5, 25), 
        (CANVAS_WIDTH - 5, CANVAS_HEIGHT - 5), (25, CANVAS_HEIGHT - 5), (5, CANVAS_HEIGHT - 25)
    ], outline=DARK_CYAN, width=2)
    
    # Corner Accents
    draw.line([(5, 5), (25, 5)], fill=CYAN, width=3)
    draw.line([(5, 5), (5, 25)], fill=CYAN, width=3)
    draw.line([(CANVAS_WIDTH-5, CANVAS_HEIGHT-5), (CANVAS_WIDTH-25, CANVAS_HEIGHT-5)], fill=MAGENTA, width=3)
    draw.line([(CANVAS_WIDTH-5, CANVAS_HEIGHT-5), (CANVAS_WIDTH-5, CANVAS_HEIGHT-25)], fill=MAGENTA, width=3)

    # Load fonts
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 22)
        font_med = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14)
        font_small = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 11)
        font_tiny = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 9)
    except IOError:
        font_large = font_med = font_small = font_tiny = ImageFont.load_default()

    # Header section
    draw.polygon([(10, 10), (CANVAS_WIDTH - 50, 10), (CANVAS_WIDTH - 30, 40), (10, 40)], fill=(12, 22, 35))
    draw.text((20, 15), f"ID:// {state.name.upper()}", fill=CYAN, font=font_large)
    
    # Stage & Level
    draw.text((CANVAS_WIDTH - 150, 18), f"LVL.{state.level:02d} [{state.stage.upper()}]", fill=YELLOW, font=font_med)

    # System Status text
    draw.text((10, 260), "SYS.ONLINE >> DDC.VER.3.0", fill=TEXT_DIM, font=font_tiny)
    draw.text((CANVAS_WIDTH - 130, 260), f"BOND // {state.bond}%", fill=MAGENTA, font=font_tiny)

    # Paste Sprite
    try:
        sprite = Image.open(sprite_path).convert("RGBA")
        sprite.thumbnail((140, 140))
        mask = sprite.split()[3]
        img.paste(sprite, (20, 70), mask)
    except Exception as e:
        print(f"Failed to paste sprite: {e}")
        
    # Stats Box
    stats_x = 180
    stats_y = 70
    
    # Function for cyberpunk segmented bars
    def draw_tech_bar(x, y, width, height, value, max_value, color):
        draw.rectangle([x, y, x + width, y + height], fill=(20, 30, 45), outline=(40, 55, 75))
        pct = max(0.0, min(1.0, value / max_value))
        if pct > 0:
            fill_width = int(width * pct)
            draw.rectangle([x, y, x + fill_width, y + height], fill=color)
            # Shine on top edge
            draw.line([(x, y), (x + fill_width, y)], fill=(255, 255, 255), width=1)
            # Add segments
            for bx in range(x + 10, x + width, 10):
                draw.line([(bx, y), (bx, y + height)], fill=(10, 15, 24), width=1)

    # HP
    draw.text((stats_x, stats_y), "HP_CORE", fill=TEXT_DIM, font=font_small)
    draw.text((stats_x + 140, stats_y), f"{state.current_hp}/{state.max_hp}", fill=TEXT_MAIN, font=font_small)
    draw_tech_bar(stats_x, stats_y + 15, 220, 12, state.current_hp, state.max_hp, (0, 255, 128))
    
    # Energy
    draw.text((stats_x, stats_y + 40), "NRG_CELL", fill=TEXT_DIM, font=font_small)
    draw.text((stats_x + 140, stats_y + 40), f"{state.energy}/100", fill=TEXT_MAIN, font=font_small)
    draw_tech_bar(stats_x, stats_y + 55, 220, 12, state.energy, 100, CYAN)
    
    # Hunger
    draw.text((stats_x, stats_y + 80), "BIO_FUEL", fill=TEXT_DIM, font=font_small)
    draw.text((stats_x + 140, stats_y + 80), f"{state.hunger}/100", fill=TEXT_MAIN, font=font_small)
    draw_tech_bar(stats_x, stats_y + 95, 220, 12, state.hunger, 100, YELLOW)

    # Attribute / Element Hexes (Techy looking data points)
    meta_y = 190
    draw.rectangle([stats_x, meta_y, stats_x + 100, meta_y + 25], outline=CYAN, fill=(10, 20, 30))
    # Add a little corner cut
    draw.polygon([(stats_x, meta_y), (stats_x+10, meta_y), (stats_x, meta_y+10)], fill=CYAN)
    draw.text((stats_x + 15, meta_y + 7), f"ATR:{state.attribute[:3].upper()}", fill=CYAN, font=font_small)

    draw.rectangle([stats_x + 110, meta_y, stats_x + 210, meta_y + 25], outline=MAGENTA, fill=(20, 10, 30))
    draw.polygon([(stats_x + 110, meta_y), (stats_x+120, meta_y), (stats_x + 110, meta_y+10)], fill=MAGENTA)
    draw.text((stats_x + 125, meta_y + 7), f"ELM:{state.element[:4].upper()}", fill=MAGENTA, font=font_small)

    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        img.save(tmp.name, format="PNG")
        return tmp.name
