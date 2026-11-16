# RodrigoFlix

Versão personalizada do [Streamyfin](https://github.com/streamyfin/streamyfin) (cliente Jellyfin para Android) usada no servidor de mídia caseiro **RodrigoFlix**. Não é um fork completo: é um conjunto de **mudanças aplicadas por script** sobre o código oficial do Streamyfin, mais uma página de instalação e os testes.

## O que muda em relação ao Streamyfin
- **Marca e instalação ao lado do original:** nome "RodrigoFlix", pacote `br.rodrigoflix.app` e esquema `rodrigoflix://`.
- **Servidor embutido:** o app abre já na tela de usuário e senha do **seu** servidor (`RODRIGOFLIX_SERVIDOR`).
- **Entrar com Google:** botão que gera um código de Quick Connect e abre `/app/sso?code=…` no navegador. A página do servidor (`servidor.py`) faz o login no plugin SSO do Jellyfin e autoriza o código, e o app entra sozinho.
- **Sessão mais estável:** um 401 passageiro do Jellyfin (item sendo atualizado) deixou de apagar a sessão. O app só sai da conta se `/Users/Me` também recusar a chave.
- **Deep link:** links `https://SEU-SERVIDOR/app/item/ID` (como os enviados por bots de WhatsApp) abrem a página do item no app, com App Links verificados. Sem login, o item fica guardado e abre depois de entrar.
- **TV ao vivo:** aba Canais com busca e "Agora: programa". No guia, o programa no ar abre o canal. A reprodução usa remux HLS (`/videos/ID/master.m3u8`) em vez do caminho interno da origem, o que corrige canais que giravam sem fim.
- **Instalação na TV:** `tela-instalar-tv.tsx` mostra o endereço para instalar o APK na TV/box.
- **Módulo ADB** (`modulo-adb/`): módulo nativo Expo para ações via ADB.

## Estrutura
| Caminho | Função |
|---|---|
| `aplicar_rodrigoflix.py` | Aplica todas as mudanças numa cópia do Streamyfin. Pode rodar de novo (cada troca confere se já foi feita). |
| `deeplink/` | Roteamento de links `/app/item/ID` (`+native-intent.tsx` e lógica testável). |
| `livetv/` | Lógica de TV ao vivo (URL de stream, remux). |
| `modulo-adb/` | Módulo nativo Expo. |
| `servidor.py` | Página `/app` (porta 3012): detecta o Android, abre o app ou baixa o APK, SSO com Google, `assetlinks.json`, redireciona `/app/item/ID`. |
| `compilar.sh`, `gradle-apk.sh` | Prebuild, assinatura e `assembleRelease`, com limite de núcleos e de temperatura. |
| `instalar-tunel*.sh` | Regras do Cloudflare Tunnel para expor `/app` na frente do Jellyfin. |
| `test/` | Testes (`bun test`): deep link, TV ao vivo e servidor. |

## Como usar
1. Clone o Streamyfin oficial e prepare o ambiente Android (SDK, NDK, bun). O build completo usa vários GB.
2. Aplique as mudanças:
   ```bash
   export RODRIGOFLIX_SERVIDOR=https://jellyfin.seudominio.com
   python3 aplicar_rodrigoflix.py /caminho/para/streamyfin
   ```
3. Crie sua chave de assinatura em `~/.config/rodrigoflix/` (`assinatura.jks` e um arquivo `senha`) e rode `BUILD_DIR=/pasta/de/build ./compilar.sh`. **Guarde a chave:** sem ela as atualizações não instalam por cima.
4. Suba a página do app:
   ```bash
   RODRIGOFLIX_SERVIDOR=https://jellyfin.seudominio.com RODRIGOFLIX_SHA256=<impressão do certificado> python3 servidor.py
   ```
   Depois publique `/app` pelo seu proxy ou túnel (`instalar-tunel.sh` é um exemplo para Cloudflare Tunnel).
5. Testes: `bun test`.

## Variáveis
| Variável | Uso |
|---|---|
| `RODRIGOFLIX_SERVIDOR` | URL do seu Jellyfin (embutida no app e usada pela página). |
| `RODRIGOFLIX_SHA256` | SHA-256 do certificado de assinatura (para o `assetlinks.json`). |
| `REDE_LOCAL` | Prefixo da rede local (padrão `192.168.`) que a página trata como rede de casa. |
| `BUILD_DIR` | Pasta de build do Android (`compilar.sh`). |

## Limites
- Os scripts de build foram escritos para o servidor do autor (caminhos como `/mnt/4tb-raw/android-build` são configuráveis por `BUILD_DIR`). Ajuste ao seu ambiente.
- A reprodução ao vivo foi validada por testes automatizados. Em TV box ARMv7 o player do app não reproduziu.
- Esta versão pública não foi reaplicada sobre uma cópia limpa do Streamyfin depois da troca do domínio por variável de ambiente. Rode `aplicar_rodrigoflix.py` primeiro e confira antes de compilar.
- O APK não é distribuído aqui, porque é assinado com a chave do autor.

## Licença
O Streamyfin é **MPL-2.0**, e os arquivos alterados precisam ficar com o código disponível. Os arquivos deste repositório também são distribuídos sob **MPL-2.0** (veja `LICENSE`).
