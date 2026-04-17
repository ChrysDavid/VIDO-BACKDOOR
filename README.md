# VIDO Admin

Application desktop de démonstration des risques d'accès à distance, réalisée dans le cadre d'un projet académique en cybersécurité.

> **Usage strictement académique et en environnement de laboratoire contrôlé.**

---

## Architecture

```
VIDO ADMIN/
└── VidoAdmin/
    ├── main.py               # Point d'entrée (panel admin)
    ├── config.py             # Configuration serveur (host, port, token)
    ├── assets/
    │   └── logo.png
    ├── agent/
    │   ├── agent.py          # Agent à déployer sur les machines cibles (labo)
    │   └── requirements.txt
    ├── core/
    │   ├── protocol.py       # Types de messages + actions (35+)
    │   ├── server.py         # Serveur TCP multi-agents
    │   └── agent_manager.py  # Pont serveur ↔ interface graphique
    └── gui/
        ├── app.py
        ├── splash.py
        ├── main_window.py
        └── panels/
            ├── agents_panel.py    # Liste + détails des agents connectés
            ├── actions_panel.py   # 33 actions en 6 catégories
            └── terminal_panel.py  # Terminal interactif avec auto-complétion
```

---

## Prérequis

- Python 3.11+
- Dépendances panel admin :

```
customtkinter
Pillow
```

- Dépendances agent :

```
Pillow
psutil
```

---

## Lancement

### 1. Panel admin (machine de contrôle)

```bash
cd VidoAdmin
pip install customtkinter Pillow
python main.py
```

### 2. Agent (machine cible du labo)

```bash
cd VidoAdmin/agent
pip install -r requirements.txt
python agent.py
```

Par défaut l'agent se connecte à `127.0.0.1:32000`. Pour pointer vers une autre machine :

```bash
python agent.py --host 192.168.1.10 --port 32000
```

---

## Configuration

Modifier `VidoAdmin/config.py` :

```python
HOST       = "0.0.0.0"   # Interface d'écoute du serveur
PORT       = 32000
AUTH_TOKEN = "vido-lab-2024"
MAX_AGENTS = 50
```

---

## Actions disponibles (33)

| Catégorie | Actions |
|-----------|---------|
| **Système** | Infos système, Processus, Services, Utilisateurs, Variables env., Uptime, Disques, Logiciels installés |
| **Écran** | Capture d'écran, Presse-papiers, Fenêtre active |
| **Fichiers** | Lister répertoire, Télécharger, Rechercher fichier, Fichiers récents, Hash SHA256, Lire fichier |
| **Réseau** | Interfaces réseau, Ports en écoute, Connexions actives, Résolution DNS, Ping cible, Table ARP |
| **Shell** | Commande shell, Historique, Identité (whoami), Répertoire courant |
| **Sécurité** | Démarrage, Tâches planifiées, Profils WiFi, Pare-feu, Antivirus, Journaux système, Ping agent |

---

## Protocole réseau

Communication TCP avec framing 4 octets (big-endian) + JSON :

```
[4 bytes: longueur] [N bytes: JSON]
```

Séquence de connexion :

```
Agent  →  AUTH {token}
Server →  AUTH_OK
Agent  →  SYSINFO {hostname, os, cpu, ram, ...}
         ← COMMAND {action, params}
         → RESPONSE {action, data}
```
