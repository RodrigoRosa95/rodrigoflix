import { describe, expect, test } from "bun:test";
import { canalDoItem, ehAoVivo, pedidoPlaybackInfoAoVivo, urlAoVivo } from "../livetv/rodrigoflixLiveTv";

const base = { basePath: "https://jellyfin.example.com", accessToken: "TOK", deviceId: "DEV", itemId: "CANAL" };

describe("ehAoVivo / canalDoItem", () => {
  test("canal e programa são ao vivo; filme e episódio não", () => {
    expect(ehAoVivo({ Type: "TvChannel" })).toBe(true);
    expect(ehAoVivo({ Type: "Program" })).toBe(true);
    expect(ehAoVivo({ Type: "Movie" })).toBe(false);
    expect(ehAoVivo({ Type: "Episode" })).toBe(false);
    expect(ehAoVivo(null)).toBe(false);
  });
  test("programa toca o canal dele", () => {
    expect(canalDoItem({ Type: "Program", Id: "P", ChannelId: "C" })).toBe("C");
    expect(canalDoItem({ Type: "TvChannel", Id: "C" })).toBe("C");
    expect(canalDoItem({ Type: "Program", Id: "P" })).toBeNull();
  });
});

describe("pedidoPlaybackInfoAoVivo", () => {
  test("desliga direct play e direct stream e abre o canal (último passo do app oficial)", () => {
    const p = pedidoPlaybackInfoAoVivo({ userId: "U", deviceProfile: { x: 1 }, maxStreamingBitrate: 8e6 });
    expect(p).toMatchObject({ enableDirectPlay: false, enableDirectStream: false, autoOpenLiveStream: true, isPlayback: true, userId: "U", startTimeTicks: 0 });
  });
});

describe("urlAoVivo", () => {
  test("usa a TranscodingUrl do servidor (remux HLS)", () => {
    expect(urlAoVivo({ ...base, mediaSource: { TranscodingUrl: "/videos/CANAL/master.m3u8?LiveStreamId=L" } }))
      .toBe("https://jellyfin.example.com/videos/CANAL/master.m3u8?LiveStreamId=L");
    expect(urlAoVivo({ ...base, basePath: base.basePath + "/", mediaSource: { TranscodingUrl: "videos/x" } }))
      .toBe("https://jellyfin.example.com/videos/x");
  });
  test("NUNCA devolve o Path interno da origem", () => {
    for (const Path of ["http://127.0.0.1:8097/pluto/x.m3u8", "https://cdn.publico.com/x.m3u8"]) {
      expect(urlAoVivo({ ...base, mediaSource: { Path, Container: "hls", SupportsDirectStream: true, LiveStreamId: "L" } })).toBeNull();
    }
  });
  test("fonte MPEG-TS sem transcode: direct stream pelo servidor com LiveStreamId", () => {
    const u = urlAoVivo({ ...base, playSessionId: "PS", mediaSource: { Id: "MS", Container: "ts", SupportsDirectStream: true, LiveStreamId: "L", Path: "http://127.0.0.1/x.ts" } })!;
    expect(u.startsWith("https://jellyfin.example.com/Videos/CANAL/stream.ts?")).toBe(true);
    const q = new URL(u).searchParams;
    expect(q.get("LiveStreamId")).toBe("L");
    expect(q.get("MediaSourceId")).toBe("MS");
    expect(q.get("Static")).toBe("true");
    expect(q.get("ApiKey")).toBe("TOK");
    expect(q.get("PlaySessionId")).toBe("PS");
  });
  test("sem LiveStreamId ou sem fonte: null (erro claro em vez de girar)", () => {
    expect(urlAoVivo({ ...base, mediaSource: { Container: "ts", SupportsDirectStream: true } })).toBeNull();
    expect(urlAoVivo({ ...base, mediaSource: null })).toBeNull();
  });
});
