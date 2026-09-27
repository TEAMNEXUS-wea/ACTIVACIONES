import cv2
import os
import numpy as np

def scan_qr_from_image(image_path):
    """
    Escanea una imagen en busca de códigos QR usando el detector nativo de OpenCV.
    No requiere DLLs externas como pyzbar.
    """
    if not os.path.exists(image_path):
        return None, "[-] ERROR: Image not found."

    try:
        # Cargamos la imagen
        img = cv2.imread(image_path)
        if img is None:
            return None, "[-] ERROR: Could not read image."

        # Inicializamos el detector de QR nativo de OpenCV
        detector = cv2.QRCodeDetector()
        
        # Intentamos detectar y decodificar
        data, points, straight_qrcode = detector.detectAndDecode(img)

        # Si no detecta nada, intentamos optimizar la imagen (Gris y Contraste)
        if not data:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Aumentamos el contraste para fotos de TV
            alpha = 1.5 # Contraste
            beta = 0    # Brillo
            adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
            data, points, straight_qrcode = detector.detectAndDecode(adjusted)

        if not data:
            return None, "NO_QR_FOUND"

        return data.strip(), "SUCCESS"

    except Exception as e:
        return None, f"[-] VISION ERROR: {str(e)}"

# OWNER: @Zzzz_0456
