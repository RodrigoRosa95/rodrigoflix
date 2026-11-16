// RodrigoFlix: o expo-router passa por aqui TODA URL que abre o app (a frio e com o app aberto)
// antes de escolher a tela. Links de item do Jellyfin viram a página do item no app.
import { storage } from "@/utils/mmkv";
import { destinoDoLink } from "@/utils/rodrigoflixDeepLink";

export function redirectSystemPath({
  path,
}: {
  path: string;
  initial: boolean;
}): string {
  try {
    return destinoDoLink(path, storage);
  } catch (e) {
    console.error("RodrigoFlix deep link:", e);
    return path;
  }
}
