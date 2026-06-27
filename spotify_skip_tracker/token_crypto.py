"""
Kryptering av OAuth refresh-tokens for Spotify Skip Tracker.

Bruker Fernet (AES-128-CBC + HMAC-SHA256) fra cryptography-pakken for å
kryptere refresh-tokens før de lagres i databasen. Refresh-tokens er
langlevde hemmeligheter som gir full tilgang til en brukers Spotify-konto
inntil de tilbakekalles.

Nøkkelen leses fra TOKEN_ENCRYPTION_KEY-miljøvariabelen. Generer en ny nøkkel
med kommandoen:
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Prefiks-system for å skille mellom krypterings-modus i databasen:
    'enc:'   — Fernet-kryptert (produksjonsmodus, TOKEN_ENCRYPTION_KEY satt)
    'plain:' — klartekst (utviklingsmodus, TOKEN_ENCRYPTION_KEY ikke satt)

Tokens uten prefiks behandles som klartekst for bakoverk ompatibilitet
(f.eks. hvis en rad ble satt inn manuelt).

Eksempel:
    from spotify_skip_tracker.token_crypto import encrypt_token, decrypt_token

    encrypted = encrypt_token("AQD...")      # lagres i DB
    original  = decrypt_token(encrypted)    # brukes i API-kall
"""

import logging

logger = logging.getLogger(__name__)

_ENC_PREFIX = "enc:"
_PLAIN_PREFIX = "plain:"


def _get_fernet():
    """
    Returnerer en Fernet-instans initialisert med TOKEN_ENCRYPTION_KEY,
    eller None dersom nøkkelen ikke er satt.

    Importeres lazily slik at cryptography-pakken kun importeres ved behov
    og feilmeldinger om ugyldig nøkkel fremstår tydelig.
    """
    from .config import TOKEN_ENCRYPTION_KEY
    if not TOKEN_ENCRYPTION_KEY:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(TOKEN_ENCRYPTION_KEY.encode())
    except Exception as exc:
        raise ValueError(
            f"TOKEN_ENCRYPTION_KEY er ugyldig: {exc}. "
            "Nøkkelen må være en Fernet-nøkkel (url-safe base64, 32 bytes). "
            "Generer en ny med: "
            "python3 -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        ) from exc


def encrypt_token(plaintext: str) -> str:
    """
    Krypterer en refresh-token og returnerer en prefiks-merket streng
    som er klar for lagring i databasen.

    Med TOKEN_ENCRYPTION_KEY satt  → 'enc:<fernet-cipher>'
    Uten TOKEN_ENCRYPTION_KEY      → 'plain:<klartekst>' + advarsel i logg

    Raises:
        ValueError  dersom TOKEN_ENCRYPTION_KEY er satt men ugyldig.
    """
    fernet = _get_fernet()
    if fernet is None:
        logger.warning(
            "TOKEN_ENCRYPTION_KEY er ikke satt — refresh-token lagres i klartekst. "
            "Sett TOKEN_ENCRYPTION_KEY i Railway-miljøet for sikker tokenlagring."
        )
        return f"{_PLAIN_PREFIX}{plaintext}"

    encrypted = fernet.encrypt(plaintext.encode()).decode()
    return f"{_ENC_PREFIX}{encrypted}"


def decrypt_token(stored: str) -> str:
    """
    Dekrypterer en lagret token-streng og returnerer klartekst.

    Støtter alle tre lagringsformater:
        'enc:...'   — Fernet-kryptert, dekrypteres med TOKEN_ENCRYPTION_KEY
        'plain:...' — klartekst med prefiks (dev-modus)
        (ingen prefiks) — legacy/manuell klartekst, returneres direkte

    Raises:
        RuntimeError  dersom token er kryptert men TOKEN_ENCRYPTION_KEY mangler.
        ValueError    dersom nøkkelen er ugyldig.
        cryptography.fernet.InvalidToken  dersom kryptert data er korrupt.
    """
    if stored.startswith(_ENC_PREFIX):
        fernet = _get_fernet()
        if fernet is None:
            raise RuntimeError(
                "Token er Fernet-kryptert ('enc:'-prefiks), men TOKEN_ENCRYPTION_KEY "
                "er ikke satt. Sett riktig nøkkel i Railway-miljøet for å dekryptere "
                "lagrede tokens."
            )
        return fernet.decrypt(stored[len(_ENC_PREFIX):].encode()).decode()

    if stored.startswith(_PLAIN_PREFIX):
        return stored[len(_PLAIN_PREFIX):]

    # Ingen prefiks: legacy / manuelt innsatt klartekst
    return stored
