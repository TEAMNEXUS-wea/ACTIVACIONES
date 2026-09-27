import requests
import re
import random

def get_free_proxies():
    """
    Scrapea proxies gratuitos de diversas fuentes públicas.
    """
    sources = [
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://www.proxy-list.download/api/v1/get?type=https",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"
    ]
    
    proxies = []
    for url in sources:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                found = re.findall(r'\d+\.\d+\.\d+\.\d+:\d+', response.text)
                proxies.extend(found)
        except:
            continue
            
    return list(set(proxies))

def get_random_proxy(proxy_list):
    if not proxy_list:
        return None
    proxy = random.choice(proxy_list)
    return {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }
