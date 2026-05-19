"""
Jornal de Angola — Playwright authenticator.

Handles the full login flow:
  1. Check if existing session is still valid.
  2. If not: navigate to login page, fill credentials, submit.
  3. Detect success or failure.
  4. Persist the new storage state.

Design principles:
  - Credentials come exclusively from environment variables (never hardcoded).
  - Session state is persisted to disk and reused across runs.
  - Re-authentication is transparent and automatic.
  - Graceful failure: logs clearly, never crashes the pipeline.
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from scrapers.config import settings


class AuthenticationError(Exception):
    """Raised when login fails and cannot be recovered automatically."""


class JdaAuthenticator:
    """
    Manages authentication state for the Jornal de Angola premium subscription.

    Usage:
        auth = JdaAuthenticator()
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            storage_state = await auth.ensure_authenticated(browser)
            context = await browser.new_context(storage_state=storage_state)
            ...
    """

    MAX_SESSION_AGE_HOURS = 20  # Re-authenticate if session is older than this

    def __init__(self) -> None:
        from scrapers.auth.session_manager import SessionManager
        self._session = SessionManager(settings.JDA_SESSION_FILE)

    # ─── Public interface ─────────────────────────────────────────────────────

    async def ensure_authenticated(self, browser: Any) -> dict[str, Any]:
        """
        Return a valid Playwright storage_state dict.

        Strategy:
          1. Try cached session (fast path, no network login).
          2. Verify session by loading a page (check for subscriber indicator).
          3. If invalid or expired: run full login flow.
        """
        if not settings.JDA_EMAIL or not settings.JDA_PASSWORD:
            raise AuthenticationError(
                "JDA_EMAIL and JDA_PASSWORD must be set in .env — "
                "credentials are required for authenticated access."
            )

        cached = self._session.load()
        age = self._session.age_hours()

        if cached and age is not None and age < self.MAX_SESSION_AGE_HOURS:
            logger.info(
                "JdA: using cached session ({:.1f}h old).", age
            )
            # Fast-path: trust the cache, skip network validation
            # (validation happens lazily when the spider actually fetches pages)
            return cached

        if cached:
            logger.info(
                "JdA: session too old ({:.1f}h) — re-authenticating.", age or 0
            )
        else:
            logger.info("JdA: no session found — authenticating.")

        return await self._login(browser)

    def invalidate(self) -> None:
        """Force re-authentication on the next run."""
        self._session.clear()
        logger.info("JdA session invalidated.")

    # ─── Private ─────────────────────────────────────────────────────────────

    # ─── Selectors ────────────────────────────────────────────────────────────
    # jornaldeangola.ao is an Angular SPA (Angular Material CDK).
    # Flow: page load → dismiss welcome overlay → click "Entrar" → login modal appears.

    _ENTRAR_SELECTOR = "button:has-text('Entrar'), button.bg-black"
    _EMAIL_SELECTORS = [
        "input[formcontrolname='email']",
        "input[formcontrolname='username']",
        "input[type='email']",
        "input[name='email']",
        ".cdk-overlay-pane input[type='email']",
        ".cdk-overlay-pane input[type='text']",
        "mat-dialog-container input[type='email']",
        "mat-dialog-container input[type='text']",
    ]
    _PASSWORD_SELECTORS = [
        "input[formcontrolname='password']",
        "input[type='password']",
        "input[name='password']",
        ".cdk-overlay-pane input[type='password']",
        "mat-dialog-container input[type='password']",
    ]
    _SUBMIT_SELECTORS = [
        "button[type='submit']:visible",
        ".cdk-overlay-pane button[type='submit']",
        "mat-dialog-container button[type='submit']",
        ".cdk-overlay-pane button:has-text('Entrar')",
        ".cdk-overlay-pane button:has-text('Login')",
        ".cdk-overlay-pane button:has-text('Iniciar')",
    ]

    async def _login(self, browser: Any) -> dict[str, Any]:
        """
        Run the full Playwright login flow for jornaldeangola.ao (Angular SPA).

        Flow:
          1. Navigate to the login URL (redirects to jornaldeangola.ao/#/assinantes/login)
          2. Wait for JS to render and dismiss any welcome overlay
          3. Click the "Entrar" button to open the login modal
          4. Fill credentials in the modal form
          5. Submit and wait for navigation
          6. Save session state

        Raises AuthenticationError on failure.
        """
        context = await browser.new_context(
            user_agent=settings.HTTP_USER_AGENT,
            locale="pt-AO",
            extra_http_headers={"Accept-Language": "pt-AO,pt;q=0.9"},
        )
        page = await context.new_page()

        try:
            # ── Step 1: Navigate ──────────────────────────────────────────────
            logger.info("JdA: navigating to {} ...", settings.JDA_LOGIN_URL)
            await page.goto(
                settings.JDA_LOGIN_URL,
                wait_until="domcontentloaded",
                timeout=settings.BROWSER_TIMEOUT,
            )
            await asyncio.sleep(3)  # Angular needs time to bootstrap + render
            logger.debug("JdA: landed on {}", page.url)

            # ── Step 2: Dismiss welcome overlay if present ────────────────────
            overlay = await page.query_selector(".cdk-overlay-backdrop")
            if overlay:
                logger.debug("JdA: dismissing welcome overlay...")
                await page.keyboard.press("Escape")
                await asyncio.sleep(1.5)

                # Fallback: click outside the overlay content
                still_overlay = await page.query_selector(".cdk-overlay-backdrop")
                if still_overlay:
                    await page.mouse.click(10, 10)
                    await asyncio.sleep(1.0)

            # ── Step 3: Click "Entrar" to open login modal ────────────────────
            entrar = await page.query_selector(self._ENTRAR_SELECTOR)
            if not entrar:
                raise AuthenticationError(
                    "Botão 'Entrar' não encontrado. O site pode ter mudado de layout."
                )
            logger.debug("JdA: clicking 'Entrar'...")
            await entrar.click()
            await asyncio.sleep(2)  # wait for Angular modal animation

            # ── Step 4: Find and fill email ───────────────────────────────────
            email_el = None
            for sel in self._EMAIL_SELECTORS:
                try:
                    el = await page.wait_for_selector(sel, timeout=5000, state="visible")
                    if el:
                        email_el = el
                        logger.debug("JdA: email field found with selector '{}'", sel)
                        break
                except Exception:
                    continue

            if not email_el:
                raise AuthenticationError(
                    "Campo de email não encontrado após abrir modal de login."
                )
            await email_el.fill(settings.JDA_EMAIL)

            # ── Step 5: Find and fill password ───────────────────────────────
            pwd_el = None
            for sel in self._PASSWORD_SELECTORS:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        pwd_el = el
                        logger.debug("JdA: password field found with selector '{}'", sel)
                        break
                except Exception:
                    continue

            if not pwd_el:
                raise AuthenticationError(
                    "Campo de password não encontrado no modal de login."
                )
            await pwd_el.fill(settings.JDA_PASSWORD)

            # ── Step 6: Submit ────────────────────────────────────────────────
            submit_el = None
            for sel in self._SUBMIT_SELECTORS:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        submit_el = el
                        logger.debug("JdA: submit button found with selector '{}'", sel)
                        break
                except Exception:
                    continue

            if not submit_el:
                # Fallback: press Enter on the password field
                logger.debug("JdA: submit button not found — pressing Enter")
                await pwd_el.press("Enter")
            else:
                await submit_el.click()

            # ── Step 7: Wait for login result ─────────────────────────────────
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass  # timeout is OK — Angular SPA may not trigger full reload
            await asyncio.sleep(2)

            # Check for subscriber indicators (successful login)
            current_url = page.url
            indicator = await page.query_selector(settings.JDA_SESSION_VALID_INDICATOR)
            still_on_login = "login" in current_url.lower() or "signin" in current_url.lower()

            if not indicator and still_on_login:
                raise AuthenticationError(
                    f"Login falhou — sem indicadores de sessão em {current_url}. "
                    "Verificar JDA_EMAIL e JDA_PASSWORD no .env."
                )

            # ── Step 8: Save session ──────────────────────────────────────────
            storage_state = await context.storage_state()
            self._session.save(storage_state)
            logger.success("JdA: autenticado com sucesso. Sessão guardada.")
            return storage_state

        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError(
                f"Erro inesperado durante login JdA: {exc}"
            ) from exc
        finally:
            await context.close()

    async def verify_session(self, browser: Any, storage_state: dict) -> bool:
        """
        Quick check: load base URL with saved cookies and see if subscriber
        indicators are visible. Returns True if session is still valid.
        """
        context = await browser.new_context(
            storage_state=storage_state,
            user_agent=settings.HTTP_USER_AGENT,
            locale="pt-AO",
        )
        page = await context.new_page()
        try:
            await page.goto(
                settings.JDA_BASE_URL,
                wait_until="domcontentloaded",
                timeout=settings.BROWSER_TIMEOUT,
            )
            await asyncio.sleep(0.5)
            indicator = await page.query_selector(settings.JDA_SESSION_VALID_INDICATOR)
            is_valid = indicator is not None
            logger.debug("JdA session verification: {}", "OK" if is_valid else "EXPIRED")
            return is_valid
        except Exception as exc:
            logger.warning("JdA session verification failed: {}", exc)
            return False
        finally:
            await context.close()
