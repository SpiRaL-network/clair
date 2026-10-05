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
- Catalogue dynamique : actualisation quotidienne depuis Hugging Face, bouton
  d’actualisation, recherche et cache hors ligne. Sept modèles initiaux de 2026.
  Nouveautés à licence ouverte, GGUF Q4_K_M ; téléchargements à la demande avec SHA-256.
- Séparation locale des voix sur CPU ou GPU NVIDIA, extraits à écouter, association aux prénoms,
  corrections par passage et prise en compte dans le prochain compte rendu.
- Thèmes clair, sombre et système ; préférence conservée dans le navigateur.
- Choix du modèle par réunion ; régénération du résumé sans retranscription.
- Reconnaissance des voix à partir d’extraits nommés de la réunion (plusieurs exemples par personne).
- Traitement automatique, GPU NVIDIA, ou CPU uniquement, avec choix indépendant pour les voix.
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
llama.cpp CPU/GPU, les deux petits modèles de voix et un runtime Python autonome. Aucun modèle ni binaire tiers
n'est inclus dans ce dépôt. `Lancer.cmd` utilise ensuite le runtime local.

Le catalogue s'ouvre dans le menu **Catalogue de modèles**. Les modèles supplémentaires
se téléchargent à la demande. Le catalogue consulte les dépôts publics Unsloth,
bartowski et LM Studio Community une fois par jour pendant que Clair est ouvert.
Aucun modèle n’est téléchargé ou sélectionné automatiquement. Désactiver
**Actualiser automatiquement chaque jour** pour conserver un usage hors ligne.
Les modèles installés, leurs révisions et le modèle par défaut sont conservés.
Les nouveautés indiquent leur date d’ajout au dépôt, leur licence et leur fiche ;
leur qualité et leur compatibilité ne sont pas garanties par la découverte.

## Utilisation

1. Choisir **Importer un enregistrement** ou **Enregistrer une réunion**.
2. Choisir la langue, le modèle, le mode CPU/GPU et éventuellement les participants
   et la séparation des voix.
3. Importer le média, ou sélectionner les périphériques audio utilisés par Teams
   puis démarrer la capture manuellement.
4. Consulter la transcription et le compte rendu ; exporter ou réécouter les passages.

La transcription conserve la langue parlée ; le compte rendu est en français.
Pour changer de modèle après traitement, choisir **Modèle pour le prochain résumé**,
puis **Refaire le résumé**. Le modèle du rapport actuel reste indiqué jusqu'au
remplacement effectif du compte rendu.

Après détection, ouvrir **Participants et voix**, écouter les extraits et associer
chaque voix à un prénom déclaré. Vérifier les passages, puis cliquer sur
**Refaire le résumé**. Les passages ambigus restent non attribués.
Le sélecteur en haut à droite propose le thème sombre.

Les données sont stockées dans `reunions/`, les modèles dans `models/`, les
préférences dans `settings.json`, le catalogue découvert dans `catalog-cache.json`. Ces fichiers sont exclus de Git.

## Développement et tests

Après installation des dépendances :

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe app.py --no-browser
```

Les **41 tests** s'exécutent sans télécharger de modèles, sans GPU et sans capturer
de périphériques. Les tests d'inférence utilisent des substituts ; les essais réels
CPU/GPU sont documentés dans [docs/VALIDATION.md](docs/VALIDATION.md).
Le workflow GitHub Actions vérifie les sources et les tests sur Windows.

## Limites

La capture démarre manuellement, et la transcription s'effectue après son arrêt.
La diarisation sépare les voix ; le nom est confirmé par l’utilisateur après écoute.
Clair n’identifie pas les personnes à partir de leur visage et ne mémorise pas
de profils vocaux entre les réunions. Les voix simultanées, le bruit et les
repères de mots imprécis peuvent laisser des passages non attribués. Les
anciennes transcriptions sans repères de mots nécessitent une retranscription
pour découper les passages contenant plusieurs personnes.
Les résumés peuvent comporter des erreurs : vérifier les noms, chiffres et engagements.
Tous les modèles initiaux et découverts n’ont pas été évalués sur le même matériel.
Une nouvelle architecture GGUF peut nécessiter une version plus récente du moteur. Les tailles de
mémoire indiquées sont des estimations ; un grand modèle peut partager GPU et RAM.

## Documentation et licence

- [Guide d'utilisation](docs/UTILISATION.md)
- [Architecture et maintenance](docs/ARCHITECTURE.md)
- [Validation et limites](docs/VALIDATION.md)
- [Composants tiers](THIRD_PARTY_NOTICES.md)
- [Licence MIT](LICENSE) pour le code de Clair ; les composants et modèles téléchargés
  conservent leurs propres licences.

### Mise à jour vers 1.3

Fermer Clair, récupérer les sources puis relancer `Installer.cmd` pour installer
le moteur sherpa-onnx CPU/CUDA 12.8 + cuDNN 9 et ses bibliothèques NVIDIA.
Les dépendances CUDA restent utilisables en mode CPU sur un PC sans carte NVIDIA.
Le paquet Windows Python 3.12 provient de l’index officiel du projet et est fixé
à une révision et un SHA-256 ; les médias restent locaux.
