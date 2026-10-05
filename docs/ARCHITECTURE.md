# Architecture et maintenance

Clair est une application Windows avec interface web locale, API FastAPI et
traitements audio/LLM dans des threads. Aucun service d'inférence tiers n'est requis.

## Organisation

| Élément | Responsabilité |
| --- | --- |
| `app.py` | Routes locales, session/jeton, import en flux, contrôle des tâches et capture |
| `core.py` | Stockage des réunions, extraction audio, Whisper, capture et génération des rapports |
| `catalog.py` | Installation et reprise des GGUF, contrôle d'intégrité et préférences |
| `models-catalog.json` | Catalogue, révisions fixées, tailles et SHA-256 des fichiers |
| `prepare.py` | Téléchargement des composants et modèles initiaux |
| `launch.py`, `Lancer.cmd` | Démarrage local et diagnostics |
| `web/` | Interface HTML/CSS/JavaScript sans compilation |
| `tests/` | Tests unitaires et API sans modèles réels |

## Traitement d'une réunion

```text
Média importé ou capture PC + micro
  -> extraction / assemblage audio 16 kHz
  -> Whisper large-v3 (CPU int8 ou GPU float16)
  -> segments horodatés + TXT/SRT
  -> découpage de la transcription
  -> rapports intermédiaires JSON avec le GGUF sélectionné
  -> consolidation du compte rendu
  -> exports Markdown/JSON
```

Les réunions utilisent un identifiant hexadécimal de 16 caractères et un dossier
distinct. Les changements de métadonnées sont écrits dans un fichier temporaire
puis remplacés. Les tâches interrompues au redémarrage peuvent être relancées.
Une seule transcription/capture est autorisée à la fois ; les téléchargements
de modèles peuvent s'effectuer séparément.

L'import sélectionné dans le navigateur utilise la boucle locale et un stockage
par morceaux. Il ne charge pas toute la vidéo en mémoire. Un import par chemin
lit directement la source. Les captures produisent `system.wav` et `mic.wav`,
puis un assemblage destiné à Whisper.

## Génération des résumés

llama.cpp écoute sur `127.0.0.1:8788`, avec clé éphémère et interface web désactivée.
Le moteur reçoit la transcription et une contrainte de sortie JSON correspondant
au schéma Pydantic du rapport. Les prompts distinguent décisions et propositions
et demandent des extraits justificatifs. Les horodatages qui ne correspondent pas
aux segments sont supprimés. Ces contrôles ne garantissent pas l'exactitude du fond.

Le moteur est arrêté après traitement. Le CPU utilise son propre binaire avec
zéro couche GPU et aucun déport sur GPU. Le moteur GPU ajuste la répartition
des couches à la mémoire disponible. Les modèles multimodaux du catalogue sont
utilisés uniquement avec le texte de la transcription.

## Accès local

L'API vérifie les noms d'hôte et origines autorisés, une session locale HttpOnly
et un jeton pour les mutations. Les exports sont limités aux noms prévus et les
identifiants de réunion sont validés. Le service n'est pas conçu pour être exposé
sur un réseau ou derrière un serveur public.

## Mise à jour du catalogue

Pour ajouter une entrée, vérifier la fiche du modèle et sa compatibilité avec
le moteur, puis renseigner dans `models-catalog.json` : identifiant stable, nom,
fichier GGUF unique, dépôt, révision, taille exacte, SHA-256 publié et date de
sortie vérifiée. Ne pas utiliser la date de mise à jour de la quantification
comme date de sortie du modèle original. Le code ne permet pas à une requête API
de fournir une URL arbitraire de téléchargement.

`legacy: true` conserve une entrée pour les anciennes réunions sans la montrer
dans le catalogue. Pour les modèles capables de raisonnement, `no_thinking: true`
active le mode de réponse directe du moteur. Valider réellement une sortie JSON
avec le modèle avant de le considérer comme testé.

## Installation et maintenance

Les versions Python sont fixées dans `requirements.lock.txt`. Les moteurs sont
les archives Windows de llama.cpp **b11408**, le runtime autonome est Python
**3.12.10**. Les téléchargements GGUF du catalogue utilisent une révision précise
et vérifient le SHA-256 avant activation. Les composants téléchargés sont exclus
du dépôt. Le lanceur ne dépend pas de Codex.

La CI teste le code sans modèles ni GPU. Une modification des moteurs, prompts,
formats ou modèles doit aussi être vérifiée par une inférence réelle et une
relecture du résultat. Les tests de substitution ne prouvent pas la compatibilité
de toutes les architectures de modèles.
