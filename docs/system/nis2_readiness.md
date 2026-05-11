# NIS2 Readiness — MoE Codex

Skeleton mapping for NIS2-Umsetzungsgesetz (NIS2UmsuCG, Stand 2024-2025).
Adressiert "wesentliche" und "wichtige" Einrichtungen gemäß § 8 NIS2UmsuCG.

> **Status:** Skeleton. Detaillierte Risiko-Maßnahmen-Tabellen folgen
> sobald MoE Codex bei einem ersten betroffenen Operator (z.B. KRITIS-
> Betreiber) deployt wird.

---

## 1. Sektorale Anwendbarkeit

NIS2 erfasst diese Sektoren (Anhang I/II):
- Energie, Verkehr, Banken/Finanzmarkt, Gesundheit, Trinkwasser, Abwasser,
  digitale Infrastruktur, Verwaltung der Informationstechnologie für
  öffentliche Verwaltung, Weltraum, Postdienste, Abfallbewirtschaftung,
  Chemie, Lebensmittelproduktion, Herstellung medizinischer Geräte,
  Verarbeitendes Gewerbe (kritische Subsektoren), digitale Dienste,
  Forschung.

Wenn der Operator in einem dieser Sektoren tätig ist UND die Größenklasse
(typisch ≥ 50 MA / ≥ 10 Mio. € Umsatz; KRITIS unabhängig der Größe) erfüllt:
NIS2-Pflicht.

---

## 2. Anforderungs-Mapping

### § 30 NIS2UmsuCG — Risikomanagementmaßnahmen

| Anforderung | Erfüllt durch |
|---|---|
| (1) Konzept Risikoanalyse + Informationssicherheit | TODO — Operator-Pflicht; codex liefert Bausteine |
| (2) Bewältigung von Sicherheitsvorfällen | Drift-Events + Kafka-Audit-Trail + Falco (Phase D.3.4) |
| (3) Aufrechterhaltung Betrieb (Backup/Restore) | `scripts/migrate-from-sovereign.sh` als Vorlage |
| (4) Sicherheit der Lieferkette | `audit-licenses.sh` + `license_compliance.md` |
| (5) Sicherheit bei Erwerb/Entwicklung/Wartung | Apache-2.0-Quelloffenheit |
| (6) Wirksamkeitsbewertung | `pytest`-Suite + Drift-Detection als laufende Wirksamkeitsprüfung |
| (7) Grundlegende Cyberhygiene + Schulung | Operator-Pflicht |
| (8) Kryptographie | TLS via Caddy; Authentik-Sessions; lakeFS-Encryption |
| (9) Personalsicherheit + Zugangskontrolle + Anlagenverwaltung | Authentik + OPA (Phase D.1.1) |
| (10) Multi-Faktor-Auth + Notfallkommunikation | Authentik 2FA |

### § 32 NIS2UmsuCG — Meldepflichten

| Frist | Pflicht | Codex-Unterstützung |
|---|---|---|
| 24 h | Frühwarnung an BSI | Alerting-Pfad: Drift-Event `severity: crit` → Falco-Alert → SIEM |
| 72 h | Vollständige Meldung | Marquez-Events + Drift-Events liefern Forensik |
| 1 Monat | Abschlussbericht | Audit-Trail via lakeFS-Commit-History |

---

## 3. Maintenance contract

Update-Trigger:
- BSI gibt NIS2-Umsetzungs-Konkretisierungen heraus
- Neue Cybersecurity-Standards (z.B. ISO 27001:202X-Revision)
- Operator meldet konkrete Audit-Anforderung
- Codex erweitert sich um audit-relevante Komponenten (z.B. OPA-Policy-Engine)

Diese Page ist Skeleton — die `TODO:`-Markierungen werden in der
Phase-2-Erweiterung systematisch ergänzt.
