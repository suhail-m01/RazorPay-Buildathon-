"""Deterministic multilingual message templates (the LLM refines copy when configured;
these are the always-available fallback and the source of truth for facts)."""
from __future__ import annotations

LANGS = ["en-IN", "hi-IN", "ta-IN", "te-IN", "mr-IN"]


def _fmt(amount_paise: int) -> str:
    return f"₹{amount_paise / 100:,.0f}"


def email_message(lang: str, name: str, merchant: str, item: str, amount_paise: int, due: str, pay_url: str) -> tuple[str, str]:
    a = _fmt(amount_paise)
    t = {
        "en-IN": (f"Payment pending: {item} — {a} (due {due})",
                  f"Hi {name},\n\nA gentle reminder from {merchant}: {item} of {a} was due on {due}.\n\nPay securely in one tap: {pay_url}\n\nNeed a few days? Just reply with how many days you need (up to 7) and we will pause all reminders until then.\n\nWarm regards,\n{merchant} · RecoverPay"),
        "hi-IN": (f"Payment baaki: {item} — {a} (due {due})",
                  f"Namaste {name},\n\n{merchant} se ek chhoti si reminder — {item} ka {a} due tha {due} ko.\n\nEk tap mein secure payment: {pay_url}\n\nKuch din chahiye? Reply karke din batayein (max 7) — hum reminders rok denge.\n\nDhanyavaad,\n{merchant} · RecoverPay"),
        "ta-IN": (f"பணம் நிலுவையில்: {item} — {a} (காலாவதி {due})",
                  f"வணக்கம் {name},\n\n{merchant} சார்பில் நினைவூட்டல் — {item} க்கு {a}, காலாவதி {due}.\n\nஒரு தட்டில் செலுத்த: {pay_url}\n\nநாட்கள் தேவையா? பதில் அளிக்கவும் (7 வரை) — நினைவூட்டல்கள் நிறுத்தப்படும்.\n\nநன்றி,\n{merchant} · RecoverPay"),
        "te-IN": (f"చెల్లింపు పెండింగ్: {item} — {a} (గడువు {due})",
                  f"నమస్కారం {name},\n\n{merchant} తరపున రిమైండర్ — {item} కు {a}, గడువు {due}.\n\nఒక్క ట్యాప్‌తో చెల్లించండి: {pay_url}\n\nరోజులు కావాలా? రిప్లై ఇవ్వండి (7 వరకు).\n\nధన్యవాదాలు,\n{merchant} · RecoverPay"),
        "mr-IN": (f"पेमेंट बाकी: {item} — {a} (देय {due})",
                  f"नमस्कार {name},\n\n{merchant} कडून स्मरणपत्रक — {item} साठी {a}, देय {due}.\n\nएका टॅपमध्ये पेमेंट: {pay_url}\n\nदिवस हवे आहेत? रिप्लाय करा (जास्तीत जास्त 7).\n\nधन्यवाद,\n{merchant} · RecoverPay"),
    }
    return t.get(lang, t["en-IN"])


def whatsapp_message(lang: str, name: str, merchant: str, item: str, amount_paise: int, due: str, pay_url: str) -> str:
    a = _fmt(amount_paise)
    t = {
        "en-IN": f"Namaste {name} 👋 {merchant} here. {item} of {a} is pending (due {due}). Pay in 1 tap: {pay_url}\nNeed time? Reply with days (up to 7). Reply STOP to opt out.",
        "hi-IN": f"Namaste {name} 👋 {merchant} se message. {item} ka {a} pending hai (due {due}). 1-tap payment: {pay_url}\nTime chahiye? Din reply karein (max 7). STOP se band.",
        "ta-IN": f"வணக்கம் {name} 👉 {merchant}. {item} — {a} நிலுவையில் (காலாவதி {due}). செலுத்த: {pay_url}\nநாட்கள் தேவையா? பதில் அளிக்கவும் (7 வரை). STOP என்று அனுப்பி நிறுத்தலாம்.",
        "te-IN": f"నమస్కారం {name} 👋 {merchant}. {item} — {a} పెండింగ్ (గడువు {due}). చెల్లించండి: {pay_url}\nరోజులు కావాలా? రిప్లై ఇవ్వండి (7 వరకు). STOP అని పంపి ఆపవచ్చు.",
        "mr-IN": f"नमस्कार {name} 👋 {merchant}. {item} — {a} बाकी (देय {due}). पेमेंट करा: {pay_url}\nदिवस हवे आहेत? रिप्लाय करा (जास्तीत जास्त 7). STOP पाठवून थांबवा.",
    }
    return t.get(lang, t["en-IN"])


def reply_message(kind: str, lang: str, name: str, pay_url: str, date: str | None = None) -> tuple[str, str]:
    t = {
        "confirm": {
            "en-IN": (f"Promise noted — reminders paused", f"Noted, {name}. All reminders are paused until {date} 09:00 IST. Pay earlier anytime: {pay_url}"),
            "hi-IN": (f"Promise note ho gaya — reminders paused", f"Noted, {name}. {date} subah 9 baje tak reminders paused. Pehle bhi pay kar sakte hain: {pay_url}"),
        },
        "reject": {
            "en-IN": ("We can hold reminders for up to 7 days", f"Sorry {name} — a hold cannot exceed 7 days. Pay now: {pay_url}\nOr reply with a date within the next 7 days."),
            "hi-IN": ("Reminders sirf 7 din tak rok sakte hain", f"Maaf kijiye {name} — hold 7 din se zyada nahi ho sakta. Abhi pay karein: {pay_url}\nYa 7 din ke andar date reply karein."),
        },
        "stop": {
            "en-IN": ("You will not be contacted again", "Understood. All outreach for this account has stopped — no further email, SMS or WhatsApp."),
            "hi-IN": ("Aapko dobara contact nahi kiya jayega", "Samajh gaye. Is account ka saara outreach band kar diya gaya hai."),
        },
        "dispute": {
            "en-IN": ("Dispute flagged — reminders paused", f"Thank you {name}. We have flagged this as a dispute and paused reminders. The team will review shortly."),
            "hi-IN": ("Dispute flag ho gaya — reminders paused", f"Dhanyavaad {name}. Dispute mark karke reminders rok di gayi hain. Team jaldi review karegi."),
        },
        "paid": {
            "en-IN": ("Checking your payment", f"Thank you {name} — we could not match a payment yet; bank confirmations can take a few minutes. If unmatched, pay here: {pay_url}"),
            "hi-IN": ("Aapka payment check ho raha hai", f"Dhanyavaad {name} — payment abhi match nahi hua; kuch minute lag sakte hain. Zarurat ho to yahan pay karein: {pay_url}"),
        },
        "unknown": {
            "en-IN": ("Tell us when you can pay", f"We did not fully understand that, {name}. Reply with the number of days you need (1–7) or pay now: {pay_url}"),
            "hi-IN": ("Batayein aap kab pay kar sakte hain", f"{name}, hum aapka message samajh nahi paye. Din reply karein (1–7) ya abhi pay karein: {pay_url}"),
        },
    }
    set_ = t.get(kind, t["unknown"])
    return set_.get(lang, set_["en-IN"])


def voice_script(lang: str, name: str, merchant: str, item: str, amount_paise: int, due: str, pay_url: str) -> str:
    """Final-rung call script. Hinglish by default — the track calls it out by name."""
    a = _fmt(amount_paise)
    first = name.split(" ")[0]
    scripts = {
        "hi-IN": (f"Namaste {first}, main {merchant} ke taraf se payment assistant bol rahi hoon. "
                  f"Aapka {item} ka payment {a} pending hai, jo {due} ko due tha. "
                  f"Aap abhi humne bheja hua link se payment kar sakte hain, ya mujhe batayein kitne din chahiye — "
                  f"zyada se zyada saat din — hum us din tak saari reminders rok denge. Dhanyavaad."),
        "en-IN": (f"Hello {first}, this is the payment assistant calling on behalf of {merchant}. "
                  f"Your {item} payment of {a} is pending since {due}. You can pay securely with the link we sent you, "
                  f"or tell me how many days you need — up to seven — and we will pause all reminders until then. Thank you."),
        "ta-IN": (f"வணக்கம் {first}, {merchant} சார்பில் பேசுகிறேன். உங்கள் {item} கட்டணம் {a} நிலுவையில் உள்ளது. "
                  f"அனுப்பிய இணைப்பின் மூலம் இப்போதே செலுத்தலாம், அல்லது எத்தனை நாட்கள் தேவை என்று சொல்லுங்கள் — ஏழு வரை. நன்றி."),
        "te-IN": (f"నమస్కారం {first}, {merchant} తరపున మాట్లాడుతున్నాను. మీ {item} చెల్లింపు {a} పెండింగ్‌లో ఉంది. "
                  f"పంపిన లింక్ ద్వారా చెల్లించవచ్చు, లేదా ఎన్ని రోజులు కావాలో చెప్పండి — ఏడు వరకు. ధన్యవాదాలు."),
        "mr-IN": (f"नमस्कार {first}, {merchant} कडून बोलत आहे. तुमचा {item} पेमेंट {a} बाकी आहे. "
                  f"पाठवलेल्या लिंकवरून पेमेंट करा, किंवा किती दिवस हवे आहेत ते सांगा — जास्तीत जास्त सात दिवस. धन्यवाद."),
    }
    return scripts.get(lang, scripts["hi-IN"] if lang not in scripts else scripts["en-IN"])
