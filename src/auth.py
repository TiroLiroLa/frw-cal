"""Google Calendar OAuth 2.0 authentication assistant."""

import argparse
import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = BASE_DIR / "config" / "credentials.json"
TOKEN_PATH = BASE_DIR / "config" / "token.json"


def authenticate_google(credentials_file: Path, token_file: Path, console: bool = False):
    print("=" * 60)
    print("  Autenticação do Google Calendar (Google Agenda)")
    print("=" * 60)

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
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)

    creds = None
    if console:
        print("\nIniciando fluxo no terminal (console)...")
        creds = flow.run_console()
    else:
        print("\nAbrindo navegador para autenticação...")
        try:
            creds = flow.run_local_server(port=0)
        except Exception as e:
            print(f"Não foi possível abrir navegador localmente ({e}).")
            print("Tentando modo console...")
            creds = flow.run_console()

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
    except Exception as e:
        print(f"[AVISO] Token salvo, mas erro ao listar calendários: {e}")


def main():
    parser = argparse.ArgumentParser(description="Autenticador do Google Calendar")
    parser.add_argument(
        "--console",
        action="store_true",
        help="Executar autenticação no modo console (sem abrir navegador local)",
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
    authenticate_google(args.credentials, args.token, args.console)


if __name__ == "__main__":
    main()
