# 🗓️ Smart Calendar (frw-cal)

Sistema de **calendário inteligente com tela e-Paper (tinta eletrônica)** de 4.2 polegadas (Preto, Branco e Vermelho) da **WeAct Studio**, acionado por um **Raspberry Pi Zero 2W** e integrado ao **Google Agenda (Google Calendar)**.

![Preview do Calendário](output/preview.png)

---

## ✨ Funcionalidades

- **Grid Mensal Dinâmico:**
  - Visualização completa do mês atual com cabeçalhos dos dias da semana.
  - Domingos destacados em **vermelho**.
  - O **dia de hoje** é realçado com um círculo sólido **vermelho** e numeração branca invertida.
  - Indicadores discretos (pontos) nos dias com compromissos agendados (**vermelho** para aniversários, **preto** para compromissos gerais).
- **Cabeçalho de Destaque:**
  - Tag superior com o **dia da semana** (ex: `SEXTA-FEIRA`).
  - **Número do dia atual em tamanho grande**.
  - Mês e ano (ex: `OUTUBRO 2026`).
- **Agenda & Próximos Compromissos:**
  - Painel lateral dedicado aos próximos compromissos e tarefas.
  - Destaques especiais: `[HOJE · 10:00]`, `[AMANHÃ · 17:00]` e `[ANIVERSÁRIO]`.
  - Exibição de horários, títulos de eventos e locais (ex: Google Meet, clínicas, etc.).
- **Previsão do Tempo Integrada:**
  - Temperatura atual e condição climática via API Open-Meteo (100% gratuita, sem necessidade de chaves de API).
- **Proteção e Economia do E-Paper:**
  - Coloca o display em modo de suspensão ultra-profunda (*deep sleep*) após cada atualização, prolongando a vida útil dos microcápsulas e reduzindo o consumo de energia a quase zero.
  - Horários ativos configuráveis (evita atualizações desnecessárias durante a madrugada).
  - Atualização automática precisa à meia-noite para avançar o dia no grid.
- **Cache Offline Resiliente:**
  - Se a conexão Wi-Fi oscilar ou cair temporariamente, o calendário mantém a última exibição válida e continua funcionando normalmente.
- **Modo Simulador no PC:**
  - Gere e visualize a renderização exata da tela em formato PNG no seu computador sem precisar do hardware conectado.

---

## 🔌 Ligação dos Pinos (Pinout GPIO)

O módulo **WeAct Studio 4.2" E-Paper (Preto/Branco/Vermelho - driver SSD1683)** se conecta ao conector de 40 pinos do Raspberry Pi Zero 2W via SPI:

| Pino do Display (WeAct) | Função | Pino Raspberry Pi (Físico) | Nome GPIO (BCM) |
| :--- | :--- | :--- | :--- |
| **VCC** / 3V3 | Alimentação 3.3V | **Pino 1** | 3.3V Power |
| **GND** | Terra / Ground | **Pino 6** | Ground |
| **DIN** / SDI / MOSI | Dados SPI | **Pino 19** | GPIO 10 (MOSI) |
| **CLK** / SCK | Clock SPI | **Pino 23** | GPIO 11 (SCLK) |
| **CS** | Chip Select | **Pino 24** | GPIO 8 (CE0) |
| **DC** / D/C | Data / Command | **Pino 22** | GPIO 25 |
| **RST** / RES | Reset | **Pino 11** | GPIO 17 |
| **BUSY** | Sinal de Ocupado | **Pino 18** | GPIO 24 |

> [!NOTE]
> Os pinos GPIO acima são os padrões recomendados e já vêm pré-configurados em [config/config.yaml](file:///home/scs/Projects/frw-cal/config/config.yaml). Caso deseje usar pinos diferentes, basta alterá-los na seção `display.pins`.

---

## 🚀 Instalação Rápida no Raspberry Pi

No terminal do seu Raspberry Pi Zero 2W:

```bash
# 1. Clone o repositório no Raspberry Pi
cd ~/
git clone https://github.com/TiroLiroLa/frw-cal.git
cd frw-cal

# 2. Execute o instalador automatizado
chmod +x install.sh
./install.sh
```

O script `install.sh` instala os pacotes do sistema, habilita a interface SPI (`raspi-config`), cria o ambiente virtual Python (`.venv`) e instala todas as dependências.

---

## 📅 Conectando com o Google Agenda

Você pode integrar o seu calendário de **3 formas diferentes**:

### Opção 1: Google Calendar API Oficial (OAuth 2.0) — *Recomendado*

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um projeto (ex: `Smart-Calendar`).
3. Vá em **APIs e Serviços** > **Biblioteca**, busque por **Google Calendar API** e clique em **Ativar**.
4. Vá em **APIs e Serviços** > **Tela de consentimento OAuth**:
   - Escolha **Externo**.
   - Preencha o nome do app e seu e-mail.
   - Na aba **Usuários de teste**, adicione o seu e-mail do Google.
5. Vá em **APIs e Serviços** > **Credenciais**:
   - Clique em **Criar credenciais** > **ID do cliente OAuth**.
   - Tipo de aplicativo: **App para computador** (Desktop App).
   - Baixe o arquivo JSON gerado.
6. Renomeie o arquivo baixado para `credentials.json` e coloque-o na pasta `config/credentials.json`.
7. Execute o assistente de autenticação:
   ```bash
   .venv/bin/python3 src/auth.py
   ```
   Ele abrirá o navegador para autorizar a leitura do calendário e salvará o `config/token.json` automaticamente.

8. No arquivo [config/config.yaml](file:///home/scs/Projects/frw-cal/config/config.yaml), defina:
   ```yaml
   calendar:
     mode: "google_api"
   ```

---

### Opção 2: Endereço Secreto iCal/ICS — *Super Fácil (Sem Google Cloud)*

Se não quiser criar um projeto no Google Cloud, use o link iCal privado:
1. Abra o [Google Calendar no navegador](https://calendar.google.com/).
2. Clique nos 3 pontinhos ao lado da sua agenda > **Configurações e compartilhamento**.
3. Role até a seção **Integrar agenda** e copie o link de **"Endereço secreto no formato iCal"**.
4. No arquivo [config/config.yaml](file:///home/scs/Projects/frw-cal/config/config.yaml):
   ```yaml
   calendar:
     mode: "ical"
     ical:
       urls:
         - "https://calendar.google.com/calendar/ical/seu_email%40gmail.com/private-xxxx/basic.ics"
   ```

---

### Opção 3: Modo Demonstração (Mock) — *Para testes imediatos*

Já vem ativo por padrão! Gera compromissos e aniversários realistas para testar a renderização sem precisar de nenhuma credencial ou internet:
```yaml
calendar:
  mode: "mock"
```

---

## 💻 Teste e Visualização Prévia no PC

Você pode desenvolver e verificar o visual do calendário a qualquer momento no seu computador sem precisar do Raspberry Pi:

```bash
# Executa a geração do preview
python3 run_preview.py
```

O script gerará a imagem renderizada em:
- [output/preview.png](file:///home/scs/Projects/frw-cal/output/preview.png) (visão realista de como fica na tela e-paper)
- [output/black_channel.png](file:///home/scs/Projects/frw-cal/output/black_channel.png) (canal de tinta preta)
- [output/red_channel.png](file:///home/scs/Projects/frw-cal/output/red_channel.png) (canal de tinta vermelha)

---

## ⚙️ Inicialização Automática no Boot (Systemd)

Para que o calendário inicie sozinho sempre que o Raspberry Pi for ligado:

```bash
# 1. Copie o arquivo de serviço para o systemd
sudo cp systemd/frw-cal.service /etc/systemd/system/

# 2. Recarregue os daemons
sudo systemctl daemon-reload

# 3. Habilite e inicie o serviço
sudo systemctl enable --now frw-cal.service

# 4. Para ver os logs em tempo real:
journalctl -u frw-cal.service -f
```

---

## 📂 Estrutura do Código

```
frw-cal/
├── assets/
│   └── fonts/                 # Fontes TTF embutidas (Liberation Sans)
├── config/
│   ├── config.example.yaml    # Modelo com todas as opções comentadas
│   ├── config.yaml            # Configuração ativa do usuário
│   ├── credentials.json       # Credenciais OAuth do Google (opcional)
│   └── token.json             # Token de acesso gerado após login
├── data/                      # Caches locais para funcionamento offline
├── output/
│   ├── preview.png            # Pré-visualização da tela renderizada
│   ├── black_channel.png      # Canal monocromático preto
│   └── red_channel.png        # Canal monocromático vermelho
├── src/
│   ├── calendar_provider/     # Módulos de integração de calendário
│   │   ├── base.py            # Dataclasses e interface abstrata
│   │   ├── google_api.py      # Conexão oficial Google Calendar API
│   │   ├── ical_provider.py   # Leitor de links iCal/ICS do Google
│   │   └── mock_provider.py   # Gerador de dados de teste
│   ├── display/               # Drivers de exibição
│   │   ├── base.py            # Interface base para displays
│   │   ├── epd4in2b_v2.py     # Driver WeAct 4.2" BWR (SSD1683)
│   │   ├── epdconfig.py       # Controle de pinos GPIO e SPI via hardware
│   │   └── mock_display.py    # Simulador que exporta imagens PNG
│   ├── ui/                    # Renderização gráfica Pillow
│   │   ├── canvas.py          # Gerenciador das camadas Preto / Vermelho
│   │   ├── fonts.py           # Carregador e cache de fontes
│   │   ├── renderer.py        # Orquestrador do layout 400x300
│   │   ├── utils.py           # Sanitização de texto e emojis
│   │   └── components/
│   │       ├── header.py      # Dia da semana, data grande, mês e ano
│   │       ├── month_grid.py  # Grid mensal com dia atual e pontos de eventos
│   │       ├── event_list.py  # Próximos compromissos e aniversários
│   │       └── status_bar.py  # Horário de sincronização e status
│   ├── auth.py                # Assistente interativo de login Google OAuth
│   ├── config.py              # Leitor tipado de configurações
│   ├── main.py                # Ponto de entrada e ciclo de atualização
│   └── weather.py             # Previsão do tempo gratuita (Open-Meteo)
├── systemd/
│   └── frw-cal.service        # Serviço systemd para inicialização no boot
├── install.sh                 # Script instalador para o Raspberry Pi OS
├── requirements.txt           # Dependências Python
├── run_preview.py             # Script de teste rápido no computador
└── README.md                  # Documentação completa do projeto
```
