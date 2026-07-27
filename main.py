import io
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
from whatsapp_manager import WhatsAppManager

# Configuration du logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

whatsapp_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global whatsapp_manager
    logger.info("Démarrage du service, initialisation de WhatsAppManager...")
    whatsapp_manager = WhatsAppManager()
    yield
    logger.info("Arrêt du service, fermeture du navigateur...")
    if whatsapp_manager:
        whatsapp_manager.close()

app = FastAPI(title="WhatsApp Web API", lifespan=lifespan)

class MessageRequest(BaseModel):
    phone: str
    message: str

@app.get("/")
def read_root():
    return {"status": "ok", "service": "WhatsApp Web API"}

@app.get("/status")
def get_status():
    if not whatsapp_manager:
        raise HTTPException(status_code=503, detail="Le gestionnaire WhatsApp n'est pas prêt")
    return whatsapp_manager.get_status()

@app.get("/qr", responses={
    200: {
        "content": {"image/png": {}}
    }
})
def get_qr():
    if not whatsapp_manager:
        raise HTTPException(status_code=503, detail="Le gestionnaire WhatsApp n'est pas prêt")
    
    if whatsapp_manager.is_connected:
        return {"message": "Déjà connecté"}
        
    img_data = whatsapp_manager.get_qr_screenshot()
    if not img_data:
        raise HTTPException(status_code=404, detail="QR Code non disponible pour le moment (chargement en cours ou erreur)")
        
    return Response(content=img_data, media_type="image/png")

@app.post("/send")
def send_message(req: MessageRequest):
    if not whatsapp_manager:
        raise HTTPException(status_code=503, detail="Le gestionnaire WhatsApp n'est pas prêt")
        
    if not whatsapp_manager.is_connected:
        raise HTTPException(status_code=401, detail="Non connecté à WhatsApp Web. Veuillez scanner le QR code.")
        
    success, msg = whatsapp_manager.send_message(req.phone, req.message)
    if success:
        return {"status": "success", "detail": msg}
    else:
        raise HTTPException(status_code=400, detail=msg)
