# Intelbras Roteador Twibi Integração para Home Assistant

![image](https://brands.home-assistant.io/intelbras_twibi_router/logo.png)

Esse integração permite que você saiba quais dispositivos estão conectados na sua rede, podendo usar isso para saber quem está em casa ou não, além de outras informações sobre o roteador.

## Features

- Saiba se seus dispositivos estão online ou offline na sua rede
- Ative a localização de dispositivos apenas Wi-Fi ou todos os dispositivos
- Ligue ou desligue o Status LED que fica na frente do roteador
- Obtenha informações sobre o roteador como número serial ou versão do firmware, inclusive se tiver mais de um roteador na mesma rede

## Instalação

### HACS (Recomendado)

1. Tenha certeza que o [HACS](https://hacs.xyz/) está instalado no seu Home Assistant.
2. Adicione este repositório ao HACS como um "custom repository":
   - HACS > Integrations
   - Clique nos 3 pontos no canto superior direito da tela e selecione "Custom repositories"
   - Enter `https://github.com/chiconws/intelbras_twibi_router` no campo repositório
   - Selecione a categoria "Integration"
   - Clique em Add

3. Procure pelo Roteador Intelbras Twibi na HACS store e instale-o.
4. Reinicie o Home Assistant.

### Instalação Manual

1. Baixe o último release do [repositório](https://github.com/chiconws/intelbras_twibi_router).
2. Descompacte-o e copie a pasta `custom_components/intelbras_twibi_router` e cole na pasta `custom_components` no seu Home Assistant.
3. Reinicie o Home Assistant.

## Configuração

1. Vá a Configurações > Dispositivos & Serviços.
2. Clique em "+ ADICIONAR INTEGRAÇÃO".
3. Procure por "Roteador Intelbras Twibi" e selecione.
4. Siga os passos da configuração:
   - Endereço IP do Twibi (Padrão: 192.168.5.1, mas o seu pode ser diferente).
   - password (senha usada para acessar o aplicativo ou a WebUI do Twibi).
   - Apenas dispositivos conectados ao Wi-Fi (ignora dispositivos conectados ao Twibi através de cabos).
   - Intervalo de Atualização (em segundos) (intervalo de atualização das informações).
5. A integração vai procurar dispositivos conectados à rede e adicioná-los como `device` ao Home Assistant e também vai criar  `device_trackers`.

Se o dispositivo tiver nome cadastrado no Twibi (`celular` por exemplo), será criado um `device celular` e um `device_tracker.celular`. Caso não tenha nenhum nome, a integração usará o MAC Address para criar o `device` (`device 00:12:33:A7:90:AA` por exemplo) e o IP para criar o `device_tracker` (`device_tracker.device_192_168_5_123` por exemplo).
Você pode alterar todos esses nomes depois.

A integração também adicionará o próprio roteador Twibi como `device`. Você vai poder ver todos os `devices` conectados à ele e outras informações como número de serial, versão do firmware e ligar ou desligar o LED do roteador.
Caso tenha mais de um Twibi na sua rede, a integração criará um device para cada um. O que estiver conectado à internet via cabo será nomeado como "Primary" e os outros serão nomeados "Secondary". Os Twibi secundários têm um sensor de qualidade do link de Wi-Fi. O ícone desse sensor muda de acordo com a força do sinal.

## Informações adicionais

Essa é minha primeira integração, então com certeza haverão bugs. Se tiver algum problema, você pode [abrir um issue](https://github.com/chiconws/intelbras_twibi_router/issues) que talvez poderei ajudar.

Criei essa integração fazendo os testes no meu próprio roteador Twibi Fast, portanto, não garanto que vá funcionar com todos os outros modelos de Twibi no mercado. Caso você tenha outro modelo e queira adicioná-lo, [abra um issue](https://github.com/chiconws/intelbras_twibi_router/issues) para conversarmos.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
