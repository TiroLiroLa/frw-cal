# 📟 Firmware ESP32 - Smart Calendar (NodeMCU-32S)

Adaptação nativa e autônoma do **Smart Calendar (frw-cal)** para o microcontrolador **NodeMCU-32S (ESP32)** com display **WeAct Studio 4.2" E-Paper (Preto, Branco e Vermelho - SSD1683)**.

O ESP32 executa **100% de forma autônoma**, sem depender de um computador ou servidor Raspberry Pi ligado:
1. Conecta ao Wi-Fi.
2. Sincroniza o relógio via NTP (Horário de Brasília / configurável).
3. Obtém o token de acesso via OAuth 2.0 da **Google Calendar API** e busca os compromissos (ou via iCal / modo Mock).
4. Renderiza a interface gráfica com layout idêntico ao do Raspberry Pi (mesma tipografia Liberation Sans Bold, cápsulas vermelhas, grade mensal e destaques).
5. Atualiza o display e-paper e entra em **Deep Sleep** (consumo ultra-baixo na faixa de microampères, ideal para bateria).

---

## 🔌 Ligação dos Pinos (Pinout NodeMCU-32S)

Conecte os 8 pinos do módulo **WeAct Studio 4.2" E-Paper (SSD1683)** aos pinos do **NodeMCU-32S**:

| Pino do Display (WeAct) | Função SPI | Pino NodeMCU-32S (GPIO) | Observações |
| :--- | :--- | :--- | :--- |
| **VCC** / 3V3 | Alimentação 3.3V | **3V3** | Alimentação estável 3.3V |
| **GND** | Terra / Ground | **GND** | Terra comum |
| **DIN** / SDI / MOSI | Dados SPI | **GPIO 23** | VSPI MOSI |
| **CLK** / SCK | Clock SPI | **GPIO 18** | VSPI SCK |
| **CS** | Chip Select | **GPIO 5** | VSPI SS |
| **DC** / D/C | Data / Command | **GPIO 17** | Controle de comando |
| **RST** / RES | Reset | **GPIO 16** | Reset do display |
| **BUSY** | Sinal Ocupado | **GPIO 4** | Monitora refresh da tela |

### 💡 Iluminação Frontal (Frontlight) e Botão de Leitura

| Componente | Pino NodeMCU-32S (GPIO) | Ligação / Observações |
| :--- | :--- | :--- |
| **Transistor dos LEDs** | **GPIO 25** | Conectado à Base (B) via resistor de **1kΩ** |
| **Botão de Leitura (Push Button)** | **GPIO 33** | Ligado entre o **GPIO 33** e o **GND** (pull-up interno ativo) |

#### Esquema Elétrico Recomendado:

```text
       VIN (5V USB)
            │
      ┌─────┴──────────────┐
      │                    │
   [120Ω]               [120Ω]        (Resistores de 100Ω a 150Ω, 1/4W)
      │                    │
    [LED 1] (Anodo +)    [LED 2] (Anodo +)
    (Catodo -)           (Catodo -)
      │                    │
      └─────┬──────────────┘
            │
        Coletor (C)
  GPIO 25 ──[ 1kΩ ]── Base (B)  [Transistor NPN: BC547, BC548 ou 2N2222]
        Emissor (E)
            │
           GND (Comum)

  GPIO 33 ──[ Push Button ]── GND  (Botão de leitura táctil na moldura)
```

* **Como funciona**: Quando o ESP32 está em *Deep Sleep*, ao apertar o botão no **GPIO 33**, o microcontrolador acorda instantaneamente via interrupção `EXT0`, acende os LEDs brancos no **GPIO 25** por 15 segundos (configurável em `LIGHT_TIMEOUT_SECONDS`) e volta a dormir sem religar Wi-Fi ou redesenhar a tela, economizando 100% de bateria. Se apertar o botão novamente enquanto a luz estiver acesa, ela apaga imediatamente.

> [!NOTE]
> Os pinos e tempo de iluminação podem ser personalizados em [firmware/include/config.h](include/config.h).

---

## 🚀 Configuração Rápida das Credenciais

Como o seu projeto já possui a autenticação do Google Calendar (`config/token.json`), você pode sincronizar todas as credenciais e configurações automaticamente com um único comando:

```bash
# Na raiz do projeto frw-cal:
python3 tools/sync_esp32_config.py
```

O script irá:
- Extrair o `client_id`, `client_secret` e `refresh_token` do Google Agenda.
- Configurar os IDs das agendas (`primary`, `birthdays`, `holidays`).
- Gerar o arquivo [firmware/include/config.h](include/config.h).

### Configurando o Wi-Fi

Abra o arquivo [firmware/include/config.h](include/config.h) e informe o nome e senha da sua rede Wi-Fi:

```c
#define WIFI_SSID       "Sua_Rede_WiFi"
#define WIFI_PASSWORD   "Sua_Senha_WiFi"
```

---

## 🛠️ Compilação e Gravação

Você pode compilar e gravar o firmware usando o **PlatformIO** ou o **Arduino IDE**:

### Opção A: PlatformIO (Recomendado)

O PlatformIO gerencia automaticamente a instalação do compilador e de todas as bibliotecas (`ArduinoJson`).

```bash
# 1. Conecte o NodeMCU-32S na porta USB do computador

# 2. Compile e grave diretamente:
.venv/bin/pio run -d firmware --target upload

# 3. Abra o monitor serial para acompanhar o ciclo de atualização:
.venv/bin/pio device monitor -d firmware
```

### Opção B: Arduino IDE

1. Abra o **Arduino IDE** (v1.8.x ou v2.x).
2. Adicione a URL de placas ESP32 em **Arquivo** > **Preferências** > **URLs do Gerenciador de Placas**:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. No **Gerenciador de Placas**, busque por `esp32` (da Espressif) e instale.
4. No **Gerenciador de Bibliotecas**, instale:
   - `ArduinoJson` (versão 7.x por Benoît Blanchon).
5. Abra o arquivo [firmware/firmware.ino](firmware.ino).
6. Selecione a placa **NodeMCU-32S** (ou **ESP32 Dev Module**) e a porta serial correspondente.
7. Clique no botão **Carregar** (Upload).

---

## ⚡ Economia de Energia (Deep Sleep)

- **Modo Diário (`REFRESH_MODE_DAILY` - Padrão):** O ESP32 calcula com precisão os segundos restantes até a meia-noite (`00:00:30`), atualiza o calendário e entra em modo deep sleep durante todo o dia. O consumo de corrente cai para ~15-20 µA, permitindo que o dispositivo funcione por semanas ou meses com uma bateria LiPo 18650.
- **Modo Intervalo (`REFRESH_MODE_INTERVAL`):** Atualiza a cada X minutos (configurável em `INTERVAL_MINUTES`).
- **Resiliência Offline:** Se a rede Wi-Fi ou a API do Google cair temporariamente, o ESP32 carrega o cache gravado na memória Flash (NVS/Preferences) e mantém a tela atualizada sem travar.

---

## 📶 Gerenciamento Sem Fio & Modo Manutenção (Zero Cabos)

O firmware conta com suporte nativo a **atualizações e diagnósticos 100% sem fio**, eliminando a necessidade de conectar cabos USB após a primeira gravação:

### 1. Comandos do Botão Físico (GPIO 33) & Feedback no LED (GPIO 25)

O botão multifunção utiliza um sistema inteligente de **cliques rápidos** e **feedback visual em tempo real no LED**, sem necessidade de ficar contando segundos no escuro:

| Comando | Ação Disparada | Feedback Visual no LED |
| :--- | :--- | :--- |
| **1 Clique (Toque simples)** | **Luz de Leitura (Frontlight):** Acende a iluminação suave por 15 segundos para ler a tela no escuro. Pressionar novamente desliga antecipadamente. | LED acende imediatamente e fica contínuo |
| **2 Cliques Rápidos (Duplo clique)** | **Forçar Sincronização:** Acorda o ESP32, conecta na VPN WireGuard (`10.8.0.7`), busca eventos do Google Calendar, atualiza o display E-Paper e envia telemetria à VPS. | **LED pisca 2 vezes** claramente (`💡__💡`) |
| **3 Cliques Rápidos (Triplo clique)** | **Modo Manutenção (Web UI & OTA):** Conecta à VPN no IP `10.8.0.7`, inicia o servidor web e receptor OTA por 5 minutos. Clique no botão para sair a qualquer momento. | **LED pisca 3 vezes rápidas** (`💡_💡_💡`) + **pulso (heartbeat)** a cada 3s durante o modo |
| *(Opcional: Segurar)* | Se preferir segurar o botão continuamente, o LED avisa o momento exato de soltar: aos 1.5s pisca 2x (Sync) e aos 3.5s pisca rápido 4x (Manutenção). | Indicação visual durante o toque |

### 2. Atualização Sem Fio e Painel de Manutenção (Zero Fricção com IPs Dinâmicos)

Para nunca depender de saber qual IP o roteador de casa atribuiu ao ESP32, você conta com **3 alternativas robustas**:

#### Método A: Via Oracle VPN WireGuard (IP Fixo `10.8.0.7`) — *Recomendado*
O ESP32 está cadastrado como peer na sua VPN Oracle (`10.8.0.7`). Ao entrar em Modo Manutenção, ele se conecta diretamente ao túnel:
* **Upload direto pelo terminal:**
  ```bash
  ./scripts/upload_vpn.sh
  # Ou equivalente:
  pio run -d firmware -t upload --upload-port 10.8.0.7
  ```
* **Painel Web na VPN:** Acesse no navegador: **`http://10.8.0.7/`**
* O IP `10.8.0.7` é **estático e imutável**, não importando qual rede Wi-Fi o ESP32 estiver utilizando.

#### Método B: Via mDNS na Rede Local (`frw-cal.local`)
Sem precisar da VPN e sem saber o IP:
* **Upload via terminal:**
  ```bash
  ./scripts/upload_mdns.sh
  # Ou equivalente:
  pio run -d firmware -t upload --upload-port frw-cal.local
  ```
* **Painel Web:** Acesse: **`http://frw-cal.local/`**

#### Método C: Auto-Update Silencioso pela VPS (Zero-Touch)
Nem requer Modo Manutenção:
1. Digite `calendario` no terminal e pressione `[f]` para ativar o novo `.bin`.
2. O ESP32 baixa a atualização sozinho no próximo ciclo agendado e grava na memória flash de forma autônoma.

---

## ☁️ Hub Central na VPS & Terminal ASCII (`calendario`)

O ESP32 envia telemetria a cada ciclo de despertar para o serviço central na VPS Oracle Cloud:

* **No Terminal (Local ou na VPS):**
  Basta digitar:
  ```bash
  calendario
  ```
  Abre uma interface gráfica em ASCII/TUI no próprio terminal com telemetria do dispositivo, histórico de ciclos, contagem regressiva para o próximo despertar e gerenciamento de arquivos OTA.
* **Teclas de Atalho no Terminal:**
  * `[r]` Recarregar dados
  * `[l]` Ver logs completos do último ciclo do ESP32
  * `[f]` Gerenciar Firmware OTA (ativação de binários para auto-update)
  * `[s]` Status do serviço de fundo systemd
  * `[q]` Sair

