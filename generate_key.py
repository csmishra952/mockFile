import secrets

# Generate a 64-character hexadecimal string
jwt_secret = secrets.token_hex(32)
print(jwt_secret)