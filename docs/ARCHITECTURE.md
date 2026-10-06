# Architecture et maintenance

Clair est une application Windows avec interface web locale, API FastAPI et
traitements audio/LLM dans des threads. Aucun service d'inférence tiers n'est requis.

## Organisation

| Élément | Responsabilité |
| --- | --- |
| `app.py` | Routes locales, session/jeton, import en flux, contrôle des tâches et capture |
| `core.py` | Stockage des réunions, extraction audio, Whisper, capture et génération des rapports |
| `catalog.py` | Installation et reprise des GGUF, contrôle d'intégrité et préférences |
| `discovery.py` | Découverte Hugging Face, licences et validation stricte des métadonnées |
| `voices.py` | Modèles ONNX vérifiés, séparation CPU/CUDA, références de voix et alignement conservateur par mot |
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
  -> mots horodatés + segments
  -> segmentation et regroupement des voix (optionnel, CPU/CUDA)
  -> découpage aux changements de voix + TXT/SRT
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

Le fichier `models-catalog.json` reste un catalogue initial fixé et disponible
hors ligne. Un thread démarré par le cycle de vie FastAPI consulte les API
publiques Hugging Face chaque jour ; le bouton d’actualisation utilise le même
mécanisme. Les requêtes n’incluent aucun contenu ou nom de réunion. Les réponses
JSON sont limitées à 4 Mo et la recherche aux trois éditeurs autorisés, avec
limites de durée, de nombre de candidats et de nouveaux modèles.

La découverte filtre les dépôts publics non restreints, les usages de génération
textuelle et les licences Apache 2.0, MIT, BSD 2/3 clauses, CC0 et CC BY 4.0.
Elle exige un GGUF Q4_K_M unique entre 0,5 et 20 Go, une révision SHA de 40 caractères
et une empreinte LFS SHA-256 de 64 caractères. Les chemins de fichiers ne peuvent
pas contenir de répertoires. Le stockage ajoute un préfixe dérivé du dépôt, de
la révision et du nom source pour éviter les collisions entre éditeurs.

Le cache `catalog-cache.json` est écrit atomiquement et validé à la lecture.
Il conserve les anciennes entrées pour résoudre les choix des réunions
existantes ; les entrées anciennes non installées peuvent disparaître de
l’affichage. Les fichiers installés et partiels restent visibles. Une panne
réseau conserve le cache précédent ; un échec partiel conserve les entrées
visibles des sources indisponibles. La découverte ne change ni le défaut ni
les poids installés. La date découverte est celle de création du dépôt GGUF,
pas une prétendue date de sortie du modèle original. La compatibilité et la
qualité ne sont pas prouvées par une empreinte valide.

## Séparation des voix et attributions

sherpa-onnx 1.13.8 exécute sur CPU ou CUDA la segmentation Pyannote 3.0 et un extracteur
ERes2Net 3D-Speaker entraîné sur VoxCeleb. Les conversions ONNX proviennent des
releases officielles sherpa-onnx ; tailles et SHA-256 sont fixés dans `voices.py`
et contrôlés avant installation puis avant analyse. L’archive est lue pour un
seul membre connu sans extraction de chemins sur le disque.

La diarisation produit des plages de parole et des groupes anonymes, ordonnés
par première apparition. Le nombre de groupes peut être estimé ou imposé. Le seuil de regroupement
automatique est fixé à 0,9 pour limiter la fragmentation observée sur un
enregistrement long ; ce réglage peut aussi fusionner des voix proches.
Les mots Whisper sont attribués par chevauchement temporel : couverture du
groupe dominant d’au moins 55 %, second groupe inférieur à 25 %. Ces seuils
sont des heuristiques, pas des scores de confiance calibrés. Les passages
ambigus restent non attribués ; une transcription ancienne sans mots conserve
son découpage de paragraphes. Les nouvelles transcriptions gardent leurs mots
pour que la réanalyse puisse refaire le découpage.

L’utilisateur associe une voix à un prénom déclaré. La correspondance s’applique
aux segments qui ne portent pas une correction manuelle. Les corrections et
le retrait explicite d’une attribution sont prioritaires. Noms, segments et
exports sont mis à jour localement. Les changements marquent le rapport existant
comme obsolète sans le modifier ; la régénération enregistre un nouvel instantané
de participants. Les prompts distinguent prénoms déclarés, correspondances
confirmées et étiquettes automatiques sans identité. Aucun nom n’est déduit d’un
visage, de la voix seule ou de l’ordre des participants. Aucun profil vocal
persistant n’est calculé pour identifier quelqu’un dans une autre réunion.

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

### Processus des voix et références

Chaque analyse démarre `voices.py --worker` avec le Python de l’application,
sans fenêtre. Audio, paramètres et résultats restent locaux ; le protocole JSON
sur pipes transmet progression et résultat. Un processus séparé évite la
collision entre les DLL ONNX Runtime du VAD de Whisper et de sherpa-onnx CUDA.
Il est terminé lors d’une annulation, puis sa mémoire GPU est libérée.

Sous Windows Python 3.12, le wheel officiel sherpa-onnx
`1.13.8+cuda12.cudnn9` est verrouillé dans `requirements.lock.txt` par révision
Hugging Face et SHA-256. CUDA runtime, cuFFT et nvJitLink complètent les
bibliothèques cuBLAS/cuDNN déjà requises. Le fournisseur `cuda` est configuré
pour la segmentation et l’extracteur ; `cpu` reste disponible. Le mode
automatique peut redémarrer le worker sur CPU en cas d’échec CUDA ; le mode
GPU explicite échoue sans repli silencieux. Le fournisseur effectivement utilisé
est enregistré dans `voice_device`.

Les références contiennent prénom, début et fin, de 3 à 20 secondes, au maximum
60 par réunion. ERes2Net produit un vecteur normalisé par exemple et par prise
de parole exploitable (au moins 1,5 seconde, jusqu’à 12 secondes analysées). Le
score de chaque prénom est la meilleure similarité cosinus parmi ses exemples.
L’attribution exige au moins 0,65 et une marge de 0,10 sur le deuxième prénom.
Ces réglages sont des heuristiques, sans calibration statistique ni garantie
d’identité. Les prises de parole superposées ou silencieuses sont exclues.
L’alignement temporel des noms conserve les seuils 55 % / 25 %.

Les attributions issues des références portent `speaker_reference`; une
correction manuelle porte `speaker_manual` et reste prioritaire, même lors du
retrait de la dernière référence. Le batch de références, les attributions,
les métriques et les exports ne sont validés qu’après réussite, jamais après
annulation. Les vecteurs ne sont pas enregistrés : ils sont recalculés depuis
l’audio local. Retirer un participant supprime également ses références.

### Sauvegarde des réunions sous Windows

`Studio.read`, `update`, `save` et `listing` partagent le verrou réentrant de
l’instance. Les handles de lecture Python sur Windows ne partagent pas DELETE :
une lecture simultanée pouvait empêcher le renommage du JSON par le worker.
`atomic_json_write` ferme et synchronise un temporaire unique avant le
remplacement atomique, puis réessaie uniquement les PermissionError avec une
attente bornée. L’ancien fichier reste lisible et complet. Un verrou persistant
laisse un fichier `meeting-*.tmp` complet, sans remplacer le JSON valide par une
écriture en place ni modifier les droits du dossier.
