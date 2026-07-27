import os
import time
import logging
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

class WhatsAppManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WhatsAppManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.driver = None
        self.is_connected = False
        self.session_dir = os.path.join(os.getcwd(), "chrome_data")
        self._initialized = True
        self._start_browser()

    def _start_browser(self):
        logger.info("Démarrage du navigateur Chrome...")
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument(f"user-data-dir={self.session_dir}")

        # Masquer l'automatisation pour éviter le blocage
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User agent pour simuler un navigateur normal
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.get("https://web.whatsapp.com/")
            logger.info("WhatsApp Web ouvert. Attente du chargement...")
            self._check_login_status_loop()
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du navigateur: {e}")
            if self.driver:
                self.driver.quit()
                self.driver = None

    def _check_login_status_loop(self):
        # Démarre un thread pour vérifier le statut de connexion régulièrement
        def check():
            while self.driver:
                try:
                    self.update_connection_status()
                except Exception as e:
                    logger.debug(f"Erreur vérification statut: {e}")
                time.sleep(5)
        
        threading.Thread(target=check, daemon=True).start()

    def update_connection_status(self):
        if not self.driver:
            self.is_connected = False
            return self.is_connected

        try:
            # Vérifie si le canvas du QR code est présent
            qr_canvas = self.driver.find_elements(By.CSS_SELECTOR, "canvas")
            # Vérifie si le panneau principal de chat (liste des conversations) est présent
            chat_pane = self.driver.find_elements(By.ID, "pane-side")
            
            if len(chat_pane) > 0:
                if not self.is_connected:
                    logger.info("Connexion WhatsApp détectée !")
                self.is_connected = True
            elif len(qr_canvas) > 0:
                self.is_connected = False
            else:
                # Écran de chargement ou autre état intermédiaire
                pass
                
        except WebDriverException:
            self.is_connected = False
            
        return self.is_connected

    def get_qr_screenshot(self):
        if not self.driver:
            return None
        
        try:
            self.update_connection_status()
            if self.is_connected:
                return None # Déjà connecté, pas de QR code
                
            # Attendre que le canvas soit présent
            canvas = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "canvas"))
            )
            # Prend un screenshot de l'élément parent qui contient le QR pour l'avoir en entier
            qr_container = canvas.find_element(By.XPATH, "..")
            return qr_container.screenshot_as_png
        except TimeoutException:
            logger.warning("Timeout attente QR code")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la capture du QR code: {e}")
            return None

    def send_message(self, phone: str, message: str):
        if not self.driver or not self.is_connected:
            return False, "Non connecté à WhatsApp Web"

        try:
            # S'assurer que le numéro n'a pas de '+' ou d'espaces
            phone_clean = "".join(filter(str.isdigit, phone))
            
            # Naviguer directement vers le chat via l'URL
            chat_url = f"https://web.whatsapp.com/send?phone={phone_clean}&text={message}"
            self.driver.get(chat_url)
            
            # Attendre que le bouton d'envoi apparaisse
            send_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Envoyer']"))
            )
            
            # Petit délai pour s'assurer que le texte est bien inséré par l'URL
            time.sleep(1) 
            
            send_button.click()
            
            # Attendre que le message soit envoyé (l'icône d'horloge disparaît souvent, mais on attend juste un peu)
            time.sleep(2)
            
            # Revenir à la page d'accueil pour éviter de rester sur le chat si besoin
            # self.driver.get("https://web.whatsapp.com/") 
            return True, "Message envoyé"
            
        except TimeoutException:
            return False, "Timeout: Le numéro est peut-être invalide ou non inscrit sur WhatsApp"
        except Exception as e:
            logger.error(f"Erreur envoi message: {e}")
            return False, str(e)

    def get_status(self):
        return {
            "browser_running": self.driver is not None,
            "whatsapp_connected": self.is_connected
        }

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.is_connected = False
            logger.info("Navigateur fermé")
