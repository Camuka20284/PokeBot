import aiohttp
import base64
import json

class ReveAPI:
    def __init__(self, api_key: str, base_url: str = "https://api.reve.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
        version: str = "latest",
    ) -> bytes | None:
        """
        Prompt gönderir, başarılıysa ham PNG byte'larını döndürür.
        Discord'a discord.File(io.BytesIO(bytes), filename="pokemon.png") ile gönderebilirsin.
        """
        payload = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "version": version
        }
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(
                    f"{self.base_url}/image/create",
                    json=payload
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

            if result.get("content_violation"):
                print("Uyarı: İçerik politikası ihlali tespit edildi.")
                return None

            if result.get("image"):
                image_bytes = base64.b64decode(result["image"])
                print(f"Görsel oluşturuldu | Kredi: -{result.get('credits_used')} | Kalan: {result.get('credits_remaining')}")
                return image_bytes

            print("Görseli API yanıtında bulamadım:", json.dumps(result, indent=2))
            return None

        except aiohttp.ClientResponseError as e:
            print(f"API hatası {e.status}: {e.message}")
            return None
        except Exception as e:
            print(f"Beklenmeyen hata: {e}")
            return None


# Pokémon tipine göre prompt üretici
STYLE_PROMPTS = {
    "fire":     "fierce fire-type pokemon, surrounded by flames, anime style, dynamic action pose",
    "water":    "powerful water-type pokemon, ocean waves, anime style, cinematic lighting",
    "grass":    "nature grass-type pokemon, lush forest background, anime style, vibrant colors",
    "electric": "electric-type pokemon, lightning bolts, anime style, glowing yellow energy",
    "psychic":  "psychic-type pokemon, galaxy background, anime style, mystical aura",
    "ice":      "ice-type pokemon, frozen tundra, anime style, crystalline blue glow",
    "dragon":   "legendary dragon-type pokemon, mountain peak, anime style, epic scale",
    "ghost":    "ghost-type pokemon, dark misty graveyard, anime style, eerie purple glow",
    "fighting": "fighting-type pokemon, martial arts pose, anime style, intense energy",
    "normal":   "pokemon in an epic battle pose, anime style, dynamic lighting",
}

def build_prompt(pokemon_name: str, types: list[str], style: str = "anime") -> str:
    """
    Pokémon adı ve tiplerine göre Reve AI'ye gönderilecek prompt üretir.
    style: "anime" | "cyberpunk" | "watercolor" | "realistic"
    """
    style_map = {
        "anime":      "anime style, vibrant colors, dynamic pose",
        "cyberpunk":  "cyberpunk neon style, dark background, glowing effects",
        "watercolor": "soft watercolor painting style, pastel colors",
        "realistic":  "photorealistic, cinematic, dramatic lighting",
    }

    # Tipe göre ortam/atmosfer seç
    type_flavor = ""
    for t in types:
        if t in STYLE_PROMPTS:
            type_flavor = STYLE_PROMPTS[t]
            break
    if not type_flavor:
        type_flavor = STYLE_PROMPTS["normal"]

    style_desc = style_map.get(style, style_map["anime"])

    return f"{pokemon_name} pokemon, {type_flavor}, {style_desc}, high quality illustration"