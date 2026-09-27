import os
import re
import json
import requests
import DisneyBot as disney
import PrimeChecker as p_check

def extract_info_from_cookie(cookie_content, service="unknown"):
    """
    Intenta extraer información de una cookie basándose en el servicio.
    """
    results = {
        "service": service.upper(),
        "email": "N/A",
        "plan": "N/A",
        "country": "N/A",
        "expiry": "N/A"
    }

    try:
        if service == "disney":
            # Usamos el parser inteligente de DisneyBot
            acc, status = disney.get_random_disney_account_from_str(cookie_content)
            if acc:
                results.update(acc)
        
        elif service == "amazon":
            # Usamos el checker de Amazon
            info = p_check.check_prime_cookie_advanced(cookie_content)
            if info:
                results["email"] = info.get("customerID", "Found")
                results["country"] = info.get("region", "N/A")
                results["plan"] = "Prime Video"
        
        elif service == "spotify":
            # Búsqueda manual de patrones en el texto de la cookie
            email_match = re.search(r'email":"([^"]+)"', cookie_content)
            if email_match: results["email"] = email_match.group(1)
            
            country_match = re.search(r'country":"([^"]+)"', cookie_content)
            if country_match: results["country"] = country_match.group(1)
            
            plan_match = re.search(r'product":"([^"]+)"', cookie_content)
            if plan_match: results["plan"] = plan_match.group(1).upper()

        return results, "SUCCESS"

    except Exception as e:
        return None, f"[-] EXTRACTION ERROR: {str(e)}"

def format_extraction_report(data):
    if not data: return "<code>[-] ERROR: No data retrieved.</code>"
    
    report = (
        "<code>\n"
        " ╔══════════════════════════════════╗\n"
        " ║   ░▒▓█ CREDENTIAL MINER █▓▒░     ║\n"
        " ╚══════════════════════════════════╝\n\n"
        f" [🚀] SERVICE: {data['service']}\n"
        f" [📧] EMAIL:   {data['email']}\n"
        f" [💎] PLAN:    {data['plan']}\n"
        f" [🌍] COUNTRY: {data['country']}\n"
        f" [⏱️] EXPIRY:  {data['expiry']}\n"
        "</code>"
    )
    return report

# OWNER: @Zzzz_0456
