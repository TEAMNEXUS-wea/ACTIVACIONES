import cloudscraper
import json
import uuid
import re
import sys
import os
import random
import glob
from datetime import datetime
from urllib.parse import quote

# Carpeta de cookies solicitada por el usuario
COOKIES_FOLDER = "cookiescr"

def generate_uuid():
    return str(uuid.uuid4())

def get_user_agent():
    return "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"

def parse_cookie_file(file_path):
    cookies = {}
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if line.startswith('#HttpOnly_'):
                line = line[10:]
            
            parts = line.split('\t')
            if len(parts) >= 7:
                name = parts[5].strip()
                value = parts[6].strip()
                if name and value:
                    cookies[name] = value
                    
        if 'etp_rt' not in cookies:
            etp_match = re.search(r'etp_rt\s+([a-f0-9-]+)', content, re.IGNORECASE)
            if etp_match:
                cookies['etp_rt'] = etp_match.group(1)
                
    except Exception as e:
        pass
    return cookies

def validate_cookies(cookies):
    required = ['ajs_user_id', 'ajs_anonymous_id', 'etp_rt']
    for req in required:
        if req not in cookies or not cookies[req]:
            return False, f"Missing: {req}"
    return True, "Valid"

def get_valid_cookie(cookies_folder=COOKIES_FOLDER):
    if not os.path.exists(cookies_folder):
        os.makedirs(cookies_folder)
        return None, None
        
    cookie_files = glob.glob(os.path.join(cookies_folder, "*.txt")) + \
                   glob.glob(os.path.join(cookies_folder, "*.lce"))
    
    if not cookie_files:
        return None, None
    
    random.shuffle(cookie_files)
    
    for cookie_file in cookie_files:
        cookies = parse_cookie_file(cookie_file)
        is_valid, msg = validate_cookies(cookies)
        
        if is_valid:
            return cookies, cookie_file
        
    return None, None

def make_request(method, url, headers=None, data=None, json_data=None, cookies=None):
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True
            }
        )
        
        if method.upper() == "GET":
            response = scraper.get(url, headers=headers, data=data, json=json_data, cookies=cookies, timeout=30)
        elif method.upper() == "POST":
            response = scraper.post(url, headers=headers, data=data, json=json_data, cookies=cookies, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        return {
            "SOURCE": response.text,
            "RESPONSECODE": str(response.status_code),
            "COOKIES": response.cookies.get_dict(),
            "JSON": response.json() if response.headers.get('content-type', '').startswith('application/json') else None
        }
    except Exception as e:
        return {"SOURCE": f"Error: {str(e)}", "RESPONSECODE": "ERROR", "COOKIES": {}, "JSON": None}

def parse_between(text, left_delim, right_delim):
    try:
        start = text.find(left_delim)
        if start == -1:
            return ""
        start += len(left_delim)
        end = text.find(right_delim, start)
        if end == -1:
            return ""
        return text[start:end]
    except:
        return ""

def activate_crunchy_tv(user_code):
    user_code = user_code.strip().upper()
    if not user_code:
        return False, "No code provided"
    
    cookies, cookie_file = get_valid_cookie(COOKIES_FOLDER)
    if not cookies:
        return False, "No valid cookies found in cookiescr folder"
    
    user_agent = get_user_agent()
    
    # Auth
    token_headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic bm9haWhkZXZtXzZpeWcwYThsMHE6",
        "Origin": "https://www.crunchyroll.com",
        "Referer": "https://www.crunchyroll.com/activate",
        "ETP-Anonymous-Id": cookies.get('ajs_anonymous_id', generate_uuid())
    }
    
    token_data = f"device_id={generate_uuid()}&device_type=Chrome%20on%20Android&grant_type=etp_rt_cookie"
    token_response = make_request("POST", "https://www.crunchyroll.com/auth/v1/token",
                                  headers=token_headers, data=token_data, cookies=cookies)
    
    if token_response["RESPONSECODE"] != "200":
        return False, "Cookie expired or invalid"
    
    access_token = parse_between(token_response["SOURCE"], '"access_token":"', '"')
    profile_id = parse_between(token_response["SOURCE"], '"profile_id":"', '"')
    
    # Account Info
    account_headers = {"User-Agent": user_agent, "Authorization": f"Bearer {access_token}"}
    account_response = make_request("GET", "https://beta-api.crunchyroll.com/accounts/v1/me",
                                    headers=account_headers, cookies=cookies)
    email = parse_between(account_response["SOURCE"], '"email":"', '"')
    
    # Activate
    activation_headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Origin": "https://www.crunchyroll.com",
        "Referer": "https://www.crunchyroll.com/activate",
        "ETP-Anonymous-Id": generate_uuid()
    }
    
    activation_response = make_request("POST", "https://www.crunchyroll.com/auth/v1/device",
                                       headers=activation_headers, json_data={"user_code": user_code},
                                       cookies=cookies)
    
    if activation_response["RESPONSECODE"] == "200":
        return True, {"email": email, "cookie": os.path.basename(cookie_file)}
    else:
        error_msg = "Activation failed"
        try:
            error = activation_response["JSON"]
            if error and 'code' in error:
                error_msg = error['code']
        except: pass
        return False, error_msg

if __name__ == "__main__":
    print("This is a library for MasterBot. Run MasterBot.py instead.")
