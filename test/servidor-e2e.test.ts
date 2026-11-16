// Teste de ponta a ponta do caminho do link do WhatsApp, contra o servidor de verdade (internet + túnel).
// Rodar: cd este repositório && bun test   (usa JELLYFIN_API_KEY do ~/.env para pegar um item real)
import { describe, expect, test } from "bun:test";
import { readFileSync, existsSync } from "fs";
import { execSync } from "child_process";
import { idDoLinkJellyfin, rotaDoItem, destinoDoLink } from "../deeplink/rodrigoflixDeepLink";

const H = "https://jellyfin.example.com";
const env = Object.fromEntries(
  readFileSync(`${process.env.HOME}/.env`, "utf8").split("\n")
    .filter((l) => /^[A-Z_]+=/.test(l)).map((l) => [l.split("=")[0], l.slice(l.indexOf("=") + 1).replace(/^["']|["']$/g, "")]),
);
const KEY = env.JELLYFIN_API_KEY;
const LOCAL = (env.JELLYFIN_URL || "http://127.0.0.1:8096").replace(/\/+$/, "");

async function itemReal(tipo: string): Promise<string> {
  const r = await fetch(`${LOCAL}/Items?IncludeItemTypes=${tipo}&Recursive=true&SortBy=DateCreated&SortOrder=Descending&Limit=1`, {
    headers: { "X-Emby-Token": KEY },
  });
  const j: any = await r.json();
  return j.Items[0].Id;
}

describe("link do WhatsApp → servidor", () => {
  for (const tipo of ["Movie", "Episode"]) {
    test(`${tipo} recente: /app/item/ID redireciona para a página do item no Jellyfin web`, async () => {
      const id = await itemReal(tipo);
      const link = `${H}/app/item/${id}`; // mesmo formato do bridge.js
      expect(idDoLinkJellyfin(link)).toBe(id);
      expect(destinoDoLink(link, { getString: () => "token", set: () => {} })).toBe(rotaDoItem(id));
      const r = await fetch(link, { redirect: "manual" });
      expect(r.status).toBe(302);
      const destino = r.headers.get("location")!;
      expect(destino).toBe(`${H}/web/index.html#!/details?id=${id}`);
      expect(idDoLinkJellyfin(destino)).toBe(id); // o app também entende o destino
      const pagina = await fetch(destino);
      expect(pagina.status).toBe(200);
    }, 30000);
  }

  test("id inválido é recusado", async () => {
    const r = await fetch(`${H}/app/item/naoexiste`, { redirect: "manual" });
    expect(r.status).toBe(400);
  });

  test("assetlinks.json publicado e com a mesma assinatura do APK (App Links verificados)", async () => {
    const r = await fetch(`${H}/.well-known/assetlinks.json`, { redirect: "manual" });
    expect(r.status).toBe(200);
    expect(r.headers.get("content-type")).toContain("application/json");
    const j: any = await r.json();
    const alvo = j.find((x: any) => x.target.package_name === "br.rodrigoflix.app");
    expect(alvo.relation).toContain("delegate_permission/common.handle_all_urls");
    for (const apk of ["RodrigoFlix.apk", "RodrigoFlix-teste.apk"]) {
      const caminho = `${process.env.HOME}/app-streamyfin/${apk}`;
      if (!existsSync(caminho)) continue;
      const sha = execSync(`apksigner verify --print-certs ${caminho} | grep 'SHA-256'`).toString().split(":").pop()!.trim();
      const formatado = sha.toUpperCase().match(/../g)!.join(":");
      expect(alvo.target.sha256_cert_fingerprints).toContain(formatado);
      const manifesto = execSync(`aapt dump xmltree ${caminho} AndroidManifest.xml`).toString();
      expect(manifesto).toContain('android:pathPrefix(0x0101002b)="/app/item/"');
      expect(manifesto).toContain('android:host(0x01010028)="jellyfin.example.com"');
    }
  }, 60000);
});
