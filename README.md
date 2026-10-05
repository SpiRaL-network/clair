# Clair

**Transcription et comptes rendus de réunions, entièrement sur votre PC Windows.**

Clair importe une vidéo ou un fichier audio, transcrit les paroles avec Whisper,
puis produit un compte rendu en français avec un modèle local. Il peut aussi
enregistrer le son du PC et le microphone pour traiter une réunion après son arrêt.

## Fonctionnalités

- Import MP4, MKV, MOV, WebM, AVI, WMV, MP3, WAV, M4A, FLAC, OGG, WMA et AAC,
  selon les codecs. Sélecteur du navigateur ou chemin de fichier local.
- Transcription horodatée, recherche, lecture audio et exports TXT/SRT.
- Compte rendu : sujets, décisions, propositions, actions et questions ouvertes.
- Catalogue de sept modèles publiés en 2026 : Qwen3.5 2B/4B/9B, Qwen3.8 27B,
  Gemma 4 E2B/E4B/12B. Téléchargements reprenables avec vérification SHA-256.
- Choix du modèle par réunion ; régénération du résumé sans retranscription.
- Traitement automatique, GPU NVIDIA, ou CPU uniquement.
- Capture WASAPI du son du PC et du microphone en pistes séparées.
- Aucun compte ni service d'inférence cloud. Interface sur `127.0.0.1:8787`.

## Installation depuis les sources

Prérequis : **Windows 10/11 64 bits**, **Python 3.12 64 bits** installé depuis
[python.org](https://www.python.org/downloads/windows/), connexion Internet pour
l'installation, et environ **20 Go libres** pour les dépendances, Whisper, le
modèle initial et les moteurs. Les autres modèles et réunions prennent de l'espace
supplémentaire. Un GPU NVIDIA compatible avec les composants CUDA téléchargés
est facultatif ; le CPU reste disponible.

```powershell
git clone https://github.com/SpiRaL-network/clair.git
cd clair
.\Installer.cmd
.\Lancer.cmd
```

`Installer.cmd` crée un environnement Python, installe les versions fixées dans
`requirements.lock.txt`, télécharge Whisper large-v3 et Qwen3.5 4B, puis les moteurs
llama.cpp CPU/GPU et un runtime Python autonome. Aucun modèle ni binaire tiers
n'est inclus dans ce dépôt. `Lancer.cmd` utilise ensuite le runtime local.

Le catalogue s'ouvre dans le menu **Catalogue de modèles**. Les modèles supplémentaires
se téléchargent à la demande. Le catalogue est vérifié au **5 octobre 2026** ; les
révisions et empreintes des fichiers sont fixées dans `models-catalog.json`.

## Utilisation

1. Choisir **Importer un enregistrement** ou **Enregistrer une réunion**.
2. Choisir la langue, le modèle du compte rendu et le mode CPU/GPU.
3. Importer le média, ou sélectionner les périphériques audio utilisés par Teams
   puis démarrer la capture manuellement.
4. Consulter la transcription et le compte rendu ; exporter ou réécouter les passages.

La transcription conserve la langue parlée ; le compte rendu est en français.
Pour changer de modèle après traitement, choisir **Modèle pour le prochain résumé**,
puis **Refaire le résumé**. Le modèle du rapport actuel reste indiqué jusqu'au
remplacement effectif du compte rendu.

Les données sont stockées dans `reunions/`, les modèles dans `models/`, les
préférences dans `settings.json`. Ces fichiers sont exclus de Git.

## Développement et tests

Après installation des dépendances :

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe app.py --no-browser
```

Les **14 tests** s'exécutent sans télécharger de modèles, sans GPU et sans capturer
de périphériques. Les tests d'inférence utilisent des substituts ; les essais réels
CPU/GPU sont documentés dans [docs/VALIDATION.md](docs/VALIDATION.md).
Le workflow GitHub Actions vérifie les sources et les tests sur Windows.

## Limites

La capture démarre manuellement, et la transcription s'effectue après son arrêt.
Clair n'identifie pas les intervenants et ne réalise pas de diarisation.
Les résumés peuvent comporter des erreurs : vérifier les noms, chiffres et engagements.
Les sept modèles n'ont pas tous été évalués sur le même matériel. Les tailles de
mémoire indiquées sont des estimations ; un grand modèle peut partager GPU et RAM.

## Documentation et licence

- [Guide d'utilisation](docs/UTILISATION.md)
- [Architecture et maintenance](docs/ARCHITECTURE.md)
- [Validation et limites](docs/VALIDATION.md)
- [Composants tiers](THIRD_PARTY_NOTICES.md)
- [Licence MIT](LICENSE) pour le code de Clair ; les composants et modèles téléchargés
  conservent leurs propres licences.
