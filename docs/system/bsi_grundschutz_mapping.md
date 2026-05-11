# BSI-Grundschutz — Baustein-Mapping

Skeleton mapping of MoE Codex components onto BSI-IT-Grundschutz-Bausteine
(Edition 2023). Operators with C5 / ISO-27001 / KritIS audits use this as
a starting point.

> **Status:** Skeleton (2026-05). Bausteine-Inhalte sind noch nicht
> vollständig kommentiert — `TODO:` Markierungen kennzeichnen offene
> Stellen, die im konkreten Operator-Kontext ergänzt werden müssen.

---

## ISMS-Schicht

| Baustein | Relevanz für Codex | Erfüllt durch |
|---|---|---|
| ISMS.1 Sicherheitsmanagement | Operator-Pflicht | TODO |

## ORP-Schicht (Organisation/Personal)

| Baustein | Relevanz | Erfüllt durch |
|---|---|---|
| ORP.4 Identitäts- und Berechtigungsmanagement | Hoch | Authentik OIDC + RBAC; OPA-Marking-Layer (Phase D.1.1) |

## CON-Schicht (Konzeption)

| Baustein | Relevanz | Erfüllt durch |
|---|---|---|
| CON.1 Krypto-Konzept | Hoch | TLS via Caddy; Authentik-Sessions; lakeFS-Secret-Key | 
| CON.3 Datensicherungs-Konzept | Hoch | `migrate-from-sovereign.sh` zeigt Backup-Pfad; Postgres-Dump-Pattern |

## OPS-Schicht (Betrieb)

| Baustein | Relevanz | Erfüllt durch |
|---|---|---|
| OPS.1.1.2 Ordnungsgemäße IT-Administration | Hoch | install.sh + Migrations-Skript + Audit-Skript |
| OPS.1.1.4 Schutz vor Schadprogrammen | Mittel | TODO — Operator-Pflicht (Falco optional in Phase D.3.4) |
| OPS.1.1.5 Protokollierung | Hoch | Marquez-Run-Events, Drift-Events, Kafka `moe.audit` |
| OPS.1.1.6 Software-Tests und -Freigaben | Hoch | pytest 287+/287 grün als Release-Gate |

## APP-Schicht (Anwendungen)

| Baustein | Relevanz | Erfüllt durch |
|---|---|---|
| APP.3.3 Webanwendungen | Hoch | FastAPI mit Pydantic-Validation; Caddy als Reverse-Proxy |
| APP.4.3 Relationale Datenbanksysteme | Hoch | Postgres mit Authentik-Auth; Backup via pg_dump |
| APP.5.3 Big Data | Mittel | Marquez/lakeFS sind Big-Data-adjazent — TODO genauere Verortung |

## SYS-Schicht (IT-Systeme)

| Baustein | Relevanz | Erfüllt durch |
|---|---|---|
| SYS.1.1 Allgemeiner Server | Hoch | Container-Hardening (read-only fs, no-new-privs) |
| SYS.1.6 Containerisierung | Hoch | Docker Compose mit explizitem `cap_drop`, Netzwerk-Isolation |

## NET-Schicht

| Baustein | Relevanz | Erfüllt durch |
|---|---|---|
| NET.3.2 Firewall | Hoch | Operator-Pflicht (Hetzner / IONOS Firewall) |
| NET.3.3 VPN | Mittel | TODO — operator-spezifisch |

## INF-Schicht (Infrastruktur)

Vollständig operator-spezifisch. Hosting-Empfehlungen siehe
[`eu_sovereignty_charter.md`](eu_sovereignty_charter.md).

---

## Maintenance contract

Update-Trigger:
- BSI veröffentlicht neue Bausteine oder Edition
- Operator meldet Mapping-Lücke aus konkretem Audit
- Neuer Codex-Container kommt hinzu → Baustein-Zuordnung dokumentieren

Diese Page ist Skeleton — bei einem konkreten Audit füllt der Operator die
`TODO:`-Markierungen mit Verweisen auf konkrete Konfigurationsdateien
und Verfahrensanweisungen.
