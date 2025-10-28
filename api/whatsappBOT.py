import logging
import math
from services.meta import send_meta_whatsapp_message
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("whatsapp_app")

# --- PLACEHOLDER FOR LOAN CALCULATION LOGIC ---
async def loan_calc(data: dict):
    """
    Handles the initiation of the loan calculation process. 
    This is where the bot would ask for the required parameters (repayment amount, duration, rate).
    """
    from_number_full = str(data.get("From") or "")
    
    # Standardize number to E.164 format (Meta prefers +<CountryCode><Number>)
    if from_number_full and not from_number_full.startswith("+"):
        # We assume the number is a complete international number but just missing the '+' prefix.
        from_number_full = "+" + from_number_full

    # Message instructing the user how to provide the input parameters
    message = (
        "✍️ *Loan Calculator*:\n"
        "Please submit your calculator details in this format to perform the calculation:\n"
        "*Amount: [repayment capacity], Duration: [months], Rate: [annual percentage]*\n\n"
        "Example: *Amount: 200000, Duration: 12, Rate: 18*"
    )
    send_meta_whatsapp_message(to=from_number_full, body=message)
    logger.info(f"Loan calculator prompt sent to {from_number_full}")
    return PlainTextResponse("OK")

# --- WHATSAPP MENU DATA (Updated) ---
main_menu = {
    "1": {
        "title": "Learn about Credit Scoring",
        "description": (
            "This is a metric that shows your **financial trustworthiness** and your history of past loan repayments. "
            "A good score is *critical* because it gives you the opportunity to get **loans faster**, at **lower interest rates**, "
            "and at **higher amounts** from financial institutions. Maintaining a good score requires timely debt repayment "
            "and not using more than your credit limit."
        )
    },
    "2": {
        "title": "Credit Bandwidth",
        "description": (
            "Credit Bandwidth indicates the **maximum amount** of credit that financial institutions can extend to you. "
            "This amount is calculated by analyzing your *income*, your *current debts*, and your *repayment history*. "
            "A large credit bandwidth gives you the ability to negotiate better and take out larger loans for investments or major projects."
        )
    },
    "3": {
        "title": "Nakopesheka!! (I Am Loanable!!)",
        "description": (
            "🔥 **Submit Your Financial Statements:**\n"
            "To start the *Nakopesheka* process, please **attach** a PDF file or an image containing your *transaction/payment statements* (Bank Statement/M-Pesa statements) for **at least three (3) months**. \n\n"
            "Our system will analyze it automatically and give you a response."
        )
    },
    "4": {
        "title": "Loan Calculator (Kikokotoo cha Mkopo)",
        "description": (
            "Use our loan calculator to find out how much loan you qualify for based on your monthly repayment capacity, loan duration, and interest rate.\n"
            "Send the word *CALC* to start the process of entering the calculator parameters."
        )
    },
    "5": {
        "title": "Types of Loans",
        "description": (
            "Loans are categorized based on **Collateral/Purpose** and **Interest Rate Type**.\n"
            "   * **Loans based on Purpose/Collateral:** These include **Home Loan** (long-term, low interest), "
            "**Business Loan** (for business expansion), **Education Loan** (for studies), and **Quick/Mobile Loan** (for sudden needs, short term).\n"
            "   * **Loans based on Interest Rate Type:** These include **Fixed Rate** (interest does not change over the term), "
            "**Variable Rate** (interest that changes based on the market), etc. Understanding these types helps you choose the most suitable loan."
        )
    },
    "6": {
        "title": "Nilipo Services (Where I Am)",
        "description": (
            "Services currently offered include: small purchases, digital payments, emergency expenses, short-term loans."
        )
    }
}


# --- MAIN WHATSAPP MENU HANDLER ---
async def whatsapp_menu(data: dict):
    try:
        from_number_full = str(data.get("From") or "")
        
        # ⚠️ CRITICAL FIX: Standardize number to E.164 format (Meta requires +<CountryCode><Number>)
        # This handles raw Meta numbers (255...) by adding the '+' prefix.
        if from_number_full and not from_number_full.startswith("+"):
            from_number_full = "+" + from_number_full
            
        # Removed the redundant .replace("whatsapp:", "") cleanup

        if not from_number_full or from_number_full == "+": # Check for empty or just "+"
            logger.warning("Missing 'From' number in request after standardization.")
            return PlainTextResponse("OK")

        incoming_msg = str(data.get("Body") or "").strip()
        incoming_msg_lower = incoming_msg.lower()

        # --- Show main menu ---
        if incoming_msg_lower in ["hi", "hello", "start", "menu","main menu", "yo","good morning","good evening","anza","good afternoon","habari","mambo"]:
            reply_text = (
                " *Welcome to Manka Loan Services*\n"
                " Choose the service you would like to be served with:\n\n"
                "1️⃣ Learn about Credit Scoring\n"
                "2️⃣ Credit Bandwidth\n"
                "3️⃣ I Am Loanable!!\n"
                "4️⃣ Loan Calculator\n"
                "5️⃣ Types of Loans\n"
                "6️⃣ Services offered for Loans"
            )
            send_meta_whatsapp_message(to=from_number_full, body=reply_text)
            return PlainTextResponse("OK")

        # --- Handle specific commands/selections ---
        
        # Option 4 Direct Trigger Command
        if incoming_msg_lower == "calc":
            return await loan_calc(data)

        # Handle menu selection 
        elif incoming_msg_lower in main_menu:
            selection = incoming_msg_lower
            
            # 3. Nakopesheka!! (Instruct user to send file/media upload)
            if selection == "3":
                item = main_menu[selection]
                reply_text = f"*{item['title']}*\n\n{item['description']}"
                send_meta_whatsapp_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")
                
            # 4. Loan Calculator (Call the loan calculation initiation function)
            elif selection == "4":
                # Instead of sending the full description, we call loan_calc to initiate the process immediately.
                return await loan_calc(data)

            # All other menu options (1, 2, 5, 6) just send the description
            else:
                item = main_menu[selection]
                reply_text = f"*{item['title']}*\n{item['description']}"
                send_meta_whatsapp_message(to=from_number_full, body=reply_text)
                return PlainTextResponse("OK")

        # --- Fallback ---
        send_meta_whatsapp_message(to=from_number_full, body="Sorry, I don't understand. Reply with 'menu' or 'start' to see our services.")
        return PlainTextResponse("OK")

    except Exception as e:
        logger.exception(f"Error in whatsapp_menu: {e}")

        try:
            # Safely send a user-friendly error message if sender info is available
            from_number_safe = locals().get("from_number_full", None)
            if from_number_safe:
                send_meta_whatsapp_message(
                    to=from_number_safe,
                    body="❌ Sorry, a technical error occurred. Please try again or send 'menu'."
                )
        except Exception as inner_error:
            logger.warning(f"⚠️ Failed to send error message: {inner_error}")
            pass  # Suppress further errors

        return PlainTextResponse("Internal Server Error", status_code=500)
