#!/bin/bash
# Põe /app e /app/apk do jellyfin.example.com na página do Streamyfin (porta 3012), antes da regra do Jellyfin.
# Uso: sudo este repositório/instalar-tunel.sh
set -e
C=/etc/cloudflared/config.yml
grep -q 'localhost:3012' "$C" && { echo "já instalado"; exit 0; }
cp "$C" "$C.bak-antes-app-streamyfin"
python3 - "$C" <<'P'
import sys
c=sys.argv[1]; s=open(c).read()
alvo='  - hostname: jellyfin.example.com\n    service: http://localhost:8096\n'
novo=('  # Página do app Streamyfin (29/10/2026): só /app e /app/apk vão para a página; o resto segue no Jellyfin\n'
      '  - hostname: jellyfin.example.com\n    path: ^/app(/apk)?/?$\n    service: http://localhost:3012\n')
assert alvo in s, 'regra do jellyfin não encontrada'
open(c,'w').write(s.replace(alvo, novo+alvo, 1))
P
if ! /usr/local/bin/cloudflared tunnel --config "$C" ingress validate; then
  cp "$C.bak-antes-app-streamyfin" "$C"; echo "config inválida — voltei o backup"; exit 1
fi
systemctl restart cloudflared
sleep 5
curl -s -o /dev/null -w "teste https: %{http_code}\n" https://jellyfin.example.com/app
