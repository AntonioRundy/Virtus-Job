# Virtus Job 🇦🇴

**Plataforma angolana de oportunidades profissionais** — vagas de emprego, concursos públicos, bolsas de estudo e estágios, extraídos automaticamente de fontes oficiais.

[![Next.js](https://img.shields.io/badge/Next.js-15-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com)
[![Expo](https://img.shields.io/badge/Expo-SDK_54-000020)](https://expo.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)](https://postgresql.org)
[![Claude AI](https://img.shields.io/badge/Claude-Sonnet_4.6-orange)](https://anthropic.com)

---

## Visão Geral

O Virtus Job agrega oportunidades profissionais de fontes angolanas de confiança, incluindo o **Jornal de Angola** (via pipeline visual multimodal com Claude Vision) e o **MAPTESS** (spider HTML). Os dados são estruturados por IA, validados e publicados em tempo real no site e na app móvel.

```
Fonte (JDA / MAPTESS)
    ↓
Spider / Visual Pipeline  (Playwright + Claude Vision)
    ↓
AI Extraction  (Claude Haiku → Sonnet fallback)
    ↓
Normalização + Trust Scoring
    ↓
PostgreSQL
    ↓
FastAPI  →  Next.js Web  +  Expo Mobile
```

---

## Stack Técnica

| Camada | Tecnologia |
|--------|-----------|
| **Frontend Web** | Next.js 15, Tailwind CSS, shadcn/ui, React Query |
| **App Mobile** | Expo SDK 54, Expo Router v5, React Native 0.81 |
| **Backend API** | FastAPI, SQLAlchemy 2.0 async, Alembic |
| **Base de Dados** | PostgreSQL 16, Redis 7 |
| **AI / Vision** | Anthropic Claude Sonnet 4.6 (Vision + Text) |
| **Scraping** | Playwright, BeautifulSoup, httpx |
| **Auth** | JWT (access + refresh com rotação) |
| **Infra** | Docker Compose |

---

## Estrutura do Projecto

```
virtus-job/
├── apps/
│   ├── api/           # FastAPI backend
│   ├── web/           # Next.js frontend
│   └── mobile/        # Expo React Native app
├── packages/
│   ├── types/         # TypeScript types partilhados
│   └── api-client/    # Cliente HTTP partilhado
├── scrapers/          # Pipeline de extracção
│   ├── sources/       # Spiders (JDA, MAPTESS)
│   ├── pipeline/      # AI extraction, segmentação visual
│   ├── jda_daily.py   # Script de produção diário
│   └── health_check.py
├── infrastructure/    # Docker, configs
└── docker-compose.yml
```

---

## Início Rápido

### Pré-requisitos

- Docker Desktop
- Node.js 20+
- Python 3.11+
- Expo Go (telemóvel)

### Configuração

```bash
# 1. Clonar
git clone https://github.com/AntonioRundy/Virtus-Job.git
cd Virtus-Job

# 2. Variáveis de ambiente
cp .env.example .env
# Editar .env com as credenciais reais

# 3. Iniciar serviços
docker compose up -d

# 4. Migrations da base de dados
docker compose exec api alembic upgrade head

# 5. Seed de dados de desenvolvimento
docker compose exec api python -m app.scripts.seed
```

### Desenvolvimento Mobile

```bash
cd apps/mobile
npm install
$env:EXPO_PUBLIC_API_URL="http://SEU_IP_LAN:8000"
npx expo start --host lan --port 8081 --clear
# Abrir Expo Go → exp://SEU_IP_LAN:8081
```

---

## Pipeline Visual JDA

O pipeline visual extrai anúncios de emprego directamente das páginas do Jornal de Angola no PressReader usando Claude Vision.

```bash
# Corrida manual
python -m scrapers.jda_daily --force

# Verificação de saúde do sistema
python -m scrapers.health_check

# Dry-run (sem guardar na BD)
python -m scrapers.jda_daily --dry-run --force
```

**Agendamento automático** (Windows — corre às 07:30 e 14:00 diariamente):
```powershell
powershell -ExecutionPolicy Bypass -File scrapers\setup_scheduler.ps1
```

---

## API — Endpoints Principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/opportunities` | Listar oportunidades (paginado) |
| `GET` | `/api/v1/opportunities/{slug}` | Detalhe de oportunidade |
| `POST` | `/api/v1/auth/register` | Registar utilizador |
| `POST` | `/api/v1/auth/login` | Login |
| `GET` | `/api/v1/opportunities/docs` | Swagger UI |

**Filtros:**
```
?type=VAGA|CONCURSO|BOLSA|ESTAGIO|FORMACAO
?province=Luanda|Benguela|...
?search=termo
?sort=recent|deadline
```

---

## Variáveis de Ambiente

Ver `.env.example` para a lista completa. Obrigatórias:

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (mín. 32 chars aleatórios) |
| `ANTHROPIC_API_KEY` | Chave Anthropic API (pipeline visual JDA) |
| `JDA_EMAIL` | Email da assinatura Jornal de Angola |
| `JDA_PASSWORD` | Password da assinatura JDA |

---

## Roadmap

- [x] Backend API (FastAPI + PostgreSQL)
- [x] Frontend Web (Next.js 15)
- [x] App Mobile (Expo SDK 54)
- [x] Pipeline MAPTESS (text spider)
- [x] Pipeline JDA (visual multimodal + Claude Vision)
- [x] Sistema de autenticação JWT
- [x] Agendamento automático diário
- [ ] Alertas push por tipo/província
- [ ] Painel de admin para aprovação de oportunidades
- [ ] Deploy cloud (Vercel + Render + Supabase)
- [ ] Distribuição App Store / Play Store

---

## Licença

Projecto privado — © 2026 AntonioRundy. Todos os direitos reservados.

---

*Construído para Angola 🇦🇴*
