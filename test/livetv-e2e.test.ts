// Ponta a ponta da TV ao vivo contra o servidor real, pela internet (túnel), com o perfil de verdade do app.
// Reproduz o defeito antigo e prova o caminho novo. Fecha tudo que abrir.
import { afterAll, describe, expect, test } from "bun:test";
import { readFileSync } from "fs";
import { pedidoPlaybackInfoAoVivo, urlAoVivo } from "../livetv/rodrigoflixLiveTv";

const H = "https://jellyfin.example.com";
const env = Object.fromEntries(readFileSync(`${process.env.HOME}/.env`, "utf8").split("\n")
  .filter((l) => /^[A-Z_]+=/.test(l)).map((l) => [l.split("=")[0], l.slice(l.indexOf("=") + 1).replace(/^["']|["']$/g, "")]));
const KEY = env.JELLYFIN_API_KEY;
const U = "620244e51a7d439892bcaa337b02e298";
const DEV = "teste-livetv-rodrigoflix";
// perfil do app (utils/profiles/native.ts): "hls" em direct play é o que fazia o servidor escolher o caminho quebrado
const PERFIL = {
  MaxStreamingBitrate: 20000000,
  DirectPlayProfiles: [{ Type: "Video", Container: "mp4,mkv,avi,mov,flv,ts,m2ts,webm,ogv,3gp,hls", VideoCodec: "h264,hevc", AudioCodec: "aac,mp3,ac3,eac3" }],
  TranscodingProfiles: [{ Type: "Video", Context: "Streaming", Protocol: "hls", Container: "ts", VideoCodec: "h264,hevc", AudioCodec: "aac,mp3,ac3", BreakOnNonKeyFrames: true }],
  CodecProfiles: [], SubtitleProfiles: [],
};
const abertos: { ls?: string; ps?: string }[] = [];
const hdr = { "X-Emby-Token": KEY, "Content-Type": "application/json" };

async function canal(nome: string) {
  const j: any = await (await fetch(`${H}/LiveTv/Channels?userId=${U}&Limit=500`, { headers: hdr })).json();
  const c = j.Items.find((x: any) => x.Name === nome);
  if (!c) throw new Error(`canal ${nome} não encontrado`);
  return c.Id as string;
}
async function playbackInfo(id: string, corpo: any) {
  const j: any = await (await fetch(`${H}/Items/${id}/PlaybackInfo?userId=${U}`, { method: "POST", headers: hdr, body: JSON.stringify(corpo) })).json();
  abertos.push({ ls: j.MediaSources?.[0]?.LiveStreamId, ps: j.PlaySessionId });
  return j;
}

afterAll(async () => {
  for (const a of abertos) {
    if (a.ps) await fetch(`${H}/Videos/ActiveEncodings?deviceId=${DEV}&playSessionId=${a.ps}`, { method: "DELETE", headers: hdr });
    if (a.ls) await fetch(`${H}/LiveStreams/Close?liveStreamId=${a.ls}`, { method: "POST", headers: hdr });
  }
}, 60000);

describe("TV ao vivo pela internet", () => {
  test("DEFEITO ANTIGO reproduzido: direct stream repassa a playlist da origem e as variantes dão 404", async () => {
    const id = await canal("Pluto TV Cine Sucessos");
    const j = await playbackInfo(id, { UserId: U, IsPlayback: true, AutoOpenLiveStream: true, DeviceProfile: PERFIL });
    const ms = j.MediaSources[0];
    expect(ms.Path).toContain("127.0.0.1"); // inalcançável do celular
    expect(ms.TranscodingUrl ?? null).toBeNull();
    const r = await fetch(`${H}/Videos/${id}/stream?static=true&container=hls&mediaSourceId=${ms.Id}&deviceId=${DEV}&ApiKey=${KEY}`);
    const m3u = await r.text();
    const variante = m3u.split("\n").find((l) => l && !l.startsWith("#"))!;
    expect(variante.startsWith("http")).toBe(false); // relativa
    expect((await fetch(`${H}/Videos/${id}/${variante}`)).status).toBe(404);
  }, 60000);

  for (const nome of ["Pluto TV Cine Sucessos", "SBT"]) {
    test(`CAMINHO NOVO: "${nome}" entrega vídeo H.264 pelo servidor`, async () => {
      const id = await canal(nome);
      const t0 = Date.now();
      const j = await playbackInfo(id, pedidoPlaybackInfoAoVivo({ userId: U, deviceProfile: PERFIL }));
      const ms = j.MediaSources[0];
      const url = urlAoVivo({ basePath: H, accessToken: KEY, deviceId: DEV, itemId: id, playSessionId: j.PlaySessionId, mediaSource: ms })!;
      expect(url).toStartWith(H);
      expect(url).toContain("LiveStreamId=");
      expect(url).not.toContain("127.0.0.1");
      const master = await (await fetch(url)).text();
      expect(master).toContain("#EXTM3U");
      const varUrl = new URL(master.split("\n").find((l) => l && !l.startsWith("#"))!, url).toString();
      expect(varUrl).toStartWith(H);
      let lista = "";
      for (let i = 0; i < 30 && !/\.(ts|mp4)/.test(lista); i++) {
        lista = await (await fetch(varUrl)).text();
        if (!/\.(ts|mp4)/.test(lista)) await Bun.sleep(1000);
      }
      const seg = new URL(lista.split("\n").find((l) => l && !l.startsWith("#"))!, varUrl).toString();
      const r = await fetch(seg);
      expect(r.status).toBe(200);
      const bytes = new Uint8Array(await r.arrayBuffer());
      expect(bytes.length).toBeGreaterThan(50_000);
      expect(bytes[0]).toBe(0x47); // MPEG-TS sync byte
      console.log(`  ${nome}: 1º segmento ${(bytes.length / 1024) | 0} KB em ${((Date.now() - t0) / 1000).toFixed(1)} s`);
    }, 90000);
  }
});
