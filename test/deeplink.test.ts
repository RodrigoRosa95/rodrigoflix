import { describe, expect, test } from "bun:test";
import {
  CHAVE_ITEM_PENDENTE,
  destinoDoLink,
  idDoLinkJellyfin,
  rotaDoItem,
} from "../deeplink/rodrigoflixDeepLink";

const ID = "0123456789abcdef0123456789abcdef";
const H = "https://jellyfin.example.com";

const memoria = (inicial: Record<string, string> = {}) => {
  const d: Record<string, string> = { ...inicial };
  return { d, getString: (k: string) => d[k], set: (k: string, v: string) => { d[k] = v; } };
};

describe("idDoLinkJellyfin", () => {
  test.each([
    [`${H}/app/item/${ID}`],
    [`${H}/app/item/${ID}/`],
    [`${H}/app/item/${ID.toUpperCase()}`],
    [`${H}/app/item/01234567-89ab-cdef-0123-456789abcdef`],
    [`${H}/app/item/${ID}?utm=wa`],
    [`http://jellyfin.example.com/app/item/${ID}`],
    [`${H}:443/app/item/${ID}`],
    [`${H}/web/#/details?id=${ID}`],
    [`${H}/web/#!/details?id=${ID}`],
    [`${H}/web/index.html#!/details?id=${ID}&serverId=abc`],
    [`${H}/web/index.html#/details?serverId=abc&id=${ID}`],
    [`rodrigoflix://item/${ID}`],
    [`rodrigoflix://app/item/${ID}`],
    [`  ${H}/app/item/${ID}  `],
  ])("reconhece %s", (url) => {
    expect(idDoLinkJellyfin(url)).toBe(ID);
  });

  test.each([
    [null], [undefined], [""], ["texto qualquer"],
    [`${H}/web/#/home`],
    [`${H}/web/index.html#!/home.html`],
    [`${H}/app`], [`${H}/app/apk`], [`${H}/app/sso?code=123`],
    [`${H}/app/item/123`],
    [`${H}/app/item/${ID}0`],
    [`${H}/app/item/${ID}/extra`],
    [`https://outro.com/app/item/${ID}`],
    [`https://jellyfin.example.com.malicioso.com/app/item/${ID}`],
    [`${H}/sso/OID/start/google`],
    [`rodrigoflix://login?apiUrl=${H}`],
    [`streamyfin://login?apiUrl=${H}`],
    [`${H}/web/#/details?id=xyz`],
  ])("ignora %s", (url) => {
    expect(idDoLinkJellyfin(url as any)).toBeNull();
  });
});

describe("destinoDoLink", () => {
  test("logado: vai direto para a página do item", () => {
    const m = memoria({ token: "abc" });
    expect(destinoDoLink(`${H}/app/item/${ID}`, m)).toBe(`/(auth)/(tabs)/(home)/items/page?id=${ID}`);
    expect(m.d[CHAVE_ITEM_PENDENTE]).toBeUndefined();
  });
  test("deslogado: guarda o item e vai para o início (login)", () => {
    const m = memoria();
    expect(destinoDoLink(`${H}/app/item/${ID}`, m)).toBe("/");
    expect(m.d[CHAVE_ITEM_PENDENTE]).toBe(ID);
  });
  test("outras URLs passam intactas (login do servidor, SSO etc.)", () => {
    const m = memoria({ token: "abc" });
    for (const u of [`rodrigoflix://login?apiUrl=${H}`, "/", "/login", `${H}/web/#/home`])
      expect(destinoDoLink(u, m)).toBe(u);
  });
  test("rota é a mesma usada pelo app ao tocar num item", () => {
    expect(rotaDoItem(ID)).toBe(`/(auth)/(tabs)/(home)/items/page?id=${ID}`);
  });
});
