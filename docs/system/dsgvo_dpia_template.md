# DSGVO DPIA — Template (Datenschutz-Folgenabschätzung)

This page is a **DPIA template** under Art. 35 DSGVO for operators
deploying MoE Codex. It is structured as a Markdown form: copy this
file into your internal compliance repo, fill in each section, and have
the data-protection officer sign off.

> **Form, not record.** This file in the moe-codex repo is the
> empty template. Filled-in DPIAs live in operator-controlled storage
> and must not be checked into this public repo.

---

## 1. Beschreibung des Vorhabens

- **Bezeichnung des Verarbeitungsvorgangs:** _<Use-Case Name>_
- **Verantwortlicher (Operator):** _<Behörde/Unternehmen, Adresse>_
- **Datenschutzbeauftragte/r:** _<Name, Email>_
- **Stand der Bearbeitung:** _<YYYY-MM-DD, Version>_

### 1.1 Zweck der Verarbeitung
_<Konkrete Beschreibung — keine generische "KI-Unterstützung", sondern
"Vorprüfung von Bauanträgen", "Recherche zu pharmazeutischen
Nebenwirkungen", "Polizei-Lagebild zu organisierter Kriminalität" o.ä.>_

### 1.2 Rechtsgrundlage
- [ ] Art. 6 Abs. 1 lit. a (Einwilligung)
- [ ] Art. 6 Abs. 1 lit. b (Vertragserfüllung)
- [ ] Art. 6 Abs. 1 lit. c (rechtliche Verpflichtung) — _<welche?>_
- [ ] Art. 6 Abs. 1 lit. e (öffentliches Interesse) — _<welches?>_
- [ ] Art. 6 Abs. 1 lit. f (berechtigtes Interesse) — _<Interessen­abwägung beilegen>_
- [ ] Art. 9 Abs. 2 (besondere Kategorien) — _<welche Ausnahme?>_

### 1.3 Betroffene Personenkreise
_<z.B. Antragsteller, Patienten, Verdächtige, Beschäftigte; Anzahl absolut
und prozentual aller deutschen/EU-Bürger>_

### 1.4 Datenkategorien
- [ ] Stammdaten (Name, Anschrift, Geburtsdatum)
- [ ] Kontaktdaten (Email, Telefon)
- [ ] Vertragsdaten
- [ ] Gesundheitsdaten (Art. 9 DSGVO)
- [ ] Strafrechtliche Daten (Art. 10 DSGVO)
- [ ] Biometrische Daten (Art. 9 DSGVO)
- [ ] Sonstige besondere Kategorien _<welche?>_
- [ ] Anonymisierte/Pseudonymisierte Daten

---

## 2. Verarbeitungs-Operationen in MoE Codex

| Schritt | Komponente | Daten-Bezug |
|---|---|---|
| 2.1 Eingang von Daten | Bundle-Import via `/v1/codex/approval/import/pending` | Datenfluss in lakeFS-Branch (verschlüsselt auf MinIO) |
| 2.2 Admin-Prüfung | `/approval` Page | Daten sichtbar für Admin-Rolle (Authentik OIDC, 2FA verpflichtend) |
| 2.3 Approval-Entscheidung | `/v1/codex/approval/.../approve` | Auf Klick: Bundle nach Neo4j (moe-sovereign) + lakeFS-Merge |
| 2.4 Lineage-Aufzeichnung | Marquez | Audit-Trail: wer hat wann was approved |
| 2.5 Drift-Erkennung | `services/data_health` | Statistische Auffälligkeiten — keine PII |
| 2.6 Catalog-Anzeige | `/catalog` | Aggregierte Metadaten, keine Roh-Inhalte |
| 2.7 Investigative Suche | Cypher Explorer (moe-sovereign) | Read-only, Zugriff per RBAC |
| 2.8 Löschung | `lakefs branch delete` + Neo4j-Delete-Skript | Operator-Aufgabe; Codex liefert die Werkzeuge |

---

## 3. Notwendigkeit und Verhältnismäßigkeit

- **Eignung:** _<Warum löst MoE Codex das konkrete Problem besser als eine
  Alternative?>_
- **Erforderlichkeit:** _<Welche milderen Mittel wurden geprüft? Warum
  reichen Excel, manuelle Sichtung, regelbasierte Filter nicht?>_
- **Angemessenheit:** _<Steht der Aufwand für die Betroffenen im
  Verhältnis zum Verarbeitungszweck?>_

---

## 4. Risikobewertung für die Rechte der Betroffenen

### 4.1 Identifizierte Risiken

| # | Risiko | Eintrittswahrscheinlichkeit | Schweregrad |
|---|---|---|---|
| 1 | Unbefugter Zugriff auf Bundle-Inhalte vor Approval | _<niedrig/mittel/hoch>_ | _<niedrig/mittel/hoch>_ |
| 2 | Falsche Approval-Entscheidung führt zu falschem Eintrag im Wissensgraph | _<…>_ | _<…>_ |
| 3 | Drift-Event-Logs enthalten unerwartet PII | _<…>_ | _<…>_ |
| 4 | Lineage-Daten in Marquez werden für Profiling missbraucht | _<…>_ | _<…>_ |
| 5 | Sovereignty-Bruch: Daten verlassen die EU | _<…>_ | _<…>_ |
| 6 | _<weitere Use-Case-spezifische Risiken>_ | | |

### 4.2 Technische und organisatorische Maßnahmen

| Risiko | Maßnahme | Wo in MoE Codex |
|---|---|---|
| 1 | Authentik-OIDC mit 2FA, RBAC, Marking-Layer (OPA Phase D.1.1) | `services/auth` in sovereign, `routes/approval` in codex |
| 2 | Approval-Workflow zweistufig (Vier-Augen-Prinzip) — Operator-Konfiguration | konfigurierbar im Approval-Plugin |
| 3 | Drift-Logs enthalten nur aggregierte Metriken (compute_drift Output) | `services/data_health.compute_drift` |
| 4 | Marquez-Zugriff nur für Admin-Rolle; keine PII in Lineage-Events | OPA-Policy konfigurierbar |
| 5 | EU-Host-Pflicht im Operator-Vertrag; siehe `eu_sovereignty_charter.md` | Plattform-Constraint |

### 4.3 Restrisiko

_<Wenn nach allen Maßnahmen noch hohes Restrisiko: Konsultation der
Aufsichtsbehörde gemäß Art. 36 DSGVO nötig. Sonst: Begründung warum
Restrisiko vertretbar ist.>_

---

## 5. Mitwirkende und Freigabe

| Rolle | Name | Unterschrift | Datum |
|---|---|---|---|
| Operator (Verantwortlicher) | _<>_ | _<>_ | _<>_ |
| Datenschutzbeauftragte/r | _<>_ | _<>_ | _<>_ |
| IT-Sicherheitsbeauftragte/r | _<>_ | _<>_ | _<>_ |
| Fachbereichsleitung | _<>_ | _<>_ | _<>_ |

---

## 6. Überprüfungsturnus

- **Erst-DPIA:** _<vor Inbetriebnahme>_
- **Reguläre Review:** jährlich oder bei wesentlicher Änderung (Art. 35 Abs. 11)
- **Trigger für Ad-hoc-Review:**
  - Neue Datenkategorie wird hinzugefügt
  - Neue Empfänger-Kategorie (z.B. neuer Mandant, Bundesland)
  - Schwerwiegender Datenschutzvorfall
  - Wesentliches Update von MoE Codex (Major-Release)

---

## 7. Verweis auf AI-Act-Risikoklassen-Mapping

Falls das Vorhaben unter den EU AI Act fällt: zusätzlich
[`eu_ai_act_mapping.md`](eu_ai_act_mapping.md) ausfüllen und beilegen.
Die DPIA gemäß DSGVO ist mit der Risk-Assessment gemäß Art. 9 AIA
strukturell kompatibel — wir empfehlen ein zusammenhängendes Dokument.

---

*Diese Vorlage ist Stand der Technik 2026-05; sie ersetzt keine Rechtsberatung. Operator konsultiert eigene Compliance-Abteilung und ggf. die zuständige Aufsichtsbehörde.*
