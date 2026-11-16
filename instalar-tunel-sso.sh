#!/bin/bash
# Amplia a regra do túnel (29/10/2026): /app/* (página, APK, login Google) e /web/index.html (script do login Google)
# vão para a página do app (porta 3012); o resto do jellyfin.example.com continua no Jellyfin.
# Uso: pkexec este repositório/instalar-tunel-sso.sh
set -e
C=/etc/cloudflared/config.yml
grep -q 'web/index' "$C" && { echo "já instalado"; exit 0; }
cp "$C" "$C.bak-antes-app-sso"
python3 - "$C" <<'P'
import sys
c=sys.argv[1]; s=open(c).read()
velho='    path: ^/app(/apk)?/?$\n'
novo='    path: ^/(app(/.*)?|web/index\\.html)$\n'
assert velho in s, 'regra /app antiga não encontrada'
s=s.replace(velho, novo, 1).replace('só /app e /app/apk vão para a página', '/app/* e /web/index.html vão para a página', 1)
open(c,'w').write(s)
P
if ! /usr/local/bin/cloudflared tunnel --config "$C" ingress validate; then
  cp "$C.bak-antes-app-sso" "$C"; echo "config inválida — voltei o backup"; exit 1
fi
systemctl restart cloudflared
sleep 5
for u in /app /app/sso /web/index.html /web/; do curl -s -o /dev/null -w "teste $u: %{http_code}\n" "https://jellyfin.example.com$u"; done
curl -s https://jellyfin.example.com/web/index.html | grep -q rf_qc_code && echo "script do login Google: ativo"
