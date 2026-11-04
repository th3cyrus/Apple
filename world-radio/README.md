# World Radio Select

A handpicked international collection of **72 stations in 44 countries/regions**, spanning independent music discovery, rock, jazz, classical, electronic, pop, news, local cultures, and community radio.

**[Subscribe in Primuse — World Radio Select](https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/radio.m3u)**

```text
https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/radio.m3u
```

Open **Primuse → Radio → + → Add Subscription → Fetch → Subscribe**. After changes, tap **Update Now** in Primuse. This is a **standalone subscription**: it does not modify the curated U.S. playlist or the 12-part American directory.

## Selection and monitoring

These are editorial selections, **not an objective world ranking**. We favor established national and independent stations, regional diversity, and HTTPS streaming paths without misleading `.mp3.m3u` extensions or short-lived tokens. Candidate URLs were cross-referenced with broadcasters and the [Radio Browser-derived country playlists](https://github.com/AlonDrilich/radio-playlists). Official source documentation is available for [NTS](https://ntslive.freshdesk.com/support/solutions/articles/77000587257-tunein), [FIP](https://www.radiofrance.fr/fip), and [Radio Swiss Jazz](https://www.radioswissjazz.ch/en/reception/internet).

Audio streams are sampled with FFprobe/FFmpeg on playlist changes and during a weekly [World Radio Select Audit](https://github.com/th3cyrus/Apple/actions/workflows/world-radio.yml). Current results and failure reports are available in GitHub Actions.

**All 72 stations have illustrated covers:** four shared U.S. stations reuse the main collection's existing optimized artwork; the other 68 have unique, reproducible 512×512 PNG tiles in [`logos/`](logos/) with the same frosted-glass design language. The covers display station names and country codes but do not impersonate official broadcaster logos. Missing covers are generated using [`scripts/generate_world_covers.py`](../scripts/generate_world_covers.py), and existing artwork is preserved. The repository links to broadcaster streams without rebroadcasting the audio.

## Radio by language

Language-based subscriptions are separate from the 72-station international selection. Each contains nonreligious broadcasters from relevant countries and services.

| Language | Stations | Subscription |
| --- | ---: | --- |
| [Kurdish](kurdish/README.md) | 7 | [M3U](kurdish/radio.m3u) |
| [Persian](persian/README.md) | 9 | [M3U](persian/radio.m3u) |
| [Arabic](arabic/README.md) | 14 | [M3U](arabic/radio.m3u) |
| [Turkish](turkish/README.md) | 14 | [M3U](turkish/radio.m3u) |
| [Russian](russian/README.md) | 13 | [M3U](russian/radio.m3u) |
| [English](english/README.md) | 10 | [M3U](english/radio.m3u) |
| [French](french/README.md) | 5 | [M3U](french/radio.m3u) |
| [German](german/README.md) | 5 | [M3U](german/radio.m3u) |
| [Spanish](spanish/README.md) | 6 | [M3U](spanish/radio.m3u) |

## Selected stations

### Europe (31)

| Station | Country | Focus |
| --- | --- | --- |
| FM4 | Austria | Alternative & Electronic |
| RTBF Classic 21 | Belgium | Classic Rock |
| RTBF Musiq3 | Belgium | Classical & Culture |
| NOVA FM Denmark | Denmark | Pop & Contemporary |
| FIP | France | Eclectic & Jazz |
| FIP Jazz | France | Jazz |
| France Inter | France | News & Culture |
| ByteFM | Germany | Music Discovery |
| Deutschlandfunk | Germany | News & Culture |
| Deutschlandfunk Kultur | Germany | Culture & Talk |
| JazzRadio Berlin | Germany | Jazz |
| Pepper 96.6 | Greece | Eclectic & Chill |
| RTÉ Radio 1 | Ireland | News & Culture |
| Radio Capital | Italy | Classic Hits |
| Radio Deejay | Italy | Pop & Entertainment |
| NPO 3FM | Netherlands | Alternative & Pop |
| NPO Radio 2 | Netherlands | Pop & Culture |
| Sublime | Netherlands | Soul & Jazz |
| NRK Klassisk | Norway | Classical |
| NRK P3 | Norway | Pop & Culture |
| Radio Nowy Świat | Poland | Independent & Talk |
| RTP Antena 3 | Portugal | Alternative & Pop |
| TSF Rádio Notícias | Portugal | News & Talk |
| LOS40 Classic | Spain | Classic Hits |
| RNE Radio 3 | Spain | Alternative & Culture |
| Sveriges Radio P3 | Sweden | Pop & Culture |
| Radio Swiss Jazz | Switzerland | Jazz & Blues |
| BBC Radio 6 Music | United Kingdom | Alternative & Discovery |
| BBC World Service | United Kingdom | International News |
| NTS Radio 1 | United Kingdom | Underground & Eclectic |
| NTS Radio 2 | United Kingdom | Underground & Eclectic |

### North America (9)

| Station | Country | Focus |
| --- | --- | --- |
| CBC Music | Canada | Music & Culture |
| CKUA | Canada | Music Discovery |
| Horizonte 107.9 | Mexico | Jazz & Culture |
| KCRW | United States | Eclectic & Culture |
| KEXP | United States | Alternative & Discovery |
| Radio Paradise Main Mix | United States | Eclectic & Rock |
| SomaFM Groove Salad | United States | Downtempo & Chill |
| WFMU | United States | Freeform & Independent |
| WWOZ | United States | Jazz & Roots |

### Caribbean (1)

| Station | Country | Focus |
| --- | --- | --- |
| Irie FM | Jamaica | Reggae |

### South America (4)

| Station | Country | Focus |
| --- | --- | --- |
| Rock & Pop 95.9 | Argentina | Rock & Alternative |
| CBN São Paulo | Brazil | News & Talk |
| Radio Cooperativa | Chile | News & Talk |
| Radio Nacional de Colombia | Colombia | Culture & World |

### Africa (7)

| Station | Country | Focus |
| --- | --- | --- |
| Happy FM Ghana | Ghana | Community & Talk |
| Capital FM Kenya | Kenya | Contemporary Hits |
| Hit Radio Morocco | Morocco | Contemporary Hits |
| Cool FM Lagos | Nigeria | Pop & Culture |
| Nigeria Info Lagos | Nigeria | News & Talk |
| 5FM | South Africa | Pop & Youth |
| Kaya FM | South Africa | Soul & Talk |

### Asia & Middle East (15)

| Station | Country | Focus |
| --- | --- | --- |
| RTHK Radio 3 | Hong Kong | News & Culture |
| Radio Mirchi Hindi | India | Hindi Pop & Bollywood |
| RRI Voice of Indonesia | Indonesia | International & World |
| Kurdistan 24 Radio | Iraq | News & Talk |
| Gensokyo Radio | Japan | Japanese Game & Anime |
| NHK World Radio | Japan | International News |
| Radio Liban | Lebanon | Culture & World |
| Radio alHara | Palestine | Independent & Eclectic |
| Easy Rock Manila | Philippines | Easy Listening |
| CNA938 | Singapore | News & Talk |
| ICRT | Taiwan | English Pop & Talk |
| Chula Radio Plus | Thailand | University & Culture |
| Radyo Eksen | Türkiye | Rock & Alternative |
| TRT FM | Türkiye | Pop & Culture |
| Dubai Eye 103.8 | United Arab Emirates | News, Talk & Sports |

### Oceania (5)

| Station | Country | Focus |
| --- | --- | --- |
| 4ZZZ | Australia | Independent & Community |
| ABC Jazz | Australia | Jazz |
| triple j | Australia | Alternative & Youth |
| 95bFM | New Zealand | Independent & Alternative |
| George FM | New Zealand | Electronic & Dance |

## Files

- [`radio.m3u`](radio.m3u): standalone Primuse-compatible M3U subscription.
- [`logos/`](logos/): 68 project-style custom station covers (other four are shared with the main collection).
- [`stations.json`](stations.json): editable titles, streams, countries, regions and genres.
- [World radio health checker](../scripts/check_world_radio.py): validates the independent playlist and can audit decoded audio.
- [Main curated U.S. collection](../radio.m3u) and [expanded U.S. directory](../us-directory/README.md) remain independent.
