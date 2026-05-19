"""
Virtus Job — Health Check
=========================
Verifica o estado de saúde completo do sistema:
  - API (backend)
  - Base de dados (oportunidades activas)
  - Pipeline JDA (última corrida bem-sucedida)
  - Metro mobile (porta 8081)
  - ANTHROPIC_API_KEY válida

Uso:
  python -m scrapers.health_check
  python -m scrapers.health_check --fix   # tenta resolver problemas automáticos

Saídas:
  EXIT 0 = tudo OK
  EXIT 1 = problemas detectados
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
RUN_LOG = ROOT / "logs" / "jda_daily_runs.json"

import os
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://virtus:virtus_secret@localhost:5432/virtus_job"
)

OK   = "[OK]  "
WARN = "[WARN]"
FAIL = "[FAIL]"


async def check_api() -> tuple[bool, str]:
    """Verifica se a API está a responder."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("http://localhost:8000/health")
            if r.status_code == 200:
                return True, "API respondeu 200 OK"
            return False, f"API respondeu {r.status_code}"
    except Exception as e:
        return False, f"API inacessível: {e}"


async def check_db_opportunities() -> tuple[bool, str]:
    """Verifica se há oportunidades activas na BD."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("http://localhost:8000/api/v1/opportunities?per_page=1")
            data = r.json()
            total = data.get("total", 0)
            if total > 0:
                return True, f"{total} oportunidades activas na BD"
            return False, "BD sem oportunidades activas"
    except Exception as e:
        return False, f"Erro ao verificar BD: {e}"


def check_jda_pipeline() -> tuple[bool, str]:
    """Verifica se o pipeline JDA correu recentemente."""
    if not RUN_LOG.exists():
        return False, "Pipeline nunca correu (log não encontrado)"
    try:
        runs = json.loads(RUN_LOG.read_text(encoding="utf-8-sig"))
        if not runs:
            return False, "Log existe mas sem registos"
        last = runs[-1]
        last_date = last.get("date", "")
        last_success = last.get("success", False)
        last_saved = last.get("saved", 0)
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last_date == today and last_success:
            return True, f"Correu hoje — {last_saved} oportunidades guardadas"
        if last_date == yesterday and last_success:
            return True, f"Correu ontem ({last_date}) — {last_saved} guardadas (hoje ainda não)"
        if not last_success:
            return False, f"Última corrida ({last_date}) FALHOU: {last.get('error', '?')[:80]}"
        days_ago = (date.today() - date.fromisoformat(last_date)).days
        return False, f"Última corrida há {days_ago} dias ({last_date}) — pipeline desactualizado"
    except Exception as e:
        return False, f"Erro ao ler log: {e}"


def check_metro() -> tuple[bool, str]:
    """Verifica se o Metro mobile está activo na porta 8081."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", 8081))
        s.close()
        if result == 0:
            return True, "Metro activo em exp://192.168.1.11:8081"
        return False, "Metro não está a correr (porta 8081 fechada)"
    except Exception as e:
        return False, f"Erro ao verificar Metro: {e}"


def check_anthropic_key() -> tuple[bool, str]:
    """Verifica se ANTHROPIC_API_KEY está configurada e tem formato válido."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        # Tentar via ScraperSettings (lê .env automaticamente)
        try:
            from scrapers.config import ScraperSettings
            s = ScraperSettings()
            key = s.ANTHROPIC_API_KEY
        except Exception:
            pass
    if not key:
        # Fallback: ler .env directamente
        for env_path in [ROOT / ".env", Path.cwd() / ".env"]:
            if env_path.exists():
                try:
                    content = env_path.read_text(encoding="utf-8-sig")
                    for line in content.splitlines():
                        if "ANTHROPIC_API_KEY" in line and "=" in line:
                            val = line.split("=", 1)[1].strip()
                            if val and val != "":
                                key = val
                                break
                    if key:
                        break
                except Exception:
                    pass
    if not key:
        return False, "ANTHROPIC_API_KEY não definida no .env"
    if not key.startswith("sk-ant-"):
        return False, f"ANTHROPIC_API_KEY tem formato inválido (não começa com sk-ant-)"
    if key.startswith("sk-ant-api03-sk-ant-"):
        return False, "ANTHROPIC_API_KEY tem prefixo duplicado (copiar novamente do console)"
    return True, f"ANTHROPIC_API_KEY válida ({key[:20]}...)"


def check_docker_services() -> tuple[bool, str]:
    """Verifica se os containers Docker estão activos."""
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}:{{.Status}}"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout
        services = {"virtus_api": False, "virtus_postgres": False, "virtus_web": False}
        for line in output.splitlines():
            for name in services:
                if name in line and "Up" in line:
                    services[name] = True
        down = [k for k, v in services.items() if not v]
        if not down:
            return True, "Todos os containers Docker activos (api, postgres, web)"
        return False, f"Containers em baixo: {', '.join(down)}"
    except Exception as e:
        return False, f"Docker inacessível: {e}"


async def main(fix: bool = False) -> int:
    """Executa todos os checks e imprime relatório."""
    print("=" * 55)
    print(f"Virtus Job — Health Check  [{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print("=" * 55)

    checks = [
        ("Docker",           check_docker_services()),
        ("API",              await check_api()),
        ("Base de Dados",    await check_db_opportunities()),
        ("Pipeline JDA",     check_jda_pipeline()),
        ("ANTHROPIC Key",    check_anthropic_key()),
        ("Metro Mobile",     check_metro()),
    ]

    problems = 0
    for name, (ok, msg) in checks:
        icon = OK if ok else (WARN if "ontem" in msg or "hoje ainda não" in msg else FAIL)
        status = "OK  " if ok else "----"
        print(f"  {icon} {name:<18} {msg}")
        if not ok and icon == FAIL:
            problems += 1

    print("=" * 55)

    if problems == 0:
        print("  Sistema operacional — tudo funcional.")
    else:
        print(f"  {problems} problema(s) detectado(s).")
        if fix:
            print("  A tentar correcções automáticas...")
            await auto_fix(checks)

    print("=" * 55)
    return 0 if problems == 0 else 1


async def auto_fix(checks: list) -> None:
    """Tenta corrigir problemas detectados automaticamente."""
    import subprocess

    for name, (ok, msg) in checks:
        if ok:
            continue

        if name == "Docker":
            print(f"  Tentando iniciar containers Docker...")
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=str(ROOT), capture_output=True,
            )

        if name == "Metro Mobile" and not ok:
            print("  Metro não activo. Para iniciar:")
            print("    Set-Location apps/mobile")
            print("    $env:EXPO_PUBLIC_API_URL='http://192.168.1.11:8000'")
            print("    npx expo start --host lan --port 8081 --clear")

        if name == "Pipeline JDA" and "nunca correu" in msg:
            print("  Pipeline nunca correu. Para executar:")
            print("    python -m scrapers.jda_daily --force")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true",
                        help="Tentar corrigir problemas automaticamente")
    args = parser.parse_args()

    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    exit_code = asyncio.run(main(args.fix))
    sys.exit(exit_code)
