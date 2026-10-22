# Post draft (LinkedIn / Medium)

Author: Vinicius Baccarini · Repository link: `<GITHUB-REPO-URL — added by Vini in T-40>` · Images: `docs/img/01-overview.png`
(cover), `03-songs.png`, `04-albums.png`, `06-sphere.png`, `drill-show.gif`.

All numbers come from the Gold build of 2026-10-22 and were reproduced in T-SQL and DAX (`docs/run-log.md`).

---

## Português

**50 anos de U2 ao vivo em um pipeline no Microsoft Fabric: o que os dados mostram**

Juntei 1.874 shows do U2, de 1976 a 2026, com dados do setlist.fm e do MusicBrainz, e montei um projeto de ponta a
ponta no Microsoft Fabric: lakehouses Bronze e Silver em PySpark, um warehouse Gold em T-SQL, um modelo semântico
Direct Lake e um relatório Power BI de nove páginas.

Três coisas que os dados mostram:

🎸 **Dez músicas são 29% de tudo o que o U2 já tocou ao vivo.** São 304 músicas diferentes, mas as dez mais tocadas
somam 8.624 de 29.366 execuções. *I Will Follow*, do primeiro disco (1980), lidera: 1.065 vezes, em 1.004 dos 1.874
shows.

💿 **Os discos dos anos 80 nunca saíram do setlist.** Músicas dos seis álbuns de estúdio dos anos 80 (de Boy a
Rattle and Hum) são 54% de tudo o que foi tocado na carreira, e ainda 43% dos setlists das turnês de 2015 a 2019. Na
turnê de aniversário de The Joshua Tree, em 2017, chegaram a 70%.

🌐 **Na Sphere, um álbum carregou a noite.** Nas 40 noites em Las Vegas (2023-24), Achtung Baby foi 54% de cada show,
contra 14% nas turnês de 2015 a 2019. Os shows tinham quase o mesmo tamanho (22,1 músicas contra 23,4), mas saíam de
um repertório de 39 músicas em vez de 89.

O que deu mais trabalho não foi o gráfico, foi a confiança no número:
- ligar os nomes das músicas no setlist.fm às obras do MusicBrainz (99,97% das execuções mapeadas, cada caso duvidoso
  revisado à mão);
- reconstruir o Gold inteiro em uma transação, com checagens que desfazem tudo se algo falhar;
- reproduzir cada número duas vezes, em T-SQL no warehouse e em DAX no modelo, e conferir três deles direto nas
  páginas do setlist.fm.

Fiz o projeto com o Claude Code, usando três agentes (engenharia de dados, análise e design do dashboard), cada um
com suas regras e especificações. O código, as especificações e o relatório estão no GitHub: `<link>`

Dados: setlist.fm (uso não comercial) e MusicBrainz. Projeto de fã, sem vínculo com o U2.

#MicrosoftFabric #PowerBI #DataEngineering #DataAnalytics #U2

---

## English

**50 years of U2 live in a Microsoft Fabric pipeline: what the data shows**

I collected 1,874 U2 shows, from 1976 to 2026, from setlist.fm and MusicBrainz and built an end-to-end project in
Microsoft Fabric: Bronze and Silver lakehouses in PySpark, a Gold warehouse in T-SQL, a Direct Lake semantic model and
a nine-page Power BI report.

Three things the data shows:

🎸 **Ten songs make up 29% of everything U2 has played live.** There are 304 different songs, but the ten most played
add up to 8,624 of 29,366 performances. *I Will Follow*, from the 1980 debut, leads: 1,065 times, at 1,004 of the
1,874 shows.

💿 **The 1980s albums never left the setlist.** Songs from the six 1980s studio albums (Boy to Rattle and Hum) are 54%
of everything played across the career, and still 43% of the setlists on the 2015-2019 tours. On the 2017 Joshua Tree
anniversary tour they reached 70%.

🌐 **At the Sphere, one album carried the night.** Across 40 nights in Las Vegas (2023-24), Achtung Baby was 54% of
each show, against 14% on the 2015-2019 tours. Shows were about as long (22.1 songs against 23.4) but drew on 39
different songs instead of 89.

The hard part was not the charts, it was trusting the numbers:
- matching setlist.fm song names to MusicBrainz works (99.97% of performances mapped, every doubtful case reviewed by
  hand);
- rebuilding the whole Gold layer in one transaction, with checks that roll everything back if one fails;
- reproducing every number twice, in T-SQL on the warehouse and in DAX on the model, and checking three of them
  directly against setlist.fm pages.

I built it with Claude Code, using three agents (data engineering, analysis and dashboard design), each with its own
rules and specs. Code, specs and the report are on GitHub: `<link>`

Data: setlist.fm (non-commercial use) and MusicBrainz. Fan project, not affiliated with U2.

#MicrosoftFabric #PowerBI #DataEngineering #DataAnalytics #U2
