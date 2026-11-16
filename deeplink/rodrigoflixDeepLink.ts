// RodrigoFlix: traduz links do Jellyfin (os que o bridge manda no WhatsApp) para rotas do app.
// Sem imports: é copiado para utils/ do Streamyfin e testado direto com `bun test` em este repositório.
//
// Formatos aceitos (id = 32 hex, com ou sem hífens de GUID):
//   https://jellyfin.example.com/app/item/ID          ← o que o bridge.js manda
//   https://jellyfin.example.com/web/#/details?id=ID
//   https://jellyfin.example.com/web/index.html#!/details?id=ID&serverId=...
//   rodrigoflix://item/ID  |  rodrigoflix://app/item/ID

export const HOST_RODRIGOFLIX = "jellyfin.example.com";
export const CHAVE_ITEM_PENDENTE = "rodrigoflix.itemPendente";

const HEX32 = /^[a-f0-9]{32}$/;

const normalizarId = (bruto: string | null | undefined): string | null => {
  if (!bruto) return null;
  let id = bruto;
  try {
    id = decodeURIComponent(bruto);
  } catch {
    // mantém o bruto
  }
  id = id.replace(/-/g, "").toLowerCase();
  return HEX32.test(id) ? id : null;
};

/** Devolve o id do item se a URL for um link de item do Jellyfin do RodrigoFlix; senão null. */
export function idDoLinkJellyfin(url: string | null | undefined): string | null {
  if (!url || typeof url !== "string") return null;
  const u = url.trim();

  // esquema próprio do app
  const proprio = u.match(/^rodrigoflix:\/\/(?:app\/)?item\/([^/?#]+)/i);
  if (proprio) return normalizarId(proprio[1]);

  const m = u.match(/^https?:\/\/([^/?#]+)(\/[^?#]*)?(\?[^#]*)?(#.*)?$/i);
  if (!m) return null;
  const host = m[1].toLowerCase().replace(/:\d+$/, "");
  if (host !== HOST_RODRIGOFLIX) return null;
  const caminho = m[2] || "/";
  const hash = m[4] || "";

  const app = caminho.match(/^\/app\/item\/([^/]+)\/?$/i);
  if (app) return normalizarId(app[1]);

  if (/^\/web(\/|\/index\.html)?$/i.test(caminho)) {
    const det = hash.match(/^#!?\/details\?(.*)$/i);
    if (!det) return null;
    const id = det[1]
      .split("&")
      .map((p) => p.split("="))
      .find(([k]) => k === "id");
    return id ? normalizarId(id[1]) : null;
  }
  return null;
}

/** Rota do expo-router da página do item (mesma usada pelo TouchableItemRouter). */
export const rotaDoItem = (id: string) => `/(auth)/(tabs)/(home)/items/page?id=${id}`;

export interface ArmazenamentoSimples {
  getString(chave: string): string | undefined;
  set(chave: string, valor: string): void;
}

/**
 * Decide para onde o app vai quando o Android entrega uma URL (abertura a frio ou com o app aberto).
 * - link de item + logado  → página do item
 * - link de item + deslogado → guarda o id e manda pro início (o login é exibido; depois abre o item)
 * - qualquer outra URL       → devolve igual (comportamento original do Streamyfin)
 */
export function destinoDoLink(path: string, armazenamento: ArmazenamentoSimples): string {
  const id = idDoLinkJellyfin(path);
  if (!id) return path;
  if (!armazenamento.getString("token")) {
    armazenamento.set(CHAVE_ITEM_PENDENTE, id);
    return "/";
  }
  return rotaDoItem(id);
}
