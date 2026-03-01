# Integração Intelbras Twibi Router para Home Assistant

![image](https://brands.home-assistant.io/intelbras_twibi_router/logo.png)

Essa integração conecta o seu roteador mesh **Intelbras Twibi** ao Home Assistant, permitindo monitorar e controlar sua rede: saber quais dispositivos estão conectados, automatizar presença de pessoas, controlar LEDs, gerenciar a rede de convidados e muito mais.

---

## ✨ Funcionalidades

### 📊 Sensores

- Status da rede (conectado/desconectado)  
- Quantidade de dispositivos conectados  
- Velocidade de upload/download da internet (WAN)  
- Tempo de atividade do roteador (uptime)  
- Número de série  
- Qualidade do link (dBm) para roteadores secundários  
- Informações da LAN e da WAN  
- Versão do firmware e status de atualização  
- QR Code da rede WiFi principal  
- QR Code da rede de convidados  

### 🔌 Rastreadores de Dispositivos

- Detecção automática de todos os dispositivos conectados  
- Status de presença (em casa/fora)  
- Informações detalhadas (MAC, IP, 2.4GHz/5GHz/Ethernet)  
- Mantém estado de “ausente” mesmo após reinício do roteador  

### 💡 Luzes

- Controle do LED de status de cada roteador  

### 🔘 Botões

- Reiniciar roteadores remotamente  

### 🔄 Interruptores

- Ativar/desativar o WiFi de convidados  

---

## 🛠️ Instalação

### HACS (Recomendado)

1. Certifique-se de que o [HACS](https://hacs.xyz/) está instalado.  
2. No HACS, adicione este repositório como *Custom Repository*:  
   - HACS → Integrações → ⋮ → *Custom repositories*  
   - Cole: `https://github.com/chiconws/intelbras_twibi_router`  
   - Categoria: *Integration* → Add  
3. Procure por **Intelbras Twibi Router** na HACS store e instale.  
4. Reinicie o Home Assistant.  

### Instalação Manual

1. Baixe o último release no [GitHub](https://github.com/chiconws/intelbras_twibi_router).  
2. Extraia e copie a pasta `custom_components/intelbras_twibi_router` para dentro da pasta `custom_components` no Home Assistant.  
3. Reinicie o Home Assistant.  

---

## ⚙️ Configuração

1. Vá em **Configurações → Dispositivos & Serviços**.  
2. Clique em **+ Adicionar Integração**.  
3. Procure por **Intelbras Twibi Router**.  
4. Informe:  
   - **Endereço IP** (padrão: `192.168.5.1`)
   - **Usuário e Senha** (credenciais do administrador)
   - Se deseja rastrear apenas dispositivos Wi-Fi ou todos
   - Intervalo de atualização (segundos)

A integração criará automaticamente:

- Dispositivos (`device`) para cada Twibi detectado (Primary/Secondary)  
- Rastreadores (`device_tracker`) para cada dispositivo conectado  
- Sensores, luzes, botões e switches correspondentes  

Se um dispositivo tiver nome configurado no Twibi, ele será usado. Caso contrário, será usado o **MAC** ou o **IP**. Esses nomes podem ser alterados no Home Assistant.  

---

## 📡 Suporte a Múltiplos Roteadores

- Detecta automaticamente roteadores em rede mesh  
- Diferencia cada um pelo número de série (últimos 4 caracteres)  
- Roteadores secundários incluem sensor de qualidade do link

---

## 📱 WiFi QR Codes

- `sensor.wifi_qr_code` – Rede principal  
- `sensor.guest_wifi_qr_code` – Rede de convidados  

Use com cartões de exibição de QR Code para facilitar o acesso de visitantes.  

---

## 🔄 Reinício Automático do Roteador

- Detecta reinícios programados (ex: 03h30)  
- Aumenta tentativas de reconexão durante esse período  
- Mantém estados de dispositivos em cache para reduzir falhas  

---

## 🧩 Exemplos de Entidades

### Sensores

- `sensor.uptime_827q` – Uptime do roteador principal  
- `sensor.link_quality_7178` – Sinal do roteador secundário  
- `sensor.connected_devices` – Total de dispositivos conectados  

### Rastreadores

- `device_tracker.celular_jose` – Smartphone do José  
- `device_tracker.laptop_escritorio` – Notebook do escritório  

### Controles

- `light.status_led_827q` – LED do roteador principal  
- `switch.guest_network` – Ativar/desativar WiFi de convidados  
- `button.restart_router` – Reiniciar roteador  

---

## 🛠️ Solução de Problemas

- **Falha de autenticação** → Verifique usuário/senha  
- **Timeout de conexão** → Confirme o IP do roteador  
- **Entidades indisponíveis** → Aguarde alguns minutos (roteador pode estar reiniciando)  

Ative debug logs em `configuration.yaml`:  

```yaml
logger:
  logs:
    custom_components.intelbras_twibi_router: debug
