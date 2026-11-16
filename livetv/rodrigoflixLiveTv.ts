// RodrigoFlix: TV ao vivo do mesmo jeito que o app oficial do Jellyfin (jellyfin-android 2.7.3 + jellyfin-web 10.11).
// Sem imports: é copiado para utils/jellyfin/media/ do Streamyfin e testado com `bun test` em este repositório.
//
// Por que os canais ficavam carregando para sempre:
//  - as listas M3U do servidor (Pluto/Plex em 127.0.0.1:8097, ponte 8099) dão um Path interno; o Streamyfin tocava
//    esse Path direto (IsRemote) ou pedia /Videos/ID/stream?static=true SEM LiveStreamId;
//  - para fonte HLS, esse "direct stream" só repassa a playlist da origem, com endereços RELATIVOS
//    (1042180/playlist.m3u8) que no servidor Jellyfin dão 404 → o player tenta de novo, sem fim.
// O app oficial não declara "remotevideo" (nativeshell.js), então nunca toca o Path da origem; e o ExoPlayer dele,
// quando falha, pede de novo com EnableDirectPlay=false e depois EnableDirectStream=false (QueueManager.kt).
// Aqui vamos direto a esse último passo: o servidor abre o canal (LiveStreamId) e o ffmpeg dele faz remux
// (codec copy, quase sem CPU) para um HLS próprio em /videos/ID/master.m3u8 — funciona de qualquer rede.

export interface FonteAoVivo {
  Id?: string | null;
  Container?: string | null;
  LiveStreamId?: string | null;
  TranscodingUrl?: string | null;
  SupportsDirectStream?: boolean;
  Path?: string | null;
}

/** Canal ou programa da TV ao vivo? */
export const ehAoVivo = (item: { Type?: string | null } | null | undefined): boolean =>
  !!item && (item.Type === "TvChannel" || item.Type === "Program" || item.Type === "LiveTvChannel");

/** Id do canal que deve ser aberto (um Program toca o canal dele). */
export const canalDoItem = (item: { Type?: string | null; Id?: string | null; ChannelId?: string | null }): string | null =>
  (item.Type === "Program" ? item.ChannelId : item.Id) || null;

/** Corpo do POST /Items/{canal}/PlaybackInfo, igual ao último passo de tentativa do app oficial. */
export const pedidoPlaybackInfoAoVivo = (o: {
  userId: string;
  deviceProfile: unknown;
  maxStreamingBitrate?: number;
  audioStreamIndex?: number;
}) => ({
  userId: o.userId,
  deviceProfile: o.deviceProfile,
  startTimeTicks: 0,
  isPlayback: true,
  autoOpenLiveStream: true,
  enableDirectPlay: false,
  enableDirectStream: false,
  maxStreamingBitrate: o.maxStreamingBitrate,
  audioStreamIndex: o.audioStreamIndex,
});

/**
 * URL que o player deve abrir para o canal. Nunca devolve o Path da origem.
 * 1) TranscodingUrl do servidor (remux/transcode HLS com LiveStreamId) — o caminho normal;
 * 2) direct stream pelo servidor com LiveStreamId, só para fontes que não são HLS (ex.: MPEG-TS cru);
 * 3) null: sem caminho que funcione — o player mostra erro em vez de ficar girando.
 */
export function urlAoVivo(o: {
  basePath: string;
  accessToken: string;
  deviceId: string;
  itemId: string;
  playSessionId?: string | null;
  mediaSource: FonteAoVivo | null | undefined;
}): string | null {
  const ms = o.mediaSource;
  if (!ms) return null;
  const base = o.basePath.replace(/\/+$/, "");
  if (ms.TranscodingUrl) {
    const t = ms.TranscodingUrl;
    if (/^https?:\/\//i.test(t)) return t;
    return `${base}${t.startsWith("/") ? "" : "/"}${t}`;
  }
  const cont = (ms.Container || "").toLowerCase();
  if (ms.SupportsDirectStream && ms.LiveStreamId && cont && cont !== "hls" && cont !== "m3u8") {
    const q = new URLSearchParams({
      Static: "true",
      MediaSourceId: ms.Id || "",
      LiveStreamId: ms.LiveStreamId,
      DeviceId: o.deviceId,
      ApiKey: o.accessToken,
    });
    if (o.playSessionId) q.append("PlaySessionId", o.playSessionId);
    return `${base}/Videos/${o.itemId}/stream.${cont}?${q.toString()}`;
  }
  return null;
}
