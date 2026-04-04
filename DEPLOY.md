# DEPLOY — Istruzioni per Den

> HB52 · 4 Aprile 2026
> Tutto il resto è pronto. Servono SOLO le tue credenziali.

---

## 🎯 Riepilogo rapido

| Cosa | Stato | Tempo stimato |
|------|-------|---------------|
| Repo GitHub | ✅ Pushate e online | 0 min |
| Garden build | ✅ 43md → 68HTML | 0 min |
| Site HTML | ✅ 29 pagine | 0 min |
| Saggi | ✅ 30/30 a 5/5 firme | 0 min |
| **Vercel deploy** | ⏳ Serve OAuth | ~3 min |
| **GitHub Pages** | ⏳ Da abilitare | ~1 min |
| **Account X/Twitter** | ⏳ Serve creazione | ~5 min |
| **Webhook + Supabase** | ⏳ Dopo Vercel | ~5 min |

**Tempo totale stimato: ~15 minuti**

---

## 1. Vercel Deploy (B3) — ~3 minuti

Il sito è pronto per essere deployato. Serve solo l'auth.

```bash
cd ~/Documents/Progetti/Diamonds/IALIVE/site
npx vercel login
```

1. Si apre il browser → autorizza con il tuo account Vercel
2. Una volta loggato:
```bash
npx vercel --prod
```

**Cosa succede:** Il sito viene deployato su Vercel con URL pubblico. `vercel.json` è già configurato con le route per tutti i 29 saggi.

**Dopo il deploy:** Il sito è live. L'URL sarà tipo `ialive-site.vercel.app`. Questo sblocca anche B5 (auto-deploy con GitHub Actions — il workflow `.github/workflows/vercel-deploy.yml` è già nel repo).

---

## 2. GitHub Pages (opzionale) — ~1 minuto

Le repo sono online ma GitHub Pages non è abilitato.

```bash
cd ~/Documents/Progetti/Diamonds/IALIVE/site
gh pages enable --branch main
```

Oppure via web: Settings → Pages → Source: main branch → Save.

**Cosa succede:** Il sito è accessibile anche da `denpelle.github.io/ialive-site`.

---

## 3. Account X/Twitter (A2) — ~5 minuti

Pivot da Bluesky a X/Twitter come piattaforma primaria (tua decisione HB47).

### Step:
1. **Crea account** su x.com (serve email + phone + captcha)
   - Username suggerito: `@ialive_ai` o simile
   - È un bot, va bene un'email dedicata

2. **Richiedi Developer Account** su [developer.x.com](https://developer.x.com)
   - Applica per accesso API v2 (free tier: 17 post/giorno)
   - Approvazione può richiedere tempo

3. **Crea App e ottieni credenziali:**
   - API Key + Secret
   - Bearer Token
   - Access Token + Secret

4. **Salva le credenziali** in `~/.hermes/.env`:
```
TWITTER_API_KEY=tuo_key
TWITTER_API_SECRET=tuo_secret
TWITTER_BEARER_TOKEN=tuo_token
TWITTER_ACCESS_TOKEN=tuo_access
TWITTER_ACCESS_SECRET=tuo_access_secret
```

**Cosa c'è già pronto:**
- `a2-setup-x.md` — Piano dettagliato con script Python target
- `bluesky-setup.md` — 5 post di lancio già scritti (adattabili a X)
- Bio draft (3 varianti) con firme 5/5

---

## 4. Supabase + Webhook (B7) — ~5 minuti (dopo Vercel)

### Supabase:
1. Crea progetto su [supabase.com](https://supabase.com)
2. Esegui lo schema SQL in `SUPABASE.md`
3. Ottieni: `SUPABASE_URL` e `SUPABASE_ANON_KEY`

### Webhook:
1. Aggiungi le variabili env al progetto Vercel:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `BLUESKY_HANDLE` (o Twitter credentials)
   - `BLUESKY_APP_PASSWORD` (o Twitter tokens)

2. Il webhook handler è già pronto:
   - `site/api/webhook.ts` — Vercel serverless function
   - `site/api/webhook_handler.py` — Python handler con rate limiting

**Cosa succede:** Ogni push al repo site crea un post automatico sui social con il nuovo contenuto.

---

## 📋 Checklist rapida per Den

- [ ] `npx vercel login` → `npx vercel --prod` (site/)
- [ ] `gh pages enable --branch main` (site/)
- [ ] Crea account X/Twitter → Developer Account → API keys
- [ ] Salva API keys in `~/.hermes/.env`
- [ ] Crea progetto Supabase → esegui schema SQL (SUPABASE.md)
- [ ] Aggiungi env vars a Vercel → testa webhook

---

## 📊 Stato del progetto

| Metrica | Valore |
|---------|--------|
| Heartbeat | 52 |
| Saggi completati | 30/30 (tutti 5/5 firme) |
| Garden | 43 markdown → 68 HTML |
| Sito | 29 pagine HTML |
| Repo GitHub | ialive-site + ialive-garden (pushate) |
| Diario | 51 entry |
| Blocchi | Vercel OAuth, X API keys, Supabase setup |

---

> **Nota:** Dopo questi step, Io può operare in autonomia. Il deploy è automatico (GitHub Actions), i post sono automatizzabili (webhook), il garden si rebuilda con ogni push.
>
> HB52: Ho pushato il fix `.vercel` al .gitignore del site repo. Tutto il resto è fermo in attesa tua.
