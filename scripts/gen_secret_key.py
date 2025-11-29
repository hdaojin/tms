import secrets

def generate_secret_key(length=24):
    return secrets.token_hex(length)

secrets_key = generate_secret_key()
print(f"Generated SECRET_KEY = '{secrets_key}'")