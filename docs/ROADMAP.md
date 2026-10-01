# Roadmap

Yavaş yavaş, aşama aşama ilerliyoruz. Her aşama tek oturumda bitecek büyüklükte, sonunda
çalışan ve testli bir uygulama bırakır; istenen yerde durulabilir. Bu dosya kararların ve
kalan işlerin tek kaynağıdır: yeni oturum buradan kaldığı yeri seçer.

Hedef: sohbet tarafı Claude.ai / ChatGPT kadar, hatta daha yetenekli olsun (web arama, URL
okuma, görsel/dosya yükleme, kaliteli MCP desteği); modeller kodcu değil normal chat asistanı
gibi davransın; Council penceresinde kimin ne dediği ve kime cevap verdiği net görünsün;
özelleştirme ekranı sadeleşsin.

## Alınan kararlar

- **Sıralama:** güvenlik -> arama ve MCP -> görsel/dosya yükleme -> Council arayüzü ->
  persona. Persona en sona kalır, çünkü modellerin prompt'u o turda gerçekten açık olan
  yeteneklerden üretilecek (hangi araçlar, hangi MCP'ler, görsel/dosya alabiliyor mu).
  Kapalı bir aracı var saymayacak, "yapamıyorum, şu ayarı aç" diyecek.
- **Arama:** kendi sunucumuzda SearXNG (ücretsiz, anahtarsız). Brave/Tavily/Exa gibi
  anahtarlı servisler opsiyonel. Mevcut HN/DuckDuckGo kodu son çare olarak kalır.
- **MCP:** varsayılan-reddet allowlist, araç başına `auto | ask | deny`, yazan veya
  çalıştıran araçlar onay ister. Mağaza kürate katalogdur; rastgele stdio komutu yalnız
  "gelişmiş" bölümünde ve uyarılı. Araç çıktıları modele "güvenilmeyen veri" çerçevesiyle
  verilir. MCP anahtarları API'de asla düz metin dönmez.
- **Workspace araçları** (`workspace_read_file`, `workspace_git_diff`) Round Table
  varsayılanında kapalı; yalnız workspace hedeflenince veya ayardan açılır.
- **Tek ortak tool döngüsü** roundtable, tek-model chat ve council için. Şu an tek araç turu
  var ve sonuçlar atılıyor.
- **Shim koltukları** (Claude Code, Antigravity) araçları metin protokolüyle kullanır;
  CLI'ların varsayılan kodlama prompt'u ve çalışma dizini persona aşamasında temizlenir.
- **Commit/push** yalnız açıkça istenince. Repo public: dosyalara özel IP, host adı, anahtar
  veya kişisel bilgi yazılmaz.

## Aşama 1: Güvenlik ve bilinen hatalar

- [x] `workspace_read_file`: mutlak yol ve klasör sınırı yok, container içindeki `.env`
      okunabiliyor. `resolve()` + `is_relative_to()` + `.env`/`.git/config`/`data/` deny
      listesi; Round Table varsayılan araç setinden çıkar.
- [x] `web_fetch` SSRF koruması: özel/loopback/link-local/metadata adresleri reddi, elle
      redirect takibi, IP pinleme, boyut ve content-type sınırı.
- [x] Markdown resimlerinin otomatik yüklenmesini kapat (veri sızdırma kanalı).
- [x] `PUT /api/config` her kaydedişte routing/tier/escalation ayarlarını varsayılana
      sıfırlıyor; oku-birleştir ve atomik yaz.
- [x] `_prepare_messages_for_model` hata dalında `return` eksik (None döner).
- [x] Skills: id/klasör uyuşmazlığı, enjekte edilen skill metni için uzunluk sınırı, skill
      içe aktarmada SSRF kontrolü.
- [x] Global istek gövdesi sınırı; yükleme ve araç uçlarına hız sınırı.
- [x] Gizli bilgi taraması testi: tüm `GET` yanıtlarında anahtar desenleri aranır.
- [x] Shim'ler liste biçimli içerikte çöküyor; şimdilik metne düzleştir.
- [x] Frontend: `loadConversation` için id/istek guard'ı (kullanıcı başka sohbete geçmişse
      ekranı geri çekmesin), sohbet başına polling zamanlayıcısı.
- [x] `GET /conversations/{id}` self-heal: çalışan deliberation'ı `idle` yapmasın.

## Aşama 2: Arama, ortak tool döngüsü, MCP

- [x] SearXNG servisi (`infra/docker-compose.yml`, yalnız iç ağ) ve `SEARXNG_URL`.
- [x] `web_fetch`: temiz markdown çıkarma, PDF metni, önbellek.
- [x] `paper_search` (arXiv, OpenAlex) ve Wikipedia araçları.
- [x] Ortak `run_tool_loop`: çok adımlı, akışlı son cevap, sınırlar (tur, süre, çağrı,
      tekrar), abort, hata olayları, sonuç ve kaynakların kalıcılığı. (Akış ve kalıcılık
      notları aşağıda.)
- [ ] Shim koltukları için metin tabanlı tool protokolü.
- [x] MCP istemcisi (resmi Python SDK), `data/mcp_servers.json`, `/api/mcp-servers` uçları,
      araç başına izin ve onay akışı. (Notlar aşağıda; UI henüz yok.)
- [x] MCP Mağazası: `backend/tools/mcp_library.py` (sabit sürümlü, `uvx` ile; şimdilik `fetch`
      ve `arxiv`). İstemci komut veremez, yalnız katalog id'si seçer; `MCP_ALLOW_STDIO` kapalı
      kalır. `markitdown-mcp` bilerek yok (`file://` ile container dosyalarını okur). Yeni
      giriş eklemeden önce PyPI/OSV doğrulaması ve araçların neye eriştiğine bakılır.
- [x] UI: MCP sekmesi (Installed / Library), onay kartı, Round Table koltuğu başına MCP araç
      seçimi (`model_mcp_tools`; seçilmeyen araç modele sunulmaz ve çağrısı reddedilir).
- [ ] UI kalanı: sohbet başlığında araç popover'ı, araç zaman çizelgesi ve kaynak chip'leri,
      Round Table'da reasoning (thinking) gösterimi.
- [ ] Council'de MCP: Stage 1 zaten araç kullanıyor (`@skill` haritası, MCP yok). Koltuk başına
      MCP için council tanımına seçim alanı ve Stage 1 akışında onay olayı gerekir; onay
      kanalı olmayan `ask` araçları şu an reddedilir.
- [x] Testler: SSRF, yol sınırı, sahte modelle tool döngüsü, MCP istemcisi
      (`test_tool_security`, `test_web_fetch`, `test_tool_loop`, `test_mcp_client`).

## Aşama 3: Görsel ve dosya yükleme

- [x] Ekler: `backend/attachments.py`, uçlar `/api/conversations/{id}/attachments` (POST/GET
      liste/GET dosya/DELETE). Tür magic-byte'tan; görsel Pillow ile yeniden kodlanır (EXIF ve
      eklenmiş veri gider, 2048 px, 50 MP sınırı, GIF ilk kare), PDF/metin çıkarımı 50k karakter
      ve yalnız sunucuda (istemciye `text_chars`). Sınırlar: görsel 10 MB, PDF 20 MB, metin 1 MB,
      sohbet başına 20. Gövde sınırı yalnız bu yolda 20 MB (`MAX_UPLOAD_BYTES`), hız sınırı var.
      Depo `DATA_ROOT/attachments/<sohbet>/`, sohbet silinince temizlenir. Yeni bağımlılık:
      `pillow`, `python-multipart` (imaj yeniden build edilmeli). Dosya `nosniff` + CSP sandbox ile
      servis edilir; frontend `<img src>` bearer gönderemez, blob olarak `apiFetch` ile çekmeli.
- [ ] Mesaj içeriği `text + image_url` listesi; vision'sız modeller için çıkarılmış metin
      (güvenilmeyen veri çerçevesiyle).
      Yapıldı (metin yolu): `SendMessageRequest.attachment_ids`; PDF/metin `<attachment>`
      çerçevesiyle (kapanış etiketi kaçırılır) Council, stream ve Round Table sorgusuna eklenir,
      mesajda yalnız herkese açık meta (`attachments`) saklanır, yabancı/bilinmeyen id 404.
      Görseller: mesajda yalnız referans (`_images`) taşınır; `openrouter._prepare_messages_for_model`
      her model için çözer: vision'lı modele `image_url` (data URL), diğerine "göremiyor" notu,
      iç alan hiçbir zaman sağlayıcıya gitmez. Council stage 1 (stream) ve Round Table ilk hop'ta.
      Sınırlar: non-stream `/message` yolu ve Round Table'ın sonraki hop'ları/eski turları görsel
      taşımaz (ek yalnız gönderildiği turda, ilk hop'ta). Stage 2/3 görseli görmez (yalnız metin).
      Görsel bayt'ı yalnız vision'lı seçili modele ve onun sağlayıcısına gider.
- [x] Model yetenek haritası: `backend/capabilities.py` yalnız vision (kayıttaki `vision`
      bayrağı > `VISION_MODELS` env > ad desenleri; bilinmeyen = yalnız metin). Araç/pdf/bağlam
      uzunluğu henüz yok.
- [ ] Shim'lerde görsel/dosya desteği (stream-json veya `--add-dir`; gerçek çağrıyla doğrula).
- [x] Frontend: `Attach` düğmesi, sürükle-bırak, yapıştır, küçük resim şeridi (taslak), baloncukta
      görsel önizleme ve dosya chip'i. Dosyalar gönderim anında yüklenir (karşılama ekranında
      sohbet henüz yok): `useAttachmentDraft`, `components/Attachments.jsx`,
      `api.uploadAttachment/getAttachmentBlob`. Görseller `apiFetch` ile blob olarak çekilir.
      Yükleme hatası stream hatasıyla aynı yoldan görünür. Tarayıcıda doğrulandı (yalıtılmış
      backend, geçici veri): yükleme, baloncuk, yeniden yüklemede önizleme, yerel modelin dosya
      metnini okuması. Eksik: istemci tarafı hata metni yalnız seçimde, sunucu reddi (ör. bozuk
      görsel) mesaj gönderilirken görünür.

## Aşama 4: Council arayüzü ve ConfigPanel

- [ ] `metadata` ve tam debate verisi kalıcı (yeniden yüklemede Stage 2 matrisi, etiketler,
      maliyet kaybolmasın).
- [ ] Rebuttal olayına `critic` bilgisi; model hataları kullanıcıya görünür.
- [ ] Tek `Turn` bileşeni: konuşan, aşama mührü, "X'e cevap" zinciri, token/maliyet/gecikme.
      Stage 1 kart ızgarası, Stage 2 sıralama chip'leri, karar kartı üstte.
- [ ] Debate'te tur içi model başına akış ve durum noktaları.
- [ ] MCP'den gelen işler `/message/stream` veya ortak arka plan yolu üzerinden çalışsın:
      canlı thinking, sidebar'da "canlı" ve "MCP" etiketi, SSE keepalive.
- [x] "Masa" görünümü: `RoundTableView.jsx` hem Council Deliberation hem Chat Rosters
      sekmesinde. Elips masa, koltuk başına SVG koltuk + yuvarlak ajan jetonu + kitap, boş
      sandalyeler (8'e kadar, tıklayınca `AddSeatPanel`), şef/lider masanın başında, dışarıdaki
      şef için "CH" koltuğu. Liste görünümü ve Table/List geçişi kaldırıldı (karar: yalnız masa).
      Koltuk editörleri: Round Table `SeatEditor` (`RosterSeatCard.jsx`), Council
      `CouncilSeatEditor` (`CouncilSeatEditor.jsx`; council koltuğunda rol prompt'u ve MCP yok).
- [~] Model Studio yeniden yapılanma (karar verildi). Yapıldı: Providers `ProvidersTab.jsx` olarak
      ayrıldı ve Settings'e "Providers" sekmesi olarak taşındı (Settings'te "koltuğa ekle"
      düğmeleri yok). Sekmeler 4'e indi (Council, Round Table, Skills & Tools alt sekmeli, Agents;
      `activeTab` değerleri aynı, `mcp` Skills'in alt görünümü). Kalan: ConfigPanel'in geri kalanını
      böl, Agents sekmesinin içeriği (aşağıdaki persona maddesi). Hedef: 4 sekme: **Council**, **Round Table**,
      **Skills** (MCP ikinci alt sekme, "Tools"), **Agents** (persona). **Custom Providers
      Model Studio'dan çıkar, Settings'e "Providers" sekmesi olarak taşınır** (altyapı ayarı,
      koltukla ilgisi yok). Başlık "Model Studio". ConfigPanel (3000+ satır) bu sırada bölünür.
- [~] Agent Personas (Türkçe kalıntılar ve base64 gizleme yapıldı; kalan: persona avatarı
      masadaki monogramın yerine geçsin). Eski metin: Türkçe kalıntılar ("MODELLER", "TEMA & SOHBET RENGI", "PROFIL RESMI")
      İngilizceye; avatar alanındaki ham base64 gizlenir (önizleme + yükle/sil); persona avatarı
      masadaki monogramın yerine kullanılır.
- [ ] MCP Servers boş durum: Library öne, elle ekleme formu "Advanced" altında katlı.
- [ ] Settings (Deliberation Settings): her ayara tooltip, kısaltmalar (CoT, DQ) açıklanır,
      sekme/etiket adları sadeleşir; Providers sekmesi buraya gelir.
- [ ] Masa cilası (isteğe bağlı): küçük ekran düzeni, klavye ile koltuk gezinmesi.
- [ ] `design/DESIGN-DNA.md` kodla uyumsuz (belge obsidian + brass + Syne, kod Electric Azure
      + Google/OpenAI Sans): belgeyi koda göre güncelle.
- [ ] Design-DNA ihlalleri (emoji/sembol simgeler, sabit renkler) temizlenir; ölü kod silinir.

## Aşama 5: Persona ve sistem promptları

- [ ] Claude shim: `--system-prompt`, `--safe-mode`, `--tools ""`, boş geçici çalışma dizini.
      Antigravity shim: boş dizin, `--disable-slash-commands`, nötr ajan/önsöz. Gerçek
      çağrıyla davranış doğrulanır.
- [ ] `format_roundtable_prompt`: mühendis/lead-architect dili kalkar, nötr sohbet asistanı
      rolü; anti-yalakalık yumuşatılır.
- [ ] Yetenek farkındalığı: prompt'a o turda gerçekten açık olan araçlar ve girdiler eklenir.
- [ ] Varsayılan roster ve sohbet prompt'ları nötr yeniden yazılır; eski kayıtlar için
      migrasyon ve "varsayılana sıfırla".
- [ ] `persona: chat | engineering` ayarı ve etkin prompt önizlemesi.
- [ ] `model@skill` dekorasyonu sohbet moduna uyarlanır; workspace dossier sistem prompt'u
      yerine kullanıcı tarafı bağlama taşınır.

## Genel ekler (aşamalara sığdıkça)

Mesaj/sohbet maliyet göstergesi, sohbet dışa aktarma ve tam metin arama, mesajı düzenleme ve
dallandırma, denetim kaydı (araç çağrıları, ayar değişiklikleri), sağlık sayfası
(provider/shim/SearXNG/MCP), shim kur/güncelle betiği, dokümanların güncellenmesi.

## MCP Mağazası aday listesi

Paket adları ve lisanslar eklemeden önce tek tek doğrulanır.

- **Araştırma:** SearXNG MCP, Crawl4AI veya Firecrawl (self-host), arXiv, Semantic Scholar,
  Wikipedia, YouTube transcript.
- **Dosya anlama:** MarkItDown veya Docling (PDF/Office/görsel -> markdown).
- **Hesaplama:** ağsız Docker sandbox'ında Python çalıştırma, grafik (chart) MCP.
- **Bilgi:** Context7 (güncel kütüphane dokümanı), Memory, Sequential Thinking, vault araması.
- **Geliştirici (varsayılan kapalı):** GitHub, Playwright, Filesystem (salt-okunur).

## Aşama 1'de yapılanlar

- `backend/netguard.py`: `web_fetch` ve skill içe aktarma için SSRF koruması (DNS doğrulama,
  IP pinleme, elle redirect, 2 MB / 500 KB gövde sınırı, content-type allowlist).
- `workspace_read_file` yol sınırı + deny listesi; Round Table varsayılanında workspace araçları kapalı.
- `SafeMarkdown`: model çıktısındaki resimler otomatik yüklenmez, bağlantı olarak görünür.
- `PUT /api/config` oku-birleştir, atomik yazım; `_prepare_messages_for_model` hata dalı.
- Skill id'si klasör adı; enjekte edilen skill metni 8000 karakterle sınırlı.
- `backend/limits.py`: 2 MB istek gövdesi sınırı (413) ve pahalı POST uçlarına dakikada 60
  istek (429; `MAX_REQUEST_BODY_BYTES`, `COSTLY_RATE_LIMIT_PER_MINUTE`). Yükleme ucu Aşama 3'te
  gelince kendi sınırını alır.
- `test_no_secret_leak.py`: tüm `GET` yanıtlarında yapılandırılmış sırlar ve anahtar desenleri aranır.
- Shim'ler liste biçimli içeriği metne düzleştirir (resimler `[image omitted]`).
- Frontend: `loadConversation` eski yanıtı atar, sohbet başına polling zamanlayıcısı.
- `GET /conversations/{id}` çalışan deliberation'ı `idle` yapmaz (`is_deliberation_running`).

## Aşama 2a'da yapılanlar

- `backend/tools/search.py`: `searxng_search` (kapalı/erişilemezse `None`, çağıran HN/DDG'ye düşer),
  `paper_search` (arXiv + OpenAlex, biri çökse diğeri döner), `wikipedia` (dil kodu doğrulanır).
- `web_search` önce SearXNG'yi dener. `council-searxng` servisi yayınlanmış port olmadan
  (`infra/searxng/settings.yml`, JSON formatı açık); `SEARXNG_SECRET` env ile değiştirilebilir.
- `paper_search`/`wikipedia` Round Table varsayılanında ve research tarzı skill'lerde açık.
- Kalan Aşama 2: shim protokolü, MCP, UI.

## Aşama 2b'de yapılanlar

- `backend/tools/executor.py`: `run_tool_loop` (varsayılan 6 tur, 10 çağrı, 90 sn, araç başına
  30 sn; aynı çağrı tekrarında önbellekten cevap + uyarı; bozuk JSON argüman modele hata olarak
  döner; bütçe dolunca araçsız son tur). Araç çıktısı "güvenilmeyen veri" çerçevesiyle ve
  12000 karakterle sınırlı modele gider. `on_event` ile `tool_call`/`tool_result`/`tool_limit`.
  `run_agentic_tool_loop` (council koltukları) ince sarmalayıcı.
- Round Table işçisi döngüyü kullanır; döngünün ürettiği cevabı tekrar sorgulamaz (eskiden
  araç çağrısı olmasa bile ikinci kez üretiliyordu). Yeni SSE olayları: `roundtable_tool_result`,
  `roundtable_tool_limit`; kaydedilen mesajdaki `tools_executed` artık `ok`, `sources`,
  `duration_ms` taşır. `target_workspace` artık araca gerçekten ulaşır.
- Bilinen eksik: araç kullanan cevap token token akmaz, tek parça gelir (döngü akışsız
  sorgular). Kaynaklar mesajdaki `sources` alanına yazılır ve `roundtable_model_complete` olayında gelir.

## Aşama 2c'de yapılanlar

- `backend/tools/webcontent.py`: stdlib ile HTML -> markdown (`<main>`/`<article>` öncelikli;
  nav/footer/aside/form/script atılır; bağlantılar mutlak URL; liste, kod, tablo), `pypdf` ile PDF
  (ilk 40 sayfa, 10 MB sınırı, şifreli veya taranmış PDF için açık hata), 15 dk / 64 kayıt
  bellek önbelleği.
- `web_fetch` sayfalar: `start_index` ve "şu değerle devam et" notu; varsayılan 6000, en çok
  20000 karakter.
- Güvenlik: `execute_tool` `web_fetch`'i önce harici fetch MCP sunucusuna yolluyordu; bu
  `netguard` SSRF korumasını atlıyordu. Kaldırıldı, regresyon testi var.
- Yeni bağımlılık: `pypdf` (imaj yeniden build edildi).

## Aşama 2d'de yapılanlar

- `backend/tools/mcp_client.py` (`mcp==2.2.0`; 2.x API'si 1.x ile uyumsuz, `MCPServer`,
  `streamable_http_client`, snake_case alanlar). Depo `data/mcp_servers.json` (0600, atomik).
  HTTP ve stdio taşıması; her işlem (keşif, çağrı) kendi bağlantısını açıp kapatır, yani
  süreç/oturum ömrü yönetimi yok, bedeli stdio'da çağrı başına süreç başlatmak.
- Varsayılan-reddet: keşfedilen her araç `deny` başlar; `auto` (serbest) ve `ask` (her çağrı
  onay) kullanıcı tarafından açılır. Kapalı/silinmiş sunucu ve bilinmeyen araç `deny` sayılır.
  Araç adı `mcp__<sunucu>__<araç>`; 64 karakteri aşan adlar atlanır (kesmek iki aracı aynı
  politikaya çökertirdi).
- stdio sunucusu backend ortamında komut çalıştırır: `MCP_ALLOW_STDIO=1` yoksa eklenemez ve
  çalışmaz. Headers/env değerleri API'de asla dönmez (`headers_set`, `env_set` yalnız adları
  verir); PUT'ta boş değer siler, verilmeyen ad korunur. Konteynerde `npx` yok, stdio
  sunucuları için node'lu imaj gerekir; HTTP sunucuları şimdiden çalışır.
- Onay akışı: `ask` araçta döngü `tool_approval_required` (Round Table'da
  `roundtable_tool_approval`, `approval_id` ile) olayı yollar ve `POST /api/mcp-approvals/{id}`
  `{"approve": bool}` yanıtını bekler; 120 sn zaman aşımı, dinleyici yoksa veya iptalde ret.
- MCP sonuçları döngü önbelleğine girmez: aynı argümanlı tekrar çağrı politikadan ve onaydan
  yeniden geçer, yan etkili araç iki kez onaysız çalışmaz. Yenilemede bir aracın açıklaması
  veya şeması değişmişse (parmak izi) politikası `deny`'a döner ve `definition_changed`
  işaretlenir; sunucunun sonradan eklediği metin modele onaysız ulaşmasın diye. Bozuk
  `mcp_servers.json` yazma yollarında hata verir, boş depoyla üzerine yazılmaz. Hata metinleri
  URL kimlik bilgisi ve sorgu değerinden arındırılır. Sunucu kimliğinde `__` yasak.
- MCP araçları yalnız Round Table'a verilir (skill'li council koltuklarına henüz değil).
- Bilinen eksik: HTTP sunucu URL'leri için SSRF koruması yok (yerel MCP sunucuları
  çalışsın diye); kimlik doğrulamalı çok kullanıcılı kurulumda onay kimlikleri sohbetten
  bağımsız global. Mağaza ve UI sonraki adım.

## Önceki oturumda yapılanlar

- Provider API anahtarları artık API yanıtlarında dönmüyor (`redact_provider`); düzenlemede
  boş anahtar mevcut anahtarı koruyor; `providers.json` atomik ve sahibine özel yazılıyor.
- Frontend: SSE satırları artık chunk sınırında kaybolmuyor (`readSSE`); yükleme durumu
  sohbet başına tutuluyor (`loadingIds`); tag filtresi Council tamamlanınca silinmiyor; aynı
  mesajın iki kez gönderimi görünüyor; çıplak URL temiz açılış ekranı; hata olayı arayüzü
  "deliberating"de takılı bırakmıyor; landing ekranı akış olaylarıyla ele geçirilmiyor.
- Round Table kimlik kuralındaki `{current_short}`, `{peers_str}`, `{user_name}` artık
  gerçekten doldurulur (f-string hatası).
- Claude shim prompt'u stdin'den alır (128 KB argv sınırı ve `--` ile başlayan prompt'un flag
  sanılması sorunu); iki shim'e gövde boyutu sınırı ve bozuk JSON için 400 eklendi.

## Bilinen açık noktalar

- Round Table'da bir modelin cevabındaki `@model` en fazla 1 hop ile başka bir koltuğu
  tetikleyebilir; web içeriğinden gelen metin bunu kullanabilir (Aşama 2'de tool çıktısı
  güvenilmeyen veri olarak işaretlenince azalır).
- `/api/providers/test` ve `fetch-models` girilen her URL'ye istek atar; public bir kurulumda
  kısıtlanmalı.
