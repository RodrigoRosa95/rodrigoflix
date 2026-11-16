#!/bin/bash
# Compila o APK RodrigoFlix (Streamyfin modificado por aplicar_rodrigoflix.py). Precisa do preparar.sh antes.
# Saída: este repositório/RodrigoFlix.apk (servido em https://jellyfin.example.com/app/apk)
# A chave fica em ~/.config/rodrigoflix/ — sem ela as atualizações não instalam por cima.
set -e
B=${BUILD_DIR:-/mnt/4tb-raw/android-build}
export ANDROID_HOME=$B/sdk ANDROID_SDK_ROOT=$B/sdk GRADLE_USER_HOME=$B/gradle PATH=$HOME/.bun/bin:$PATH
export EXPO_TV=0 NODE_ENV=production SENTRY_DISABLE_AUTO_UPLOAD=true EXPO_NO_TELEMETRY=1
K=$HOME/.config/rodrigoflix
cd $B/streamyfin
echo "== $(date +%T) mudanças do RodrigoFlix"
python3 "$(dirname "$(readlink -f "$0")")"/aplicar_rodrigoflix.py .
echo "== $(date +%T) prebuild android"
bunx expo prebuild --platform android --no-install --clean 2>&1 | tail -5
echo "== $(date +%T) assinatura"
G=android/app/build.gradle
if ! grep -q 'signingConfigs.rodrigoflix' "$G"; then
  python3 - "$G" "$K" <<'P'
import sys,re
g,k=sys.argv[1],sys.argv[2]; s=open(g).read(); senha=open(k+'/senha').read().strip()
s=s.replace("    signingConfigs {\n", "    signingConfigs {\n        rodrigoflix {\n"
  f"            storeFile file('{k}/assinatura.jks')\n            storePassword '{senha}'\n"
  f"            keyAlias 'rodrigoflix'\n            keyPassword '{senha}'\n        }}\n", 1)
s=re.sub(r"(release \{[^}]*?)signingConfig signingConfigs\.debug", r"\1signingConfig signingConfigs.rodrigoflix", s, count=1, flags=re.S)
assert 'signingConfigs.rodrigoflix' in s, 'não achei o bloco release'
open(g,'w').write(s)
P
fi
# play-services-cast puxa mediarouter 1.9 beta, que exige compileSdk 37 e AGP 9.1.
G2=android/build.gradle
grep -q 'mediarouter:1.8.1' "$G2" || sed -i "s|^allprojects {|allprojects {\n  configurations.all { resolutionStrategy.force 'androidx.mediarouter:mediarouter:1.8.1', 'com.google.android.gms:play-services-cast-framework:21.5.0' }|" "$G2"
# cast-framework "+" pega a 23.0.0 (Kotlin metadata 2.4.0, incompatível com 2.1.x)
sed -i "s|castFrameworkVersion = \"+\"|castFrameworkVersion = \"21.5.0\"|" "$G2"
echo "== $(date +%T) gradle assembleRelease (demora)"
cd android && printf '\norg.gradle.jvmargs=-Xmx4g -XX:MaxMetaspaceSize=1g\norg.gradle.workers.max=3\nkotlin.daemon.jvmargs=-Xmx2g\n' >> gradle.properties
bash "$(dirname "$(readlink -f "$0")")"/gradle-apk.sh
