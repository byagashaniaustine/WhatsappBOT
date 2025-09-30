from fastapi import FastAPI, Request
from api.whatsappBOT import whatsapp_menu
from api.whatsappfile import whatsapp_file

app = FastAPI()

@app.post("/whatsapp-webhook/")
async def whatsapp_webhook(request: Request):
    # Fetch form data from the incoming Twilio POST request
    data = await request.form()
    
    # Check if Twilio reported media content attached (NumMedia > 0)
    num_media = int(data.get("NumMedia", 0))

    if num_media > 0:
        # File message → call the function directly (FIXED)
        return await whatsapp_file(data)

    # Normal text message → call the function directly (FIXED)
    return await whatsapp_menu(data)
