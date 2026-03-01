# Integração Intelbras Twibi Router para Home Assistant

[![HACS][badge-hacs]][link-hacs] [![GitHub Release][badge-release]][link-release] [![GitHub Commit Activity][badge-commit-activity]][link-commits] [![HACS Validation][badge-hacs-validation]][link-hacs-validation] [![Hassfest][badge-hassfest]][link-hassfest]

![Logo da integração](https://brands.home-assistant.io/intelbras_twibi_router/logo.png)

Integração local para roteadores **Intelbras Twibi** no Home Assistant.

Ela adiciona sensores do roteador, `device_trackers` para os dispositivos da rede e alguns controles úteis, como LED, reinício, rede de convidados e UPnP.

## Recursos

- Sensores de status e informações da rede
- `device_tracker` para presença dos dispositivos conectados
- Filtro para considerar apenas dispositivos Wi-Fi
- Seleção de quais dispositivos devem ser rastreados
- Controle do LED dos nós
- Botão para reiniciar o roteador principal
- Switches para rede de convidados e UPnP

## Instalação

### HACS

1. Adicione este repositório como repositório customizado no HACS:
   `https://github.com/chiconws/intelbras_twibi_router`
2. Selecione a categoria `Integration`.
3. Instale a integração e reinicie o Home Assistant.

### Manual

1. Copie a pasta `custom_components/intelbras_twibi_router` para `custom_components`.
2. Reinicie o Home Assistant.

## Configuração

1. Vá em `Configurações > Dispositivos e Serviços`.
2. Adicione a integração `Roteador Intelbras Twibi`.
3. Informe IP, senha e intervalo de atualização.
4. Escolha se deseja listar apenas dispositivos conectados ao Wi-Fi.
5. Selecione quais dispositivos deseja rastrear.

Se nenhum dispositivo for selecionado na configuração inicial, a integração assume rastreamento de todos os dispositivos disponíveis.

## Problemas comuns

- Nenhum dispositivo para selecionar: desmarque `Apenas dispositivos conectados ao Wi-Fi` e confirme se há clientes conectados.
- Falha de autenticação: confirme o IP do nó principal e a senha da interface do roteador.
- Entidades indisponíveis: aguarde alguns instantes caso o roteador tenha reiniciado.

## Debug

```yaml
logger:
  logs:
    custom_components.intelbras_twibi_router: debug
```

[badge-hacs]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[badge-release]: https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Fchiconws%2Fintelbras_twibi_router%2Freleases%2Flatest&query=%24.tag_name&label=release
[badge-commit-activity]: https://img.shields.io/github/commit-activity/m/chiconws/intelbras_twibi_router
[badge-hacs-validation]: https://github.com/chiconws/intelbras_twibi_router/actions/workflows/hacs.yaml/badge.svg
[badge-hassfest]: https://github.com/chiconws/intelbras_twibi_router/actions/workflows/hassfest.yaml/badge.svg
[link-hacs]: https://github.com/custom-components/hacs
[link-release]: https://github.com/chiconws/intelbras_twibi_router/releases/latest
[link-commits]: https://github.com/chiconws/intelbras_twibi_router/commits/main
[link-hacs-validation]: https://github.com/chiconws/intelbras_twibi_router/actions/workflows/hacs.yaml
[link-hassfest]: https://github.com/chiconws/intelbras_twibi_router/actions/workflows/hassfest.yaml
