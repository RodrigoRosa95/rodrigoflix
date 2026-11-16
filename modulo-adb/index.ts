import { Platform, requireNativeModule } from "expo-modules-core";

export interface TvDevice {
  ip: string;
  modelo: string;
}

export interface InstallResult {
  ok: boolean;
  msg?: string;
  erro?: string;
}

const AdbInstallerModule = (() => {
  if (Platform.OS !== "android") return null;
  try {
    return requireNativeModule("AdbInstaller");
  } catch {
    return null;
  }
})();

export async function getLocalSubnet(): Promise<string | null> {
  if (!AdbInstallerModule) return null;
  try {
    return await AdbInstallerModule.getLocalSubnet();
  } catch {
    return null;
  }
}

export async function scanTVs(subnetPrefix?: string): Promise<TvDevice[]> {
  if (!AdbInstallerModule) return [];
  try {
    const prefix = subnetPrefix || (await getLocalSubnet());
    if (!prefix) return [];
    return await AdbInstallerModule.scan(prefix);
  } catch (e) {
    console.error("[AdbInstaller] scan error:", e);
    return [];
  }
}

export async function installOnTV(
  ip: string,
  apkPath: string,
): Promise<InstallResult> {
  if (!AdbInstallerModule)
    return { ok: false, erro: "Só funciona em Android" };
  try {
    return await AdbInstallerModule.install(ip, apkPath);
  } catch (e: any) {
    return { ok: false, erro: e?.message || "Erro desconhecido" };
  }
}

export const isAdbInstallerAvailable = AdbInstallerModule !== null;
