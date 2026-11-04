# World Radio Select

A handpicked international collection of **72 stations in 44 countries/regions**, spanning independent music discovery, rock, jazz, classical, electronic, pop, news, local cultures, and community radio.

**[Subscribe in Primuse — World Radio Select](https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/radio.m3u)**

```text
https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/radio.m3u
```

Open **Primuse → Radio → + → Add Subscription → Fetch → Subscribe**. After changes, tap **Update Now** in Primuse. This is a **standalone subscription**: it does not modify the curated U.S. playlist or the 12-part American directory.

## Selection principles and playback warning

These are editorial selections, **not an objective world ranking**. We favor established national and independent stations, regional diversity, and HTTPS streaming paths without misleading `.mp3.m3u` extensions or short-lived tokens. Candidate URLs were cross-referenced with broadcasters and the [Radio Browser-derived country playlists](https://github.com/AlonDrilich/radio-playlists). Official source documentation is available for [NTS](https://ntslive.freshdesk.com/support/solutions/articles/77000587257-tunein), [FIP](https://www.radiofrance.fr/fip), and [Radio Swiss Jazz](https://www.radioswissjazz.ch/en/reception/internet).

**Verification is pending:** these are documented or directory-listed streams, not 72 streams individually proven audible in Primuse. Playback can fail by region, outage, codec or client; tests from GitHub cannot verify availability from Iraq. The original 36-station U.S. checker does not automatically validate this separate collection. The [World Radio Select Audit](https://github.com/th3cyrus/Apple/actions/workflows/world-radio.yml) now runs automatically on changes and weekly, using FFprobe/FFmpeg to check decoded non-silent audio. It publishes an audit report without removing stations on transient failures.

The four shared U.S. stations reuse this project's original custom cover artwork; other stations have no custom matching artwork yet. Do not mistake these streams for rebroadcast audio hosted by this repository.

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
| Bangkok Community Radio | Thailand | Electronic & Discovery |
| Radyo Eksen | Türkiye | Rock & Alternative |
| TRT FM | Türkiye | Pop & Culture |
| Sharjah Quran Radio | United Arab Emirates | Culture & Religious |

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
- [`stations.json`](stations.json): editable titles, streams, countries, regions and genres.
- [World radio health checker](../scripts/check_world_radio.py): validates the independent playlist and can audit decoded audio.
- [Main curated U.S. collection](../radio.m3u) and [expanded U.S. directory](../us-directory/README.md) remain independent.
