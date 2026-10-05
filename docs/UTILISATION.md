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
modèle par défaut. Les entrées affichent leur date de sortie, taille et fiche.
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
Internet est nécessaire pour télécharger les composants et les modèles ; il
n'est pas nécessaire pour traiter une réunion après installation.

| Dossier/fichier | Contenu |
| --- | --- |
| `reunions/` | Réunions, pistes audio, transcriptions et comptes rendus |
| `models/` | Modèles de transcription et de résumé |
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
