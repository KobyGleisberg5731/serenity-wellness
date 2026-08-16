"""SMTP provider presets — pick a provider, enter email + password."""

SMTP_PRESETS = {
    "gmail": {
        "name": "Gmail",
        "description": "Use a Google App Password (not your regular password).",
        "host": "smtp.gmail.com",
        "port": "587",
        "use_tls": "1",
        "hint": "Enable 2FA, then create an App Password at myaccount.google.com/apppasswords",
    },
    "outlook": {
        "name": "Outlook / Hotmail",
        "description": "Microsoft 365, Outlook.com, Hotmail, Live.",
        "host": "smtp-mail.outlook.com",
        "port": "587",
        "use_tls": "1",
        "hint": "Use your full @outlook.com or @hotmail.com email and account password.",
    },
    "yahoo": {
        "name": "Yahoo Mail",
        "description": "Yahoo email accounts.",
        "host": "smtp.mail.yahoo.com",
        "port": "587",
        "use_tls": "1",
        "hint": "Generate an app password in Yahoo Account Security settings.",
    },
    "gmx": {
        "name": "GMX Mail",
        "description": "GMX.com, GMX.net, GMX.de and other GMX addresses.",
        "host": "mail.gmx.com",
        "port": "587",
        "use_tls": "1",
        "hint": "Use your full GMX email address and account password. Enable SMTP in GMX settings if needed.",
    },
    "icloud": {
        "name": "iCloud Mail",
        "description": "Apple iCloud email.",
        "host": "smtp.mail.me.com",
        "port": "587",
        "use_tls": "1",
        "hint": "Use an app-specific password from appleid.apple.com",
    },
    "zoho": {
        "name": "Zoho Mail",
        "description": "Zoho business email.",
        "host": "smtp.zoho.com",
        "port": "587",
        "use_tls": "1",
        "hint": "Use your full Zoho email address.",
    },
    "sendgrid": {
        "name": "SendGrid",
        "description": "Transactional email via SendGrid SMTP.",
        "host": "smtp.sendgrid.net",
        "port": "587",
        "use_tls": "1",
        "hint": "Username is literally 'apikey'. Password is your SendGrid API key.",
        "default_user": "apikey",
    },
    "mailgun": {
        "name": "Mailgun",
        "description": "Mailgun SMTP relay.",
        "host": "smtp.mailgun.org",
        "port": "587",
        "use_tls": "1",
        "hint": "Use the SMTP credentials from your Mailgun domain settings.",
    },
    "custom": {
        "name": "Custom SMTP",
        "description": "Enter host, port, and settings manually.",
        "host": "",
        "port": "587",
        "use_tls": "1",
        "hint": "",
    },
}

DEFAULT_SMTP_PRESET = "gmail"
