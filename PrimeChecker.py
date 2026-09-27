import requests
import re
import json
import uuid
import cloudscraper

# Headers estandarizados del script PrimeCookie.py
REQUEST_HEADERS = {
    "Host": "www.primevideo.com",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "identity",
}

def check_prime_cookie_advanced(cookie_str):
    """
    Versión avanzada del checker de Prime Video basada en PrimeCookie.py
    """
    scraper = cloudscraper.create_scraper()
    
    # Limpiar cookie string
    cookie_str = cookie_str.strip()
    
    headers = dict(REQUEST_HEADERS)
    headers["Cookie"] = cookie_str
    
    try:
        # Paso 1: Storefront (Verificación de Redirección)
        storefront_url = "https://www.primevideo.com/region/eu/storefront"
        resp = scraper.get(storefront_url, headers=headers, allow_redirects=True, timeout=15)
        
        if resp.status_code != 200 or "signin" in resp.url.lower() or "ap/signin" in resp.url.lower():
            return {"ok": False, "error": "DEAD: Redirected to Login"}
            
        # Paso 2: Configuración (Verificación de Identidad)
        config_url = "https://atv-ps.primevideo.com/acm/GetConfiguration/WebClient?deviceTypeID=AOAGZA014O5RE&deviceID=Web"
        config_headers = dict(headers)
        config_headers["Host"] = "atv-ps.primevideo.com"
        config_headers["Accept"] = "application/json, text/plain, */*"
        
        config_resp = scraper.get(config_url, headers=config_headers, timeout=15)
        
        if config_resp.status_code == 200:
            try:
                data = config_resp.json()
                customer_id = data.get("customerID")
                territory = data.get("recordTerritory")
                
                if customer_id and territory:
                    # Si tiene estos campos, la sesión es 100% válida
                    return {
                        "ok": True,
                        "name": f"User_{customer_id[:6]}",
                        "country": territory,
                        "plan": "Prime Active (Verified)",
                        "status": "LIVE"
                    }
            except:
                pass
        
        # Paso 3: Fallback (Búsqueda de marcas de vida en el HTML)
        html = resp.text.lower()
        if "nav-item-signout" in html or "sign out" in html or "cerrar sesión" in html:
            return {
                "ok": True,
                "name": "Amazon User",
                "country": "Unknown",
                "plan": "Active Session",
                "status": "LIVE"
            }
            
        return {"ok": False, "error": "DEAD: Session Inactive"}

    except Exception as e:
        return {"ok": False, "error": str(e)}

def parse_amazon_file(file_path):
    """
    Parsea archivos de cookies (Netscape, JSON o texto plano).
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        if content.strip().startswith("["):
            try:
                data = json.loads(content)
                return "; ".join([f"{c['name']}={c['value']}" for c in data if 'name' in c and 'value' in c])
            except: pass
                
        lines = content.splitlines()
        cookie_parts = []
        for line in lines:
            if line.startswith("#") or not line.strip(): continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookie_parts.append(f"{parts[5]}={parts[6]}")
        
        if cookie_parts: return "; ".join(cookie_parts)
        
        # Fallback: Texto plano, pero quitando posibles comentarios/sellos inyectados
        final_lines = []
        for line in lines:
            if line.startswith("#") or not line.strip(): continue
            final_lines.append(line.strip())
        return "; ".join(final_lines)
    except:
        return None
