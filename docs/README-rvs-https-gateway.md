# CDYP7 RV&S HTTPS Gateway

This gateway connects the static dashboard in `frontend/static/` to RV&S/Integrity through a secure server-side API.

## Why this exists

The static HTML dashboard should not collect or store Z-ID/password. Users log in to this internal HTTPS gateway; the gateway validates the credentials with RV&S and stores them only in a short-lived in-memory session.

## Endpoints

```text
GET  /health
GET  /auth/login
POST /auth/login
GET  /auth/me
POST /auth/logout
GET  /api/rvs/dashboard
GET  /api/rvs/receipt/latest
```

## Install

```powershell
pip install -r requirements-gateway.txt
```

## Run for local development without TLS

```powershell
python app/gateway/rvs_https_gateway.py --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/
```

## Run with HTTPS

Use an internal trusted certificate if available. For a local test certificate, create one with PowerShell:

```powershell
New-SelfSignedCertificate `
  -DnsName "localhost" `
  -CertStoreLocation "cert:\CurrentUser\My" `
  -KeyExportPolicy Exportable `
  -FriendlyName "CDYP7 RV&S Gateway Localhost"
```

Then export a `.pfx` and convert to cert/key using your approved internal process, or use a corporate-issued certificate.

Run:

```powershell
$env:CDYP7_TLS_CERT = "C:\certs\cdyp7-rvs-gateway.crt"
$env:CDYP7_TLS_KEY  = "C:\certs\cdyp7-rvs-gateway.key"
python app/gateway/rvs_https_gateway.py --host 0.0.0.0 --port 8443 --certfile $env:CDYP7_TLS_CERT --keyfile $env:CDYP7_TLS_KEY
```

Open:

```text
https://<gateway-host>:8443/
```

## Required RV&S config

```powershell
$env:RVS_HOST = "skobde-mks-im.kobde.trw.com"
$env:RVS_PORT = "7001"
$env:RVS_IM_EXE = "C:\app\tools\ptc\RVS\bin\im.exe"
```

The gateway uses this default query:

```text
Find Liv Projects All My Work
```

## Security controls

- Credentials are never stored in browser JavaScript.
- Session cookie is `HttpOnly` and `Secure` by default.
- Credentials are stored only in process memory and expire by default after 1 hour.
- Browser can only request allowlisted RV&S queries.
- Passwords are redacted from RV&S command errors.
- The service should run only on VPN / office Wi-Fi accessible networks.

## Frontend static page

Place the RV&S companion dashboard here:

```text
frontend/static/cdyp7-rvs-integrity-dashboard.html
```

The gateway serves it at:

```text
https://<gateway-host>:8443/
```

The page can also directly call:

```text
/api/rvs/dashboard
```

if you update its endpoint field to that path.
