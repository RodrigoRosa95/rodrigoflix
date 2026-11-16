#!/usr/bin/env python3
"""Transforma o código do Streamyfin no app RodrigoFlix (pedido do usuário 29/10/2026):
  - nome "RodrigoFlix", pacote br.rodrigoflix.app e link rodrigoflix:// (instala ao lado do Streamyfin oficial);
  - servidor embutido (RODRIGOFLIX_SERVIDOR, ex.: https://jellyfin.seudominio.com): o app já abre na tela de usuário e senha;
  - botão "Entrar com Google": gera um código de Quick Connect e abre /app/sso?code=… no navegador; a página do
    servidor (./servidor.py) faz o login no plugin SSO e autoriza o código; o app, que já fica
    conferindo o código a cada segundo, entra sozinho;
  - um 401 passageiro do Jellyfin não tira mais da conta: só sai se /Users/Me também recusar a chave;
  - Live TV no celular: aba Canais com busca e toque para assistir; no guia, o programa no ar abre o canal.
Licença do Streamyfin: MPL-2.0 — os arquivos alterados precisam ficar com o código disponível.

Uso: aplicar_rodrigoflix.py PASTA_DO_STREAMYFIN   (pode rodar de novo: cada troca confere se já foi feita)
"""
import json
import os
import shutil
import sys

SERVIDOR = os.environ.get('RODRIGOFLIX_SERVIDOR', 'https://jellyfin.example.com').rstrip('/')
HOST = SERVIDOR.split('://', 1)[-1]
PACOTE = 'br.rodrigoflix.app'
NOME = 'RodrigoFlix'
ESQUEMA = 'rodrigoflix'


def copiar(origem, destino):
    # copia o arquivo trocando o domínio de exemplo pelo seu servidor
    texto = open(origem, encoding='utf-8').read().replace('jellyfin.example.com', HOST)
    os.makedirs(os.path.dirname(destino) or '.', exist_ok=True)
    open(destino, 'w', encoding='utf-8').write(texto)


def trocar(caminho, pares):
    s = open(caminho, encoding='utf-8').read()
    for antigo, novo in pares:
        if novo in s:
            continue
        if antigo not in s:
            sys.exit(f'❌ {caminho}: trecho não encontrado (o Streamyfin mudou?):\n{antigo[:200]}')
        s = s.replace(antigo, novo, 1)
    open(caminho, 'w', encoding='utf-8').write(s)


def main():
    raiz = sys.argv[1]
    os.chdir(raiz)

    app = json.load(open('app.json', encoding='utf-8'))
    e = app['expo']
    e['name'], e['scheme'] = NOME, ESQUEMA
    e['android']['package'] = PACOTE
    # Android App Links: deep links do Jellyfin abrem no app
    # Formato: /app/item/HEX (sem o app instalado, o servidor.py redireciona pro Jellyfin web)
    e['android']['intentFilters'] = [f for f in e['android'].get('intentFilters', [])
                                     if not any(d.get('host') == HOST
                                                for d in (f.get('data') if isinstance(f.get('data'), list) else [f.get('data', {})]))]
    for prefix in ['/app/item/']:  # só o link do bridge; /web segue no navegador (SSO, web)
        e['android']['intentFilters'].append({
            'action': 'VIEW',
            'autoVerify': True,
            'data': [{'scheme': 'https', 'host': HOST, 'pathPrefix': prefix}],
            'category': ['BROWSABLE', 'DEFAULT'],
        })
    json.dump(app, open('app.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

    # o plugin do Google Services só compila se o pacote estiver no google-services.json
    trocar('google-services.json', [('"com.fredrikburmester.streamyfin"', f'"{PACOTE}"')])

    os.makedirs('constants', exist_ok=True)
    open('constants/RodrigoFlix.ts', 'w', encoding='utf-8').write(
        '// App RodrigoFlix (Streamyfin modificado): servidor embutido e login com Google pelo SSO do servidor.\n'
        f'export const SERVIDOR_PADRAO = "{SERVIDOR}";\n'
        '// Página do servidor que faz o login no Google e autoriza o código do Quick Connect\n'
        'export const urlLoginGoogle = (base: string, codigo: string) =>\n'
        '  `${base.replace(/\\/+$/, "")}/app/sso?code=${encodeURIComponent(codigo)}`;\n')

    trocar('components/login/Login.tsx', [
        ('import { useLocalSearchParams, useNavigation } from "expo-router";',
         'import { useLocalSearchParams, useNavigation } from "expo-router";\n'
         'import * as WebBrowser from "expo-web-browser";'),
        ('import { Colors } from "@/constants/Colors";',
         'import { Colors } from "@/constants/Colors";\n'
         'import { SERVIDOR_PADRAO, urlLoginGoogle } from "@/constants/RodrigoFlix";'),
        ('''  const {
    apiUrl: _apiUrl,
    username: _username,
    password: _password,
  } = params as { apiUrl: string; username: string; password: string };''',
         '''  const {
    apiUrl: _apiUrlLink,
    username: _username,
    password: _password,
  } = params as { apiUrl: string; username: string; password: string };
  // RodrigoFlix: sem servidor no link, usa o servidor embutido
  const _apiUrl = _apiUrlLink || SERVIDOR_PADRAO;'''),
        ('''    if (user) setQuickConnectCode(null);''',
         '''    if (user) setQuickConnectCode(null);
    // RodrigoFlix: fecha o navegador do login com Google, se ainda estiver aberto
    if (user) {
      try {
        WebBrowser.dismissBrowser()?.catch?.(() => {});
      } catch {}
    }'''),
        ('''  return (
    <SafeAreaView style={{ flex: 1, paddingBottom: 16 }}>''',
         '''  // RodrigoFlix: login com Google = código do Quick Connect autorizado pela página /app/sso do servidor
  const handleGoogleLogin = async () => {
    if (!api?.basePath) return;
    try {
      const code = await initiateQuickConnect();
      if (!code) throw new Error("sem código");
      setQuickConnectActive(true);
      await WebBrowser.openBrowserAsync(urlLoginGoogle(api.basePath, code));
    } catch (_error) {
      Alert.alert(
        t("login.error_title"),
        "Não foi possível abrir o login com Google. Tente de novo.",
      );
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, paddingBottom: 16 }}>'''),
        ('''                    <MaterialCommunityIcons
                      name='cellphone-lock'
                      size={24}
                      color='white'
                    />
                  </TouchableOpacity>
                </View>''',
         '''                    <MaterialCommunityIcons
                      name='cellphone-lock'
                      size={24}
                      color='white'
                    />
                  </TouchableOpacity>
                </View>
                <TouchableOpacity
                  onPress={handleGoogleLogin}
                  className='flex flex-row items-center justify-center h-12 rounded-xl bg-white mt-2'
                  activeOpacity={0.8}
                >
                  <Ionicons name='logo-google' size={20} color='#4285F4' />
                  <Text className='ml-2 font-semibold' style={{ color: "#111" }}>
                    Entrar com Google
                  </Text>
                </TouchableOpacity>'''),
        ('''              <Text className='text-3xl font-bold'>Streamyfin</Text>''',
         f'''              <Text className='text-3xl font-bold'>{NOME}</Text>'''),
    ])
    # O Jellyfin responde 401 por um instante em itens que estão sendo atualizados (biblioteca mudando) e o Streamyfin
    # saía da conta no primeiro 401 ("Opa! Algo correu mal", 29/10/2026). Agora só sai se a chave for recusada também
    # num pedido simples (/Users/Me); erro de rede ou 401 passageiro não derrubam a sessão.
    trocar('providers/JellyfinProvider.tsx', [
        ('''      (error) => {
        if (error?.response?.status === 401) {
          handleSessionExpired();
        }
        return Promise.reject(error);
      },''',
         '''      (error) => {
        if (error?.response?.status === 401) {
          // RodrigoFlix: confirma que a chave morreu antes de sair da conta
          fetch(`${api.basePath}/Users/Me`, {
            headers: { Authorization: `MediaBrowser Token="${api.accessToken}"` },
          })
            .then((r) => {
              if (r.status === 401) handleSessionExpired();
            })
            .catch(() => {});
        }
        return Promise.reject(error);
      },'''),
    ])
    # Live TV no celular (pedido do usuário 29/10/2026): no Streamyfin a aba Canais só listava os canais, sem tocar,
    # e o guia abria a página do programa. Agora: busca + programa atual na lista, toque abre o canal no player
    # (o direct-player já sabe abrir/fechar o LiveStream), e no guia o programa que está no ar abre o canal.
    open('app/(auth)/(tabs)/(home,libraries,search,favorites,watchlists)/livetv/channels.tsx', 'w',
         encoding='utf-8').write(CANAIS_TSX)
    # Módulo ADB Installer: copia o módulo nativo para modules/adb-installer
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0] if len(sys.argv) > 0 else __file__))
    modulo_src = os.path.join(script_dir, 'modulo-adb')
    modulo_dst = os.path.join('modules', 'adb-installer')
    if os.path.isdir(modulo_src):
        if os.path.isdir(modulo_dst):
            shutil.rmtree(modulo_dst)
        shutil.copytree(modulo_src, modulo_dst)
        print('  📺 módulo adb-installer copiado')

    # Registrar o módulo no modules/index.ts
    index_modules = open('modules/index.ts', 'r', encoding='utf-8').read()
    adb_export = '// ADB Installer (RodrigoFlix TV)\nexport { isAdbInstallerAvailable, scanTVs, installOnTV } from "./adb-installer";\n'
    if 'adb-installer' not in index_modules:
        open('modules/index.ts', 'a', encoding='utf-8').write('\n' + adb_export)

    # Copiar tela "Instalar na TV"
    tela_src = os.path.join(script_dir, 'tela-instalar-tv.tsx')
    tela_dst = os.path.join('app', '(auth)', '(tabs)', '(home)', 'instalar-tv.tsx')
    if os.path.isfile(tela_src):
        shutil.copy2(tela_src, tela_dst)
        print('  📺 tela instalar-tv.tsx copiada')

    # Adicionar botão "Instalar na TV" na tela de configurações
    trocar('app/(auth)/(tabs)/(home)/settings.tsx', [
        ('''import { useJellyfin, userAtom } from "@/providers/JellyfinProvider";''',
         '''import { useJellyfin, userAtom } from "@/providers/JellyfinProvider";\nimport { isAdbInstallerAvailable } from "@/modules/adb-installer";'''),
        ('''        <StorageSettings />''',
         '''        {isAdbInstallerAvailable && (
          <View className='mb-4'>
            <ListGroup title='RodrigoFlix'>
              <ListItem
                onPress={() => router.push("/(auth)/(tabs)/(home)/instalar-tv")}
                showArrow
                title='📺 Instalar na TV'
              />
            </ListGroup>
          </View>
        )}

        <StorageSettings />'''),
    ])

    # Registrar rota instalar-tv no layout da home
    trocar('app/(auth)/(tabs)/(home)/_layout.tsx', [
        ('''      <Stack.Screen
        name='companion-login'
        options={{''',
         '''      <Stack.Screen
        name='instalar-tv'
        options={{
          title: 'Instalar na TV',
          headerShown: !Platform.isTV,
          headerBlurEffect: "none",
          headerTransparent: Platform.OS === "ios",
          headerShadowVisible: false,
        }}
      />
      <Stack.Screen
        name='companion-login'
        options={{'''),
    ])

    # Deep link (12/11): o link do WhatsApp (https://SEU-SERVIDOR/app/item/ID) abre o item no app.
    # Antes era um useEffect no _layout que perdia a corrida (getInitialURL chegava depois do efeito) e o
    # expo-router ia pra +not-found. Agora o próprio roteador traduz a URL em app/+native-intent.tsx.
    # A lógica fica em ./deeplink/ (testada com `bun test` em este repositório).
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deeplink')
    copiar(os.path.join(d, 'rodrigoflixDeepLink.ts'), 'utils/rodrigoflixDeepLink.ts')
    copiar(os.path.join(d, '+native-intent.tsx'), 'app/+native-intent.tsx')
    # tira o patch antigo do _layout, se a pasta já tinha sido modificada
    s = open('app/_layout.tsx', encoding='utf-8').read()
    a = s.find('  // RodrigoFlix: deep link — abre item do Jellyfin direto no app')
    if a != -1:
        fim = '  }, [user, api, router]);\n'
        b = s.index(fim, a) + len(fim)
        s = s[:a].rstrip(' \n') + '\n\n' + s[b:].lstrip('\n')
        s = s.replace('import { Linking } from "react-native";\nimport { Stack, useSegments }',
                      'import { Stack, useSegments }', 1)
        open('app/_layout.tsx', 'w', encoding='utf-8').write(s)
    # deslogado: o +native-intent guardou o item; abre assim que o login terminar
    trocar('app/_layout.tsx', [
        ('import { storage } from "@/utils/mmkv";',
         'import { storage } from "@/utils/mmkv";\n'
         'import { CHAVE_ITEM_PENDENTE, rotaDoItem } from "@/utils/rodrigoflixDeepLink";'),
        ('  useNotificationObserver();\n  useNativePlayerLogBridge();\n',
         '  useNotificationObserver();\n  useNativePlayerLogBridge();\n'
         '\n'
         '  // RodrigoFlix: item do link aberto antes do login (guardado pelo +native-intent)\n'
         '  useEffect(() => {\n'
         '    if (!user?.Id || !api || _segments[0] !== "(auth)") return;\n'
         '    const id = storage.getString(CHAVE_ITEM_PENDENTE);\n'
         '    if (!id) return;\n'
         '    const t = setTimeout(() => {\n'
         '      storage.remove(CHAVE_ITEM_PENDENTE);\n'
         '      router.push(rotaDoItem(id) as any);\n'
         '    }, 400);\n'
         '    return () => clearTimeout(t);\n'
         '  }, [user?.Id, api, _segments[0]]);\n'),
    ])

    # TV ao vivo (12/11): mesmo caminho do app oficial do Jellyfin — o servidor abre o canal e faz remux HLS.
    # Antes os canais (Pluto/Plex 127.0.0.1:8097, ponte 8099) ficavam girando: o app tocava o Path interno ou
    # repassava a playlist HLS da origem com endereços relativos (404). Lógica em ./livetv/ (bun test).
    copiar(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'livetv', 'rodrigoflixLiveTv.ts'),
           'utils/jellyfin/media/rodrigoflixLiveTv.ts')
    trocar('utils/jellyfin/media/getStreamUrl.ts', [
        ('import { isPlayableItem } from "./isPlayableItem";',
         'import { isPlayableItem } from "./isPlayableItem";\n'
         'import {\n'
         '  canalDoItem,\n'
         '  ehAoVivo,\n'
         '  pedidoPlaybackInfoAoVivo,\n'
         '  urlAoVivo,\n'
         '} from "./rodrigoflixLiveTv";'),
        ('  let mediaSource: MediaSourceInfo | undefined;\n'
         '  let sessionId: string | null | undefined;\n',
         '  // RodrigoFlix: TV ao vivo como no app oficial — PlaybackInfo sem direct play/stream, o servidor\n'
         '  // abre o canal (LiveStreamId) e entrega HLS próprio (remux). Nunca toca o Path da origem.\n'
         '  if (ehAoVivo(item)) {\n'
         '    const canalId = canalDoItem(item);\n'
         '    if (!canalId) {\n'
         '      throw markExpectedError(new Error("Programa sem canal"));\n'
         '    }\n'
         '    const res = await getMediaInfoApi(api).getPlaybackInfo(\n'
         '      { itemId: canalId },\n'
         '      {\n'
         '        method: "POST",\n'
         '        data: pedidoPlaybackInfoAoVivo({\n'
         '          userId,\n'
         '          deviceProfile,\n'
         '          maxStreamingBitrate,\n'
         '          audioStreamIndex,\n'
         '        }) as any,\n'
         '      },\n'
         '    );\n'
         '    const fonte = res.data.MediaSources?.[0];\n'
         '    if (!fonte) {\n'
         '      throw markExpectedError(\n'
         '        new Error(\n'
         '          `Canal sem fonte de mídia (${res.data.ErrorCode ?? "sem ErrorCode"})`,\n'
         '        ),\n'
         '      );\n'
         '    }\n'
         '    const url = urlAoVivo({\n'
         '      basePath: api.basePath,\n'
         '      accessToken: api.accessToken,\n'
         '      deviceId: deviceId || api.deviceInfo.id,\n'
         '      itemId: canalId,\n'
         '      playSessionId: res.data.PlaySessionId,\n'
         '      mediaSource: fonte,\n'
         '    });\n'
         '    if (!url) {\n'
         '      throw markExpectedError(\n'
         '        new Error("O servidor não ofereceu um fluxo para este canal"),\n'
         '      );\n'
         '    }\n'
         '    console.log("TV ao vivo pelo servidor:", url);\n'
         '    return {\n'
         '      url,\n'
         '      sessionId: res.data.PlaySessionId || null,\n'
         '      mediaSource: fonte,\n'
         '    };\n'
         '  }\n'
         '\n'
         '  let mediaSource: MediaSourceInfo | undefined;\n'
         '  let sessionId: string | null | undefined;\n'),
    ])

    # TV ao Vivo: toque no canal abre o player direto (não a página do item)
    trocar('components/common/TouchableItemRouter.tsx', [
        ('''  if ("CollectionType" in item && item.CollectionType === "livetv") {
    return {
      pathname: "/livetv" as const,
    };
  }''',
         '''  if ("CollectionType" in item && item.CollectionType === "livetv") {
    return {
      pathname: "/livetv" as const,
    };
  }

  // RodrigoFlix: canal ao vivo abre o player direto
  if (item.Type === "TvChannel") {
    return {
      pathname: "/player/direct-player" as const,
      params: {
        itemId: item.Id!,
        audioIndex: "",
        subtitleIndex: "",
        mediaSourceId: "",
        bitrateValue: "",
      },
    };
  }'''),
    ])

    # TV ao Vivo na home: seção horizontal com os canais ao vivo no topo da página inicial
    trocar('components/home/Home.tsx', [
        ('import {\n  getItemsApi,\n  getSuggestionsApi,\n  getTvShowsApi,\n  getUserLibraryApi,\n  getUserViewsApi,\n} from "@jellyfin/sdk/lib/utils/api";',
         'import {\n  getItemsApi,\n  getLiveTvApi,\n  getSuggestionsApi,\n  getTvShowsApi,\n  getUserLibraryApi,\n  getUserViewsApi,\n} from "@jellyfin/sdk/lib/utils/api";'),
        ('''    const ss: Section[] = [
      ...firstSections,
      ...latestMediaViews.map((s) => ({ ...s, priority: 2 as const })),''',
         '''    const ss: Section[] = [
      ...firstSections,
      {
        title: "📺 TV ao Vivo",
        queryKey: ["home", "liveTvChannels", api.basePath, user.Id],
        queryFn: async ({ pageParam = 0 }) => {
          const res = await getLiveTvApi(api).getLiveTvChannels({
            startIndex: pageParam,
            limit: 20,
            enableFavoriteSorting: true,
            userId: user.Id,
            addCurrentProgram: true,
            enableUserData: false,
            enableImageTypes: ["Primary"],
          });
          return res.data.Items || [];
        },
        type: "InfiniteScrollingCollectionList",
        orientation: "horizontal",
        pageSize: 20,
        priority: 1,
      },
      ...latestMediaViews.map((s) => ({ ...s, priority: 2 as const })),'''),
    ])

    trocar('components/livetv/LiveTVGuideRow.tsx', [
        ('import { Dimensions, View } from "react-native";',
         'import { useRouter } from "expo-router";\n'
         'import { Dimensions, View } from "react-native";'),
        ('''  const screenWidth = Dimensions.get("window").width;''',
         '''  const screenWidth = Dimensions.get("window").width;
  const router = useRouter();
  // RodrigoFlix: programa no ar abre o canal ao vivo
  const assistirAgora = (p: BaseItemDto) => {
    const q = new URLSearchParams({
      itemId: p.ChannelId ?? channel.Id ?? "",
      audioIndex: "",
      subtitleIndex: "",
      mediaSourceId: "",
      bitrateValue: "",
    });
    router.push(`/player/direct-player?${q.toString()}`);
  };'''),
        ('''      {programsWithPositions?.map((p) => (
        <TouchableItemRouter item={p} key={p.Id}>''',
         '''      {programsWithPositions?.map((p) => (
        <TouchableItemRouter
          item={p}
          key={p.Id}
          {...(isCurrentlyLive(p) ? { onPress: () => assistirAgora(p) } : {})}
        >'''),
    ])

    # Live TV na aba Biblioteca: o getUserViews nem sempre inclui a Live TV,
    # então injetamos um card virtual se houver canais no servidor
    trocar('components/library/Libraries.tsx', [
        ('import {\n  getUserLibraryApi,\n  getUserViewsApi,\n} from "@jellyfin/sdk/lib/utils/api";',
         'import {\n  getLiveTvApi,\n  getUserLibraryApi,\n  getUserViewsApi,\n} from "@jellyfin/sdk/lib/utils/api";'),
        ('''  const libraries = useMemo(
    () =>
      data
        ?.filter((l) => !settings?.hiddenLibraries?.includes(l.Id!))
        .filter((l) => l.CollectionType !== "books") || [],
    [data, settings?.hiddenLibraries],
  );''',
         '''  // RodrigoFlix: garantir que a Live TV aparece na lista mesmo que getUserViews não a retorne
  const { data: liveTvCount } = useQuery({
    queryKey: ["livetv", "channel-count"],
    queryFn: async () => {
      const res = await getLiveTvApi(api!).getLiveTvChannels({
        userId: user?.Id,
        limit: 1,
      });
      return res.data.TotalRecordCount ?? 0;
    },
    enabled: !!api && !!user?.Id,
    staleTime: 5 * 60 * 1000,
  });

  const libraries = useMemo(() => {
    const filtered =
      data
        ?.filter((l) => !settings?.hiddenLibraries?.includes(l.Id!))
        .filter((l) => l.CollectionType !== "books") || [];

    const hasLiveTv = filtered.some((l) => l.CollectionType === "livetv");
    if (!hasLiveTv && liveTvCount && liveTvCount > 0) {
      filtered.push({
        Name: "TV ao Vivo",
        CollectionType: "livetv",
        Id: "livetv-virtual",
        Type: "CollectionFolder",
      } as any);
    }

    return filtered;
  }, [data, settings?.hiddenLibraries, liveTvCount]);'''),
    ])
    trocar('components/library/LibraryItemCard.tsx', [
        ('''  const { data: itemsCount } = useQuery({
    queryKey: ["library-count", library.Id],
    queryFn: async () => {
      const response = await getItemsApi(api!).getItems({
        userId: user?.Id,
        parentId: library.Id,
        recursive: true,
        limit: 0,
        includeItemTypes: itemType ? [itemType] : undefined,
      });
      return response.data.TotalRecordCount;
    },
  });

  if (!url) return null;''',
         '''  const isLiveTv = library.CollectionType === "livetv";

  const { data: itemsCount } = useQuery({
    queryKey: ["library-count", library.Id],
    queryFn: async () => {
      if (isLiveTv) {
        const { getLiveTvApi } = await import("@jellyfin/sdk/lib/utils/api");
        const res = await getLiveTvApi(api!).getLiveTvChannels({
          userId: user?.Id,
          limit: 0,
        });
        return res.data.TotalRecordCount;
      }
      const response = await getItemsApi(api!).getItems({
        userId: user?.Id,
        parentId: library.Id,
        recursive: true,
        limit: 0,
        includeItemTypes: itemType ? [itemType] : undefined,
      });
      return response.data.TotalRecordCount;
    },
  });

  if (!url && !isLiveTv) return null;'''),
        # Imagem cover: fallback com ícone quando não tem imagem (Live TV virtual)
        ('''            <Image
              source={{ uri: url }}
              style={{
                width: "100%",
                height: "100%",
              }}
              cachePolicy={"memory-disk"}
            />''',
         '''            {url ? (
              <Image
                source={{ uri: url }}
                style={{
                  width: "100%",
                  height: "100%",
                }}
                cachePolicy={"memory-disk"}
              />
            ) : (
              <View style={{ width: "100%", height: "100%", alignItems: "center", justifyContent: "center", backgroundColor: "#1b2128" }}>
                <Ionicons name={icons[library.CollectionType!] || "folder"} size={32} color="#e5e5e5" />
              </View>
            )}'''),
        # Imagem poster: fallback com ícone
        ('''          <Image
            source={{ uri: url }}
            className='h-full aspect-[2/1] object-cover rounded-lg overflow-hidden'
          />''',
         '''          {url ? (
            <Image
              source={{ uri: url }}
              className='h-full aspect-[2/1] object-cover rounded-lg overflow-hidden'
            />
          ) : (
            <View className='h-full aspect-[2/1] rounded-lg overflow-hidden items-center justify-center' style={{ backgroundColor: "#1b2128" }}>
              <Ionicons name={icons[library.CollectionType!] || "folder"} size={28} color="#e5e5e5" />
            </View>
          )}'''),
    ])

    print('✅ RodrigoFlix aplicado em', raiz)


CANAIS_TSX = '''// RodrigoFlix: canais ao vivo com busca, programa atual e toque para assistir (Streamyfin só listava).
import { getLiveTvApi } from "@jellyfin/sdk/lib/utils/api";
import { FlashList } from "@shopify/flash-list";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useAtom } from "jotai";
import { useMemo, useState } from "react";
import { TouchableOpacity, View } from "react-native";
import { Input } from "@/components/common/Input";
import { ItemImage } from "@/components/common/ItemImage";
import { Text } from "@/components/common/Text";
import { apiAtom, userAtom } from "@/providers/JellyfinProvider";

const semAcento = (s?: string | null) =>
  (s ?? "")
    .normalize("NFD")
    .replace(/[\\u0300-\\u036f]/g, "")
    .toLowerCase();

export default function LiveTvChannelsPage() {
  const [api] = useAtom(apiAtom);
  const [user] = useAtom(userAtom);
  const router = useRouter();
  const [busca, setBusca] = useState("");

  const { data: channels, isLoading } = useQuery({
    queryKey: ["livetv", "channels", "rodrigoflix"],
    queryFn: async () => {
      const res = await getLiveTvApi(api!).getLiveTvChannels({
        startIndex: 0,
        limit: 2000,
        enableFavoriteSorting: true,
        userId: user?.Id,
        addCurrentProgram: true,
        enableUserData: false,
        enableImageTypes: ["Primary"],
      });
      return res.data;
    },
    enabled: !!api,
    staleTime: 60 * 1000,
  });

  const lista = useMemo(() => {
    const termo = semAcento(busca.trim());
    const itens = channels?.Items ?? [];
    if (!termo) return itens;
    return itens.filter(
      (c) =>
        semAcento(c.Name).includes(termo) ||
        semAcento(c.CurrentProgram?.Name).includes(termo),
    );
  }, [channels, busca]);

  const assistir = (id?: string | null) => {
    if (!id) return;
    const q = new URLSearchParams({
      itemId: id,
      audioIndex: "",
      subtitleIndex: "",
      mediaSourceId: "",
      bitrateValue: "",
    });
    router.push(`/player/direct-player?${q.toString()}`);
  };

  return (
    <View className='flex flex-1'>
      <View className='px-4 pt-3 pb-2'>
        <Input
          placeholder='Buscar canal ou programa'
          value={busca}
          onChangeText={setBusca}
          autoCorrect={false}
          returnKeyType='search'
          clearButtonMode='while-editing'
        />
      </View>
      {!isLoading && lista.length === 0 ? (
        <Text className='px-4 mt-4 text-neutral-500'>Nenhum canal encontrado.</Text>
      ) : null}
      <FlashList
        data={lista}
        keyboardShouldPersistTaps='handled'
        keyExtractor={(item) => item.Id!}
        renderItem={({ item }) => (
          <TouchableOpacity
            onPress={() => assistir(item.Id)}
            className='flex flex-row items-center px-4 py-1 mb-1'
          >
            <View className='mr-4 rounded-lg overflow-hidden bg-neutral-900'>
              <ItemImage
                style={{ aspectRatio: "1/1", width: 56, borderRadius: 8 }}
                item={item}
              />
            </View>
            <View className='flex-1'>
              <Text className='font-bold' numberOfLines={1}>
                {item.ChannelNumber ? `${item.ChannelNumber}  ` : ""}
                {item.Name}
              </Text>
              {item.CurrentProgram?.Name ? (
                <Text className='text-xs text-neutral-400' numberOfLines={1}>
                  Agora: {item.CurrentProgram.Name}
                </Text>
              ) : null}
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}
'''


if __name__ == '__main__':
    main()
