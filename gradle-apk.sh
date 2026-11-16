#!/bin/bash
# Só a etapa do Gradle (sem refazer o prebuild de 20 min). Roda em escopo com teto de memória:
# 30/10 a compilação sem limite + serviços levou o notebook a OOM e reboot.
B=${BUILD_DIR:-/mnt/4tb-raw/android-build}
export ANDROID_HOME=$B/sdk ANDROID_SDK_ROOT=$B/sdk GRADLE_USER_HOME=$B/gradle PATH=$HOME/.bun/bin:$PATH
export EXPO_TV=0 NODE_ENV=production SENTRY_DISABLE_AUTO_UPLOAD=true EXPO_NO_TELEMETRY=1
cd $B/streamyfin/android || exit 1
echo "== $(date +%T) gradle assembleRelease"
# 30/10 09:56 queda seca sem nada no log, com CPU em 91 °C: 2 núcleos físicos e congela o build a 95 °C até voltar a 80 °C.
(
  congelado=0
  while sleep 15; do
    t=$(sensors | awk '/Package id 0/{gsub(/[+°C]/,"",$4); print int($4)}')
    [ -n "$t" ] || continue
    if [ $congelado = 0 ] && [ "$t" -ge 95 ]; then
      systemctl --user freeze apk-gradle.scope && congelado=1 && echo "$(date +%T) congelado a $t °C" >> $B/temperatura.log
    elif [ $congelado = 1 ] && [ "$t" -le 80 ]; then
      systemctl --user thaw apk-gradle.scope && congelado=0 && echo "$(date +%T) retomado a $t °C" >> $B/temperatura.log
    fi
  done
) &
GUARDA=$!
systemd-run --user --scope --quiet --unit=apk-gradle -p MemoryHigh=6G -p MemoryMax=7G \
  taskset -c 2,3 nice -n 15 ./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a,armeabi-v7a --no-daemon > $B/gradle-completo.log 2>&1
kill $GUARDA
grep -E "BUILD|FAILURE|error:|What went wrong|> Task :app:assemble" $B/gradle-completo.log | tail -20
APK=$(ls -t app/build/outputs/apk/release/*.apk 2>/dev/null | head -1)
[ -n "$APK" ] || { echo "== $(date +%T) FALHOU: sem APK"; exit 1; }
cp "$APK" "$(dirname "$(readlink -f "$0")")/RodrigoFlix.apk"
echo "== $(date +%T) PRONTO: $(du -h "$(dirname "$(readlink -f "$0")")/RodrigoFlix.apk" | cut -f1)"
