import hashlib
import hmac
from urllib.parse import parse_qsl

def validate_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """
    Validates the data received from Telegram Web App (TWA) Mini App.
    """
    if not init_data or not bot_token:
        return False
        
    try:
        parsed_data = dict(parse_qsl(init_data))
    except Exception:
        return False
        
    if "hash" not in parsed_data:
        return False
        
    hash_value = parsed_data.pop("hash")
    
    # Sort keys algorithm required by Telegram
    sorted_keys = sorted(parsed_data.keys())
    data_check_string = "\n".join(f"{k}={parsed_data[k]}" for k in sorted_keys)
    
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return calculated_hash == hash_value
