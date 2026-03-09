# Authentication & RBAC

## Auth Flow

```
1. POST /api/auth/login  { username, password }
       |
       v
2. Server verifies bcrypt hash (12 rounds)
       |
       v
3. Returns:  access_token (JWT, 30min)  in body
             refresh_token (JWT, 7d)    as httponly cookie
       |
       v
4. Client sends access_token in Authorization: Bearer header
       |
       v
5. When access_token expires -> POST /api/auth/refresh
   (refresh_token sent automatically via cookie)
```

**Why two tokens?**
- Short-lived access token limits damage window if intercepted
- Long-lived refresh token (httponly cookie) can't be read by JavaScript (XSS protection)
- Refresh rotation: every refresh issues a new refresh token, invalidating the old one

## Role Hierarchy

| Role | Can do |
|---|---|
| `root` | Everything. Created on first boot via env vars or auto-generated token |
| `admin` | Manage users, view all data, force password resets |
| `user` | Manage own bots, credentials, trades. No admin panel |

Enforced by `get_current_user` dependency that checks `user.role` in route handlers.

## Root Bootstrap (Elasticsearch Pattern)

On first startup, if no users exist:
1. Check `ROOT_PASSWORD` env var
2. If set -> create root user with that password
3. If empty -> generate a random token, print it to stdout once

This avoids hardcoded defaults while allowing automated deployments.

## Credential Encryption

```python
from cryptography.fernet import Fernet
cipher = Fernet(FERNET_KEY)
encrypted = cipher.encrypt(api_key.encode())  # encrypt
decrypted = cipher.decrypt(encrypted).decode()  # decrypt
```

Fernet provides AES-128-CBC + HMAC-SHA256 — encryption AND authentication. If someone tampers with the ciphertext, decryption fails rather than returning garbage.

## Deep Dive

- JWT introduction: https://jwt.io/introduction
- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- Why httponly cookies: https://owasp.org/www-community/HttpOnly
- Fernet spec: https://github.com/fernet/spec/blob/master/Spec.md
