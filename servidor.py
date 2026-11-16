#!/usr/bin/env python3
"""Página https://jellyfin.example.com/app — baixa o app RodrigoFlix e conecta no servidor.

Rotas:
  /app                    página com download do app e login
  /app/apk                envia o RodrigoFlix.apk
  /app/sso?code=123456    login com Google via Quick Connect
  /app/sso/pronto         fim do login
  /app/tv/scan            escaneia TVs Android na rede local (ADB)
  /app/tv/instalar        instala APK na TV via ADB
  /app/item/<id>          deep link: abre no app ou redireciona pro Jellyfin web
  /.well-known/assetlinks.json  Android App Links (valida o app para deep links)
  /web/index.html         Jellyfin web + script de Quick Connect
"""
import json
import os
import re
import socket
import subprocess
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORTA = 3012
JELLYFIN_LOCAL = 'http://127.0.0.1:8096'
PROVEDOR_SSO = 'Google'
VALIDADE_CODIGO_MS = 10 * 60 * 1000
SERVIDOR = os.environ.get('RODRIGOFLIX_SERVIDOR', 'https://jellyfin.example.com').rstrip('/')
PACOTE = 'br.rodrigoflix.app'
SHA256_CERT = os.environ.get('RODRIGOFLIX_SHA256', '')  # impressão digital do certificado que assina o APK (assetlinks.json)
APK_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'RodrigoFlix.apk')

ASSETLINKS = json.dumps([{
    'relation': ['delegate_permission/common.handle_all_urls'],
    'target': {
        'namespace': 'android_app',
        'package_name': PACOTE,
        'sha256_cert_fingerprints': [SHA256_CERT],
    },
}])
REDE_LOCAL = os.environ.get('REDE_LOCAL', '192.168.')
ADB_PORTA = 5555
ADB_SCAN_TIMEOUT = 0.4


def _adb(args, timeout=60):
    return subprocess.run(['adb'] + args, capture_output=True, text=True, timeout=timeout)


def scan_tvs():
    """Escaneia a rede local por dispositivos com ADB aberto (porta 5555)."""
    encontrados = []
    def testar(ip):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(ADB_SCAN_TIMEOUT)
            if s.connect_ex((ip, ADB_PORTA)) == 0:
                encontrados.append(ip)
            s.close()
        except Exception:
            pass
    threads = []
    for i in range(1, 255):
        ip = REDE_LOCAL + str(i)
        t = threading.Thread(target=testar, args=(ip,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=2)
    resultado = []
    for ip in sorted(encontrados):
        alvo = f'{ip}:{ADB_PORTA}'
        _adb(['connect', alvo], timeout=10)
        r = _adb(['shell', '-s', alvo, 'getprop', 'ro.product.model'], timeout=10)
        # tenta de novo com -s IP:porta explícito se não veio nada
        modelo = r.stdout.strip()
        if not modelo:
            r = _adb(['-s', alvo, 'shell', 'getprop', 'ro.product.model'], timeout=10)
            modelo = r.stdout.strip()
        resultado.append({'ip': ip, 'modelo': modelo or 'Android'})
    return resultado


def instalar_tv(ip):
    """Conecta via ADB e instala o APK. Retorna (ok, mensagem)."""
    if not re.match(r'^192\.168\.\d{1,3}\.\d{1,3}$', ip):
        return False, 'IP inválido'
    if not os.path.isfile(APK_LOCAL):
        return False, 'APK não encontrado no servidor'
    alvo = f'{ip}:{ADB_PORTA}'
    r = _adb(['connect', alvo], timeout=15)
    if 'connected' not in r.stdout.lower() and 'already' not in r.stdout.lower():
        return False, f'Não consegui conectar em {ip} — a TV precisa estar com depuração ADB pela rede ativada'
    r = _adb(['-s', alvo, 'install', '-r', APK_LOCAL], timeout=300)
    if r.returncode == 0 and 'success' in r.stdout.lower():
        return True, f'RodrigoFlix instalado com sucesso em {ip}'
    erro = (r.stdout + r.stderr).strip().split('\n')[-1]
    return False, f'Falha na instalação: {erro}'


def pagina():
    q = urllib.parse.quote(SERVIDOR, safe='')
    esquema = f'rodrigoflix://login?apiUrl={q}'
    intent = (f'intent://login?apiUrl={q}#Intent;scheme=rodrigoflix;package={PACOTE};'
              f'S.browser_fallback_url={urllib.parse.quote(SERVIDOR + "/app/apk", safe="")};end')
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>RodrigoFlix</title>
<style>
:root{{--fundo:#101418;--cartao:#1b2128;--texto:#eef2f5;--suave:#9aa7b2;--destaque:#00a4dc;--google:#4285F4;--verde:#16a34a}}
body{{margin:0;background:var(--fundo);color:var(--texto);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:460px;margin:0 auto;padding:28px 16px}}
h1{{font-size:1.5rem;margin:0 0 4px}} p{{color:var(--suave);margin:0 0 20px}}
.passo{{background:var(--cartao);border-radius:14px;padding:16px;margin-bottom:14px}}
.passo b{{display:block;margin-bottom:10px}}
a.botao,.botao{{display:block;text-align:center;background:var(--destaque);color:#fff;text-decoration:none;
font-weight:600;padding:14px;border-radius:10px;width:100%;box-sizing:border-box;cursor:pointer;border:none;font:inherit}}
.secundario{{background:transparent;border:1px solid var(--suave);color:var(--texto)}}
small{{color:var(--suave);display:block;margin-top:8px}}
.oculto{{display:none}}
.url-box{{background:var(--fundo);border:1px solid var(--suave);border-radius:8px;padding:12px;
margin-top:8px;text-align:center;font-size:1.05rem;word-break:break-all;user-select:all;letter-spacing:.3px}}
.metodo{{background:var(--fundo);border-radius:8px;padding:12px;margin-top:8px}}
.metodo b{{font-size:.95rem;display:block;margin-bottom:4px}}
.metodo ol{{margin:4px 0 0;padding-left:20px;color:var(--suave);font-size:.9rem}}
.metodo ol li{{margin-bottom:2px}}
#tv-area{{margin-top:8px}}
.botao:disabled{{opacity:.5;cursor:wait}}
.tv-item{{display:flex;align-items:center;justify-content:space-between;background:var(--fundo);
border-radius:8px;padding:10px 12px;margin-top:8px}}
.tv-item span{{font-size:.95rem}}
.tv-item .botao{{width:auto;padding:8px 16px;font-size:.85rem}}
.msg{{padding:10px;border-radius:8px;margin-top:8px;font-size:.9rem;text-align:center}}
.msg.ok{{background:#14532d;color:#86efac}} .msg.erro{{background:#7f1d1d;color:#fca5a5}}
.abas{{display:flex;gap:6px;margin-bottom:10px}}
.aba{{flex:1;text-align:center;padding:8px 4px;border-radius:8px;font-size:.85rem;cursor:pointer;
background:var(--fundo);color:var(--suave);border:1px solid transparent}}
.aba.ativa{{background:var(--destaque);color:#fff;border-color:var(--destaque)}}
</style></head><body><main>

<!-- ===== MODO TV: aparece se detectar Android TV / TV Box ===== -->
<div id="modo-tv" class="oculto">
<h1>📺 RodrigoFlix na TV</h1>
<p>Instale o app e assista direto na sua TV.</p>
<div class="passo"><b>1. Baixe e instale</b>
<a class="botao" href="/app/apk">⬇️ Baixar RodrigoFlix</a>
<small>Depois de baixar, abra o arquivo e toque em <b style="display:inline">Instalar</b>.</small></div>
<div class="passo"><b>2. Abra o app e entre na sua conta</b>
<small>Use seu <b style="display:inline">usuário e senha</b> do Jellyfin ou <b style="display:inline">Entrar com Google</b>.</small></div>
</div>

<!-- ===== MODO CELULAR: aparece por padrão ===== -->
<div id="modo-cel">
<h1>🎬 RodrigoFlix</h1>
<p>Assista e baixe séries e filmes para ver sem internet.</p>
<div class="passo"><b>1. Instale o app</b>
<a class="botao secundario" id="baixar" href="/app/apk">⬇️ Baixar o app (Android)</a>
<small>Se pedir, permita "instalar apps desconhecidos".</small></div>
<div class="passo"><b>2. Entre na sua conta</b>
<a class="botao" id="abrir" href="{esquema}">▶️ Abrir o app</a>
<small>Entre com <b style="display:inline">Google</b> ou com <b style="display:inline">usuário e senha</b> do Jellyfin.</small></div>

<div class="passo"><b>📺 Também na TV Android / TV Box</b>
<div class="abas">
<div class="aba ativa" onclick="abaTV(0)">Na TV</div>
<div class="aba" onclick="abaTV(1)">Pelo celular</div>
<div class="aba oculto" id="aba-adb" onclick="abaTV(2)">Automático</div>
</div>

<div id="tv-tab-0">
<div class="metodo"><b>Abra na sua TV:</b>
<div class="url-box" id="url-tv">{SERVIDOR}/app</div>
<small style="margin-top:6px">No navegador da TV (Chrome, Silk, Puffin) ou no app <b style="display:inline">Downloader</b> (grátis na Play Store).</small>
<ol>
<li>Na TV, abra o navegador ou o Downloader</li>
<li>Digite o endereço acima</li>
<li>A TV mostra esta mesma página — toque em <b style="display:inline">Baixar</b> e depois <b style="display:inline">Instalar</b></li>
<li>Abra o app e entre na sua conta</li>
</ol></div>
</div>

<div id="tv-tab-1" class="oculto">
<div class="metodo"><b>Envie do celular para a TV:</b>
<ol>
<li>No celular, toque em <b style="display:inline">Baixar o app</b> acima e salve o APK</li>
<li>Instale o app gratuito <b style="display:inline">Send Files to TV</b> no celular E na TV (Play Store)</li>
<li>Na TV, abra o Send Files to TV e toque em <b style="display:inline">Receber</b></li>
<li>No celular, abra o Send Files to TV, toque em <b style="display:inline">Enviar</b> e escolha o APK baixado</li>
<li>Na TV, abra o arquivo recebido e instale</li>
</ol></div>
</div>

<div id="tv-tab-2" class="oculto">
<small>Procura TVs na sua rede Wi-Fi e instala direto.</small>
<div id="tv-area">
<button class="botao secundario" id="btn-scan" onclick="scanTVs()">🔍 Procurar TVs na rede</button>
</div>
<small>A TV precisa estar com <b style="display:inline">Depuração USB pela rede</b> ativada (Configurações → Opções do desenvolvedor).</small>
</div>

</div><!-- fim passo TV -->
</div><!-- fim modo-cel -->

</main><script>
var ua = navigator.userAgent;
var ehTV = /Android/i.test(ua) && (/TV|AFT|BRAVIA|Chromecast|SmartTV|MIBOX|Stick|GoogleTV/i.test(ua) || (screen.width > 960 && !('ontouchstart' in window)));
if (ehTV) {{ document.getElementById('modo-tv').classList.remove('oculto'); document.getElementById('modo-cel').classList.add('oculto'); }}
if (/android/i.test(ua) && !ehTV) document.getElementById('abrir').href = {json.dumps(intent)};

function abaTV(n) {{
  for (var i = 0; i < 3; i++) {{
    var tab = document.getElementById('tv-tab-' + i);
    var aba = document.querySelectorAll('.aba');
    if (tab) tab.classList.toggle('oculto', i !== n);
    if (aba[i]) aba[i].classList.toggle('ativa', i === n);
  }}
}}

// testa se a rede local está disponível (scan funciona) e mostra a aba Automático
fetch('/app/tv/scan', {{method:'POST'}}).then(r => r.json()).then(d => {{
  if (!d.erro) document.getElementById('aba-adb').classList.remove('oculto');
}}).catch(function(){{}});

function scanTVs() {{
  var btn = document.getElementById('btn-scan'), area = document.getElementById('tv-area');
  btn.disabled = true; btn.textContent = '🔍 Procurando…';
  fetch('/app/tv/scan', {{method:'POST'}}).then(r => r.json()).then(d => {{
    btn.disabled = false; btn.textContent = '🔍 Procurar TVs na rede';
    if (!d.tvs || !d.tvs.length) {{ area.innerHTML = btn.outerHTML + '<div class="msg erro">Nenhuma TV encontrada na rede.</div>'; reativarScan(); return; }}
    var h = btn.outerHTML;
    d.tvs.forEach(function(tv) {{
      h += '<div class="tv-item"><span>📺 ' + tv.modelo + '<br><small style="color:var(--suave)">' + tv.ip + '</small></span>'
        + '<button class="botao" onclick="instalarTV(\'' + tv.ip + '\',this)">Instalar</button></div>';
    }});
    area.innerHTML = h;
    reativarScan();
  }}).catch(function() {{ btn.disabled = false; btn.textContent = '🔍 Procurar TVs na rede'; }});
}}
function reativarScan() {{ var b = document.getElementById('btn-scan'); if (b) b.onclick = scanTVs; }}
function instalarTV(ip, btn) {{
  btn.disabled = true; var txt = btn.textContent; btn.textContent = 'Instalando…';
  fetch('/app/tv/instalar', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{ip:ip}})}})
    .then(r => r.json()).then(d => {{
      btn.disabled = false;
      if (d.ok) {{ btn.textContent = '✅ Instalado!'; btn.style.background = 'var(--verde)'; }}
      else {{ btn.textContent = txt; var p = btn.parentElement; p.innerHTML += '<div class="msg erro">' + (d.erro||'Erro') + '</div>'; }}
    }}).catch(function() {{ btn.disabled = false; btn.textContent = txt; }});
}}
</script></body></html>'''


def pagina_simples(titulo, texto):
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{titulo}</title>
<style>:root{{--fundo:#101418;--texto:#eef2f5;--suave:#9aa7b2}}
body{{margin:0;background:var(--fundo);color:var(--texto);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:460px;margin:0 auto;padding:40px 16px;text-align:center}} p{{color:var(--suave)}}</style>
</head><body><main>{texto}</main></body></html>'''


def pagina_sso():
    """Guarda o código do Quick Connect (só 6 dígitos) por 10 min e vai para o login do Google."""
    return pagina_simples('Entrando com Google', f'''<h1>🔐 Entrando com Google…</h1>
<p id="msg">Aguarde, abrindo o login do Google.</p>
<script>
var c = new URLSearchParams(location.search).get('code') || '';
if (/^\\d{{6}}$/.test(c)) {{
  localStorage.setItem('rf_qc_code', c);
  localStorage.setItem('rf_qc_ate', String(Date.now() + {VALIDADE_CODIGO_MS}));
  location.replace('/sso/OID/start/{PROVEDOR_SSO}');
}} else {{
  document.getElementById('msg').textContent = 'Link inválido. Volte ao app e toque de novo em Entrar com Google.';
}}
</script>''')


def pagina_pronto(erro):
    if erro:
        return pagina_simples('Não deu certo', f'''<h1>⚠️ Não deu certo</h1>
<p>O servidor recusou a autorização (código {erro}). Volte ao app e toque de novo em <b>Entrar com Google</b>.</p>''')
    return pagina_simples('Pronto', '''<h1>✅ Pronto!</h1>
<p>Sua conta Google foi confirmada. Pode voltar ao app — ele entra sozinho em alguns segundos.</p>''')


# Roda dentro do Jellyfin web: só age se /app/sso guardou um código há menos de 10 min e já existe a chave do login
SCRIPT_SSO = '''<script>(function () {
  if (window.top !== window) return;               // o plugin SSO carrega /web/index.html num iframe antes de ter a chave
  var c = localStorage.getItem('rf_qc_code'), ate = +localStorage.getItem('rf_qc_ate') || 0;
  if (!c) return;
  if (Date.now() > ate) { localStorage.removeItem('rf_qc_code'); return; }
  var s = ((JSON.parse(localStorage.getItem('jellyfin_credentials') || '{}').Servers) || [])[0];
  if (!s || !s.AccessToken) return;
  localStorage.removeItem('rf_qc_code');
  fetch('/QuickConnect/Authorize?code=' + encodeURIComponent(c), {method: 'POST',
        headers: {'Authorization': 'MediaBrowser Token="' + s.AccessToken + '"'}})
    .then(function (r) { location.replace('/app/sso/pronto' + (r.ok ? '' : '?erro=' + r.status)); })
    .catch(function () { location.replace('/app/sso/pronto?erro=rede'); });
})();</script>'''


def index_jellyfin():
    """/web/index.html do Jellyfin com o SCRIPT_SSO antes do </head>; None se o Jellyfin não responder."""
    try:
        req = urllib.request.Request(JELLYFIN_LOCAL + '/web/index.html', headers={'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8')
    except Exception:
        return None
    return html.replace('</head>', SCRIPT_SSO + '</head>', 1)


class Pedido(BaseHTTPRequestHandler):
    def responder(self, corpo, tipo='text/html; charset=utf-8', status=200):
        corpo = corpo.encode()
        self.send_response(status)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(corpo)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(corpo)

    def responder_json(self, obj, status=200):
        corpo = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(corpo)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(corpo)

    def _eh_local(self):
        """True se o request veio da rede local (não pelo túnel Cloudflare)."""
        if self.headers.get('CF-Connecting-IP') or self.headers.get('X-Forwarded-For'):
            return False
        ip = self.client_address[0]
        return ip.startswith('192.168.') or ip.startswith('10.') or ip == '127.0.0.1'

    def do_POST(self):
        caminho = self.path.split('?', 1)[0].rstrip('/')
        if caminho == '/app/tv/scan':
            if not self._eh_local():
                self.responder_json({'tvs': [], 'erro': 'Só funciona na rede local'})
                return
            tvs = scan_tvs()
            self.responder_json({'tvs': tvs})
        elif caminho == '/app/tv/instalar':
            try:
                corpo = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            except Exception:
                self.responder_json({'ok': False, 'erro': 'JSON inválido'}, 400)
                return
            if not self._eh_local():
                self.responder_json({'ok': False, 'erro': 'Só funciona na rede local'})
                return
            ip = str(corpo.get('ip', '')).strip()
            ok, msg = instalar_tv(ip)
            self.responder_json({'ok': ok, 'erro': '' if ok else msg, 'msg': msg if ok else ''})
        else:
            self.send_error(404)

    def do_GET(self):
        caminho = self.path.split('?', 1)[0].rstrip('/')
        if caminho == '/app':
            corpo = pagina().encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        elif caminho == '/app/sso':
            self.responder(pagina_sso())
        elif caminho == '/app/sso/pronto':
            erro = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('erro', [''])[0]
            self.responder(pagina_pronto(re.sub(r'[^0-9a-z]', '', erro)[:8]))
        elif caminho == '/web/index.html':
            html = index_jellyfin()
            if html is None:
                self.send_error(502)
            else:
                self.responder(html)
        elif caminho == '/.well-known/assetlinks.json':
            corpo = ASSETLINKS.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(corpo)))
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            self.wfile.write(corpo)
        elif caminho.startswith('/app/item/'):
            item_id = caminho.split('/app/item/', 1)[1].split('/')[0]
            if not re.match(r'^[a-f0-9]{32}$', item_id):
                self.send_error(400)
                return
            self.send_response(302)
            self.send_header('Location', f'{SERVIDOR}/web/index.html#!/details?id={item_id}')
            self.end_headers()
        elif caminho == '/app/apk':
            if not os.path.isfile(APK_LOCAL):
                self.send_error(404, 'APK não encontrado')
                return
            tamanho = os.path.getsize(APK_LOCAL)
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.android.package-archive')
            self.send_header('Content-Length', str(tamanho))
            self.send_header('Content-Disposition', 'attachment; filename="RodrigoFlix.apk"')
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            with open(APK_LOCAL, 'rb') as f:
                while bloco := f.read(1024 * 1024):
                    self.wfile.write(bloco)
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', PORTA), Pedido).serve_forever()
