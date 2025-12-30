# Deployment Guide - Eltariff AI API

## Fly.io Deployment

### 1. Installera Fly CLI

```bash
# macOS
brew install flyctl

# eller
curl -L https://fly.io/install.sh | sh
```

### 2. Logga in på Fly.io

```bash
fly auth login
```

### 3. Skapa appen (första gången)

```bash
cd eltariff-ai-api
fly launch --no-deploy
```

Välj:
- Region: `arn` (Stockholm)
- App name: `eltariff`

### 4. Sätt secrets (API-nyckel)

```bash
fly secrets set ANTHROPIC_API_KEY=din-api-nyckel-här
```

### 5. Deploya

```bash
fly deploy
```

## Custom Domain (eltariff.sourceful.energy)

### 1. Lägg till domän i Fly.io

```bash
fly certs add eltariff.sourceful.energy
```

### 2. DNS-konfiguration

Lägg till en CNAME-post i din DNS (t.ex. Cloudflare, Route53):

| Type   | Name     | Target                  |
|--------|----------|-------------------------|
| CNAME  | eltariff | eltariff.fly.dev        |

Alternativt för root-domän eller om CNAME inte fungerar, använd A/AAAA:

```bash
fly ips list
```

Sedan lägg till:
| Type | Name     | Value           |
|------|----------|-----------------|
| A    | eltariff | <IPv4 från ips> |
| AAAA | eltariff | <IPv6 från ips> |

### 3. Verifiera SSL-certifikat

```bash
fly certs show eltariff.sourceful.energy
```

SSL-certifikat skapas automatiskt via Let's Encrypt (kan ta några minuter).

## Användbara kommandon

```bash
# Se loggar
fly logs

# SSH till container
fly ssh console

# Skala upp/ner
fly scale count 1

# Se status
fly status

# Öppna i browser
fly open
```

## Miljövariabler

| Variabel          | Beskrivning                    | Obligatorisk |
|-------------------|--------------------------------|--------------|
| ANTHROPIC_API_KEY | API-nyckel för Claude          | Ja           |
| PORT              | Server-port (default: 8000)    | Nej          |

## Rate Limiting

API:et har inbyggd rate limiting:
- AI-endpoints: 10 requests/timme per IP
- Övriga endpoints: Ingen begränsning

## Kostnadsuppskattning (Fly.io)

- **Free tier**: 3 shared-cpu-1x VMs med 256MB RAM
- **Nuvarande config**: 1 shared CPU, 512MB RAM
- **Uppskattad kostnad**: ~$5-10/månad beroende på användning
