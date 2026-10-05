# Utiliser Clair

## Importer un média

**Importer un enregistrement** ouvre un formulaire. **Parcourir…** utilise le
sélecteur de fichiers du navigateur. Le média sélectionné est copié en flux vers
le service local ; une progression apparaît pendant la copie. Le fichier original
reste à son emplacement. Il est aussi possible de coller un chemin absolu pour
lire directement un fichier sur le PC, sans copier la vidéo originale.

Choisir la langue (détection automatique par défaut), le modèle, le mode de
traitement et le résultat souhaité : transcription seule ou transcription et
compte rendu. Le champ **Vocabulaire utile** aide pour les noms et acronymes.
Garder le service ouvert jusqu'à la fin. L'annulation conserve la transcription
déjà produite.

## Capturer une réunion Teams

1. Dans Teams, identifier la sortie audio et le microphone utilisés.
2. Dans Clair, ouvrir **Enregistrer une réunion** et sélectionner ces périphériques.
3. Démarrer la capture et vérifier les indicateurs de niveau.
4. À la fin, cliquer sur **Arrêter et créer le compte rendu**.

Le son du PC et le micro sont conservés dans deux pistes séparées. Les autres
applications qui jouent sur la même sortie audio peuvent aussi être capturées.
La sélection **Sans microphone** permet de capturer uniquement le son du PC.
Le remplissage des silences maintient l'alignement des pistes lorsque WASAPI ne
renvoie pas de buffers pendant une période silencieuse.

Clair ne détecte pas le début d'une réunion et ne transcrit pas en direct pendant
la capture. La capture enregistre ce que les périphériques sélectionnés reçoivent.

## Choisir le modèle et le matériel

Dans **Catalogue de modèles**, télécharger les modèles souhaités et définir le
modèle par défaut. Les entrées initiales affichent leur date de sortie ; les
nouveautés découvertes indiquent la date d’ajout au dépôt GGUF, la licence et la fiche.
**Arrêter** conserve la partie reçue ; **Reprendre le téléchargement** reprend
depuis cette partie lorsque le dépôt accepte les requêtes de plage.
Le fichier est activé seulement après vérification complète de son SHA-256.

| Mode | Transcription | Résumé |
| --- | --- | --- |
| Automatique | NVIDIA si détecté, sinon CPU | NVIDIA si détecté, sinon moteur CPU |
| GPU NVIDIA | GPU compatible obligatoire | GPU avec partage possible entre VRAM et RAM |
| CPU uniquement | Whisper int8 CPU | Moteur llama.cpp CPU, sans CUDA |

Les choix sont enregistrés avec la réunion. Les préférences globales concernent
les nouvelles réunions. Pour un résumé déjà produit, choisir un autre modèle ou
mode dans sa page, puis **Refaire le résumé**. La transcription reste inchangée.

Un grand modèle peut être plus lent ou manquer de mémoire. Les estimations
affichées ne comprennent pas tous les besoins du système. Qwen3.8 27B Q4_K_M
pèse 17,44 Go : prévoir suffisamment de RAM même avec une carte de 16 Go.

## Catalogue actualisable

L’actualisation automatique est activée au départ. Clair consulte Hugging Face
au démarrage si le cache a plus de 24 heures, puis vérifie chaque heure si une
nouvelle consultation est nécessaire. L’application doit être ouverte ; aucun
service supplémentaire n’est installé. **Actualiser maintenant** permet de
relancer la recherche. La date et les erreurs apparaissent dans le catalogue.

La découverte retient jusqu’à douze nouveaux GGUF, répartis entre Unsloth,
bartowski et LM Studio Community : un fichier Q4_K_M unique, de 0,5 à 20 Go,
licence ouverte reconnue, dépôt public non soumis à acceptation d’accès.
Les modèles de génération d’images, de voix, de transcription, d’embeddings et
les archives GGUF fractionnées sont exclus. Ce filtre est une sélection
technique ; il ne garantit pas la qualité en français ni l’exactitude des résumés.
Chaque nouveauté possède une révision précise et une empreinte publiée.
Le moteur llama.cpp peut ne pas prendre en charge une architecture récente.

Une panne réseau conserve les données locales. Les fichiers installés ne sont
jamais remplacés par cette recherche, et le modèle par défaut ne change pas.
Aucun téléchargement de poids ne démarre sans clic sur **Télécharger**.
Le champ de recherche filtre les noms, éditeurs et licences.

## Participants et voix

1. Saisir les prénoms dans **Participants**, séparés par virgules, points-virgules
   ou retours à la ligne ; ils peuvent être modifiés ensuite.
2. Activer **Distinguer les voix après la transcription** pour un import ou une
   capture. Les modèles sont installés par `Installer.cmd`, ou avec le bouton
   correspondant dans le catalogue. Le moteur travaille toujours sur CPU.
3. Laisser **Nombre de voix attendues** à 0 pour une estimation, ou indiquer
   le nombre de personnes qui parlent réellement (1 à 30). Le nombre de noms
   déclarés ne force pas le nombre de voix.
4. Dans la réunion, ouvrir **Participants et voix**, écouter les extraits et
   choisir le prénom de chaque voix. Les noms ne sont jamais devinés.
5. Vérifier l’onglet transcription. Le sélecteur de chaque passage permet une
   correction ou **Non attribué**. Une correction manuelle reste prioritaire
   lorsqu’une correspondance voix/prénom est modifiée.
6. Cliquer sur **Refaire le résumé** après les attributions. Un message signale
   les changements non encore pris en compte ; l’ancien rapport reste conservé.

**Distinguer les voix** fonctionne également après une transcription déjà
terminée. Une réanalyse remplace les voix et leurs correspondances : revoir les
attributions après son exécution. Une annulation conserve les attributions
précédentes. La suppression d’un prénom efface ses attributions dans les passages
et dans les voix, mais laisse l’ancien rapport intact jusqu’à sa régénération.

Whisper produit des repères par mot pour les nouvelles transcriptions. Clair
les rapproche des plages de parole détectées et découpe les passages aux
changements de voix. Une couverture faible ou plusieurs voix concurrentes
laissent le passage non attribué. Pour les anciennes transcriptions dépourvues
de ces repères, relancer la transcription permet ce découpage. Les horodatages
et les voix peuvent être inexacts : utiliser les extraits pour vérifier.

Les noms et les étiquettes de voix apparaissent dans les exports TXT/SRT. Le
rapport Markdown/JSON contient les participants déclarés au moment de sa
génération. Une liste de noms seule ne constitue pas une preuve d’identité ou
d’attribution des actions. Clair ne reconnaît pas les visages et ne constitue
pas une bibliothèque de signatures vocales.

## Apparence

Le menu **Thème de l’application**, en haut à droite, propose **Thème clair**,
**Thème sombre** et **Thème système**. Le choix est conservé dans ce navigateur.
Le mode système suit les changements de thème du système d’exploitation.

## Consulter et exporter

Le compte rendu présente les sujets, décisions, propositions à confirmer, actions
et questions ouvertes. La transcription est horodatée et recherchable. Cliquer sur
un horodatage permet de réécouter le passage cité lorsque l'audio est disponible.

**Copier** copie l'onglet courant. **Exporter** fournit TXT, SRT, Markdown ou JSON.
Le modèle qui a produit le compte rendu est conservé dans ses métadonnées.
**Ouvrir les fichiers** ouvre la bibliothèque dans l'Explorateur Windows.

## Données et réseau

Le service écoute uniquement sur la boucle locale. Audio, transcription et résumé
sont conservés sur le PC. Les données ne sont pas chiffrées par Clair ; elles
utilisent les protections du disque et du compte Windows.
Internet sert aussi à l’actualisation optionnelle du catalogue. Il est nécessaire
pour télécharger les composants et les modèles ; il
n'est pas nécessaire pour traiter une réunion après installation.

| Dossier/fichier | Contenu |
| --- | --- |
| `reunions/` | Réunions, pistes audio, transcriptions et comptes rendus |
| `models/` | Modèles de transcription, résumé et séparation des voix |
| `catalog-cache.json` | Métadonnées publiques des modèles découverts et dernière consultation |
| `bin/cpu/`, `bin/gpu/` | Moteurs locaux de résumé |
| `runtime/`, `.venv/` | Runtime et bibliothèques Python |
| `settings.json` | Préférences locales |
| `.imports/`, `*.part` | Fichiers temporaires ou téléchargements partiels |
| `*.log` | Diagnostics pouvant contenir des informations locales |

Ces fichiers ne sont pas versionnés. Fermer l'onglet ne ferme pas le service.
**Quitter Clair** arrête le service après la fin ou l'annulation du traitement.

## Dépannage

- **Sélecteur bloqué** : recharger la page pour charger la dernière version ;
  utiliser le sélecteur du navigateur ou coller un chemin absolu.
- **Fichier introuvable** : pour un import par chemin, remettre le média à cet
  emplacement ou importer une nouvelle copie.
- **Aucun son de réunion** : vérifier la sortie sélectionnée dans Teams et Clair,
  puis effectuer une capture courte et l'écouter.
- **Erreur de résumé** : la transcription reste disponible ; essayer un modèle
  plus petit ou le CPU, puis régénérer le résumé.
- **GPU indisponible** : choisir le CPU ou vérifier le pilote NVIDIA et la
  compatibilité des composants CUDA installés.
- **Modèles absents** : relancer `Installer.cmd` avec Internet ou le téléchargement
  dans le catalogue.
- **Port occupé** : les services utilisent les ports locaux 8787 et 8788.
- **Blocage Windows** : vérifier les diagnostics de Windows ; Clair ne modifie
  pas les réglages de sécurité.

Les journaux principaux sont `service.log`, `application.log` et
`moteur-resume.log`. Retirer les chemins et contenus privés avant de les partager.
