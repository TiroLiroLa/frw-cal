#!/usr/bin/env python3
"""Google Calendar OAuth 2.0 authentication assistant with headless / SSH support."""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# If not running inside the virtual environment, automatically switch to .venv
if sys.prefix == sys.base_prefix:
    venv_python = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python3"
    if venv_python.exists():
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

# Allow HTTP for local redirect URIs
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError as e:
    print(f"\n[ERRO] Dependências ausentes ({e}).")
    print("Execute este script usando o ambiente virtual:")
    print("  .venv/bin/python3 src/auth.py\n")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = BASE_DIR / "config" / "credentials.json"
TOKEN_PATH = BASE_DIR / "config" / "token.json"


def authenticate_google(
    credentials_file: Path,
    token_file: Path,
    headless: bool = False,
):
    print("=" * 65)
    print("  Autenticação do Google Calendar (Google Agenda)")
    print("=" * 65)

    if not credentials_file.exists():
        print(f"\n[ERRO] Arquivo de credenciais não encontrado:")
        print(f"       {credentials_file}\n")
        print("Passo a passo para obter o 'credentials.json':")
        print("1. Acesse o Google Cloud Console: https://console.cloud.google.com/")
        print("2. Crie um novo projeto (ex: 'Smart-Calendar').")
        print("3. No menu lateral, acesse 'APIs e Serviços' -> 'Biblioteca'.")
        print("4. Pesquise por 'Google Calendar API' e clique em 'Ativar'.")
        print("5. Vá para 'APIs e Serviços' -> 'Tela de consentimento OAuth':")
        print("   - Selecione 'Externo' e preencha o nome do app e seu e-mail.")
        print("   - Em 'Usuários de teste', adicione a sua própria conta Google.")
        print("6. Vá para 'APIs e Serviços' -> 'Credenciais':")
        print("   - Clique em 'Criar credenciais' -> 'ID do cliente OAuth'.")
        print("   - Tipo de aplicativo: 'App para computador' (Desktop App).")
        print("7. Baixe o JSON gerado e salve-o como:")
        print(f"   {credentials_file}\n")
        sys.exit(1)

    print(f"Carregando credenciais de: {credentials_file}")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        scopes=SCOPES,
        redirect_uri="http://localhost:8080/",
    )

    # Detect if we are running in a headless environment (SSH / No GUI display)
    is_headless = headless or not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    creds = None
    if not is_headless:
        # Try local browser flow if graphical display is available
        try:
            print("\nAbrindo navegador local para autenticação...")
            creds = flow.run_local_server(port=8080, open_browser=True)
        except Exception as e:
            print(f"Navegador local não disponível ({e}). Alternando para modo sem monitor...")
            is_headless = True

    if is_headless:
        # Headless Flow (SSH / Sem monitor)
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="true",
        )

        print("\n" + "=" * 65)
        print("  MODO SEM MONITOR (HEADLESS / SSH)")
        print("=" * 65)
        print("1. No navegador do seu computador ou celular, abra este link:\n")
        print(f"   {auth_url}\n")
        print("2. Faça login com a sua conta Google e clique em 'Continuar/Permitir'.")
        print("3. Ao final, o navegador tentará abrir uma página que pode dar")
        print("   'Não é possível conectar' (localhost:8080). ISSO É NORMAL!")
        print("   Copie a URL inteira da barra de endereços do seu navegador.")
        print("   Exemplo: http://localhost:8080/?state=...&code=4/0A...")
        print("=" * 65)

        try:
            response_input = input("\nCole a URL copiada aqui e pressione ENTER:\n> ").strip()
        except EOFError:
            print("\nOperação cancelada.")
            sys.exit(1)

        if not response_input:
            print("[ERRO] Nenhuma URL ou código fornecido.")
            sys.exit(1)

        try:
            # Handle either the full URL or just the code parameter
            if response_input.startswith("http://") or response_input.startswith("https://"):
                flow.fetch_token(authorization_response=response_input)
            elif "code=" in response_input:
                # If partial query string was pasted
                parsed = parse_qs(response_input)
                code = parsed.get("code", [response_input])[0]
                flow.fetch_token(code=code)
            else:
                # Direct code pasted
                flow.fetch_token(code=response_input)
            creds = flow.credentials
        except Exception as e:
            print(f"\n[ERRO] Falha ao validar autorização: {e}")
            sys.exit(1)

    # Save token
    token_file.parent.mkdir(parents=True, exist_ok=True)
    with open(token_file, "w") as token:
        token.write(creds.to_json())

    print(f"\n[SUCESSO] Token salvo com sucesso em: {token_file}")

    # Test connection and list calendars
    print("\nTestando conexão com a Google Calendar API...")
    try:
        service = build("calendar", "v3", credentials=creds)
        calendar_list = service.calendarList().list().execute()
        print("\nCalendários encontrados na sua conta:")
        for cal in calendar_list.get("items", []):
            summary = cal.get("summary", "Sem nome")
            cal_id = cal.get("id")
            primary_str = " (Principal)" if cal.get("primary") else ""
            print(f" - {summary}{primary_str} [ID: {cal_id}]")
        print("\nAutenticação concluída e validada com sucesso!")
        print("Agora seu Raspberry Pi pode sincronizar a agenda continuamente sem precisar de login!")
    except Exception as e:
        print(f"[AVISO] Token salvo, mas erro ao listar calendários: {e}")


def main():
    parser = argparse.ArgumentParser(description="Autenticador do Google Calendar")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Forçar modo sem monitor (exibe link para abrir no PC e colar a resposta)",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=CREDENTIALS_PATH,
        help="Caminho para credentials.json",
    )
    parser.add_argument(
        "--token",
        type=Path,
        default=TOKEN_PATH,
        help="Caminho para salvar token.json",
    )

    args = parser.parse_args()
    authenticate_google(args.credentials, args.token, args.headless)


if __name__ == "__main__":
    main()
