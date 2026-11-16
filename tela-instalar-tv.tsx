// RodrigoFlix: tela "Instalar na TV" — escaneia TVs Android na rede local e instala o APK via ADB.
import { File, Paths } from "expo-file-system";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  TouchableOpacity,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "@/components/common/Text";
import { SERVIDOR_PADRAO } from "@/constants/RodrigoFlix";
import {
  type InstallResult,
  type TvDevice,
  isAdbInstallerAvailable,
  scanTVs,
  installOnTV,
} from "@/modules/adb-installer";

const APK_URL = `${SERVIDOR_PADRAO}/app/apk`;
const APK_NAME = "RodrigoFlix.apk";

type Status = "idle" | "scanning" | "downloading" | "installing";

export default function InstalarNaTV() {
  const insets = useSafeAreaInsets();
  const [status, setStatus] = useState<Status>("idle");
  const [tvs, setTvs] = useState<TvDevice[]>([]);
  const [progresso, setProgresso] = useState("");
  const [instalando, setInstalando] = useState<string | null>(null);
  const [instalados, setInstalados] = useState<Set<string>>(new Set());

  const scan = useCallback(async () => {
    setStatus("scanning");
    setProgresso("Procurando TVs na rede Wi-Fi…");
    try {
      const resultado = await scanTVs();
      setTvs(resultado);
      if (resultado.length === 0) {
        setProgresso(
          "Nenhuma TV encontrada. Verifique se a TV está com depuração ADB pela rede ativada.",
        );
      } else {
        setProgresso(`${resultado.length} TV(s) encontrada(s)`);
      }
    } catch (e: any) {
      setProgresso(`Erro: ${e?.message || "falha no scan"}`);
    }
    setStatus("idle");
  }, []);

  const baixarApk = useCallback(async (): Promise<string | null> => {
    setProgresso("Baixando APK do servidor…");
    try {
      const dest = new File(Paths.cache, APK_NAME);
      if (dest.exists && dest.size && dest.size > 50 * 1024 * 1024) {
        return dest.uri;
      }
      setProgresso("Baixando APK…");
      await File.downloadFileAsync(APK_URL, dest);
      if (dest.exists) return dest.uri;
      return null;
    } catch (e: any) {
      setProgresso(`Erro ao baixar: ${e?.message}`);
      return null;
    }
  }, []);

  const instalar = useCallback(
    async (tv: TvDevice) => {
      setInstalando(tv.ip);
      setStatus("downloading");

      const apkPath = await baixarApk();
      if (!apkPath) {
        setInstalando(null);
        setStatus("idle");
        return;
      }

      setStatus("installing");
      setProgresso(`Instalando em ${tv.modelo} (${tv.ip})…`);

      const result: InstallResult = await installOnTV(tv.ip, apkPath);
      setInstalando(null);
      setStatus("idle");

      if (result.ok) {
        setInstalados((prev) => new Set(prev).add(tv.ip));
        setProgresso(`✅ ${result.msg || "Instalado!"}`);
        Alert.alert("Pronto!", `RodrigoFlix instalado na ${tv.modelo}.`);
      } else {
        setProgresso(`❌ ${result.erro || "Falha na instalação"}`);
        Alert.alert("Erro", result.erro || "Não foi possível instalar.");
      }
    },
    [baixarApk],
  );

  if (!isAdbInstallerAvailable) {
    return (
      <View className="flex-1 items-center justify-center p-8">
        <Text className="text-center text-neutral-400">
          Instalação na TV não disponível neste dispositivo.
        </Text>
      </View>
    );
  }

  return (
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      contentContainerStyle={{
        paddingLeft: insets.left + 16,
        paddingRight: insets.right + 16,
        paddingTop: 16,
        paddingBottom: insets.bottom + 32,
      }}
    >
      <View className="mb-6">
        <Text className="text-2xl font-bold mb-1">📺 Instalar na TV</Text>
        <Text className="text-neutral-400">
          Encontra TVs Android e TV Boxes na sua rede Wi-Fi e instala o
          RodrigoFlix direto, sem pendrive.
        </Text>
      </View>

      <TouchableOpacity
        onPress={scan}
        disabled={status !== "idle"}
        className="flex-row items-center justify-center rounded-xl py-3 mb-4"
        style={{
          backgroundColor: status !== "idle" ? "#333" : "#00a4dc",
          opacity: status !== "idle" ? 0.6 : 1,
        }}
        activeOpacity={0.8}
      >
        {status === "scanning" ? (
          <ActivityIndicator color="#fff" style={{ marginRight: 8 }} />
        ) : (
          <Ionicons
            name="search"
            size={20}
            color="#fff"
            style={{ marginRight: 8 }}
          />
        )}
        <Text className="font-semibold text-white">
          {status === "scanning" ? "Procurando…" : "🔍 Procurar TVs na rede"}
        </Text>
      </TouchableOpacity>

      {progresso ? (
        <Text className="text-sm text-neutral-400 mb-4 text-center">
          {progresso}
        </Text>
      ) : null}

      {tvs.map((tv) => {
        const jaInstalou = instalados.has(tv.ip);
        const estaInstalando = instalando === tv.ip;
        return (
          <View
            key={tv.ip}
            className="flex-row items-center justify-between rounded-xl p-4 mb-3"
            style={{ backgroundColor: "#1b2128" }}
          >
            <View className="flex-1 mr-3">
              <Text className="font-bold">📺 {tv.modelo}</Text>
              <Text className="text-xs text-neutral-500">{tv.ip}</Text>
            </View>
            <TouchableOpacity
              onPress={() => instalar(tv)}
              disabled={estaInstalando || status === "downloading"}
              className="rounded-lg px-4 py-2"
              style={{
                backgroundColor: jaInstalou ? "#16a34a" : "#00a4dc",
                opacity: estaInstalando ? 0.5 : 1,
              }}
              activeOpacity={0.8}
            >
              {estaInstalando ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Text className="font-semibold text-white text-sm">
                  {jaInstalou ? "✅ Instalado" : "Instalar"}
                </Text>
              )}
            </TouchableOpacity>
          </View>
        );
      })}

      <View
        className="rounded-xl p-4 mt-2"
        style={{ backgroundColor: "#1b2128" }}
      >
        <Text className="text-sm text-neutral-400">
          💡 A TV precisa estar com{" "}
          <Text className="font-bold text-neutral-300">
            Depuração USB pela rede
          </Text>{" "}
          ativada. Vá em Configurações → Sobre → toque 7x no número da versão →
          volte → Opções do desenvolvedor → Depuração USB → Depuração pela rede.
        </Text>
      </View>
    </ScrollView>
  );
}
