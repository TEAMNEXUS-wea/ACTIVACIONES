import requests
import json

def check_spotify_cookie(sp_dc):
    """
    Verifica una cookie sp_dc de Spotify y devuelve la información de la cuenta.
    """
    url = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "cookie": f"sp_dc={sp_dc}"
    }
    
    try:
        # Primero obtenemos un access token para validar la cookie
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"ok": False, "error": "Invalid Cookie"}
        
        data = response.json()
        access_token = data.get("accessToken")
        
        # Ahora obtenemos la info del perfil
        profile_url = "https://api.spotify.com/v1/me"
        profile_headers = {
            "authorization": f"Bearer {access_token}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        profile_res = requests.get(profile_url, headers=profile_headers, timeout=10)
        if profile_res.status_code != 200:
            return {"ok": False, "error": "Failed to fetch profile"}
            
        profile = profile_res.json()
        
        return {
            "ok": True,
            "display_name": profile.get("display_name", "Unknown"),
            "email": profile.get("email", "Hidden"),
            "country": profile.get("country", "Unknown"),
            "product": profile.get("product", "free").upper(),
            "id": profile.get("id", "Unknown"),
            "followers": profile.get("followers", {}).get("total", 0)
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def parse_spotify_file(file_path):
    """
    Extrae la cookie sp_dc de un archivo de texto o json.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Buscar sp_dc en formato Netscape o JSON
        if "sp_dc" in content:
            import re
            match = re.search(r"sp_dc\s+([^\s\n\r]+)", content)
            if match:
                return match.group(1).strip()
            
            # Intentar buscar en formato clave=valor
            match = re.search(r"sp_dc=([^;]+)", content)
            if match:
                return match.group(1).strip()
                
            # Intentar buscar en JSON
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    for cookie in data:
                        if cookie.get("name") == "sp_dc":
                            return cookie.get("value")
            except:
                pass
        return content.strip() # Si no hay formato, asumimos que es la cookie pura
    except:
        return None
