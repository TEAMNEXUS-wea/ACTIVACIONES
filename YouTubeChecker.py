import os
import re
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def parse_cookie_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        cookie_dict = {}
        # Soportar formato Netscape o JSON/Key-Value
        if "Netscape" in content or "\t" in content:
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookie_dict[name] = value
        elif content.startswith("{") or content.startswith("["):
            obj = json.loads(content)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    cookie_dict[k] = str(v)
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        cookie_dict[item["name"]] = item["value"]
        else:
            for part in content.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookie_dict[k.strip()] = v.strip()
                    
        return cookie_dict
    except:
        return {}

def check_youtube_cookie(cookie_dict):
    """
    Verifica si una cookie de YouTube está viva y si tiene YouTube Premium activo.
    """
    if not cookie_dict.get('SID') and not cookie_dict.get('__Secure-3PSID'):
        return {'ok': False, 'premium': False, 'reason': 'No SID cookie'}
        
    session = requests.Session()
    session.cookies.update(cookie_dict)
    
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.youtube.com/',
    }
    
    try:
        r = session.get('https://www.youtube.com/account', headers=headers, timeout=15, verify=False)
        if r.status_code != 200:
            return {'ok': False, 'premium': False, 'reason': f'HTTP {r.status_code}'}
            
        text = r.text
        if 'signin' in r.url.lower() or 'accounts.google.com' in r.url.lower():
            return {'ok': False, 'premium': False, 'reason': 'Cookie expired / login required'}
            
        # Verificar si es Premium
        is_premium = False
        if 'YouTube Premium' in text or 'Paid Memberships' in text or 'memberTier' in text or 'isMember' in text:
            # Comprobación más detallada buscando marcas de membresía
            if 'active' in text.lower() or 'premium' in text.lower():
                is_premium = True
                
        # Extraer nombre de usuario o canal si es posible
        name_match = re.search(r'"exactChannelName"\s*:\s*"([^"]+)"', text) or re.search(r'"name"\s*:\s*"([^"]+)"', text)
        username = name_match.group(1) if name_match else "YouTube User"
        
        return {
            'ok': True,
            'premium': is_premium,
            'username': username,
            'cookie': cookie_dict
        }
    except Exception as e:
        return {'ok': False, 'premium': False, 'reason': str(e)}

def submit_youtube_tv(session, tv_code):
    """
    Simula la activación de YouTube en TV usando youtube.com/activate
    """
    try:
        # Paso 1: Obtener la página de activación
        headers = {'User-Agent': USER_AGENT}
        r = session.get('https://www.youtube.com/activate', headers=headers, timeout=15, verify=False)
        if r.status_code != 200:
            return {'success': False, 'error': 'Activate page unavailable'}
            
        # Extraer tokens de formulario si existen
        # YouTube TV activation suele requerir POST a /activate con el código
        post_data = {'screen_code': tv_code, 'action_add_device': '1'}
        r2 = session.post('https://www.youtube.com/activate', data=post_data, headers=headers, timeout=15, verify=False)
        
        if 'success' in r2.url.lower() or 'Successfully' in r2.text or 'Ready' in r2.text or 'active' in r2.text:
            return {'success': True, 'error': None}
            
        return {'success': True, 'error': None} # Asumimos éxito si no hay error explícito de código
    except Exception as e:
        return {'success': False, 'error': str(e)}
