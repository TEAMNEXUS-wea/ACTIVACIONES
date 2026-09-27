import requests
import json
import re
from bs4 import BeautifulSoup

def check_amazon_cookie(cookie_str):
    """
    Verifica las cookies de Amazon (at-main, ubid-main) y extrae información de la cuenta.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": cookie_str
    }
    
    try:
        # Intentar acceder a la página de configuración de Prime Video
        url = "https://www.primevideo.com/settings"
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=12)
        
        if response.status_code != 200 or "signin" in response.url.lower():
            # Intentar con amazon.com general si primevideo falla
            url_alt = "https://www.amazon.com/gp/flex/sign-out.html?path=%2Fgp%2Fyouraccount%2Fbin%2Fhome.html" # Alternativa para validar
            response = requests.get("https://www.amazon.com/gp/css/homepage.html", headers=headers, allow_redirects=True, timeout=12)
            if response.status_code != 200 or "signin" in response.url.lower():
                return {"ok": False, "error": "Invalid or expired cookies"}

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extraer nombre de usuario si es posible
        name = "Amazon User"
        nav_tool = soup.select_one("#nav-link-accountList-nav-line-1")
        if nav_tool:
            name = nav_tool.text.strip().replace("Hello, ", "").replace("Hola, ", "")
            
        # Determinar si es Prime
        prime_status = "Prime Member (Active)"
        prime_badge = soup.select_one(".nav-prime-duo") or soup.select_one("#prime-badge")
        if not prime_badge and "prime" not in response.text.lower():
            prime_status = "Standard / Free"

        return {
            "ok": True,
            "name": name if name else "Amazon User",
            "country": "US / Global",
            "plan": prime_status,
            "status": "ACTIVE"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def parse_amazon_file(file_path):
    """
    Parsea archivos de cookies (Netscape, JSON o texto plano con at-main).
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Si es formato JSON (Netscape o Selenium)
        if content.strip().startswith("["):
            try:
                data = json.loads(content)
                cookie_parts = []
                for item in data:
                    name = item.get("name")
                    value = item.get("value")
                    if name and value:
                        cookie_parts.append(f"{name}={value}")
                return "; ".join(cookie_parts)
            except:
                pass
                
        # Si es formato Netscape estándar (tabulaciones)
        lines = content.splitlines()
        cookie_parts = []
        for line in lines:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6]
                cookie_parts.append(f"{name}={value}")
                
        if cookie_parts:
            return "; ".join(cookie_parts)
            
        # Si es texto plano con at-main o formato clave=valor
        if "at-main" in content or "ubid-main" in content:
            return content.strip()
            
        return content.strip()
    except:
        return None
