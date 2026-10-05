# Validation — 5 octobre 2026

Essais effectués sur Windows, avec 32 Go de RAM et une NVIDIA RTX 5080 de 16 Go.
Les enregistrements, transcriptions, noms de réunions et chemins personnels ne
sont pas inclus dans le dépôt.

## Tests automatisés

**14 tests passent** sans modèles réels ni GPU :

1. Conservation des passages lors du découpage d'une longue transcription.
2. Reprise après interruption et validation des identifiants/chemins.
3. Assemblage d'une piste microphone seule.
4. Conservation des exports après annulation.
5. Distinction des propositions dans l'export Markdown.
6. Maintien de la durée d'une source audio silencieuse.
7. Copie et démarrage d'un média sélectionné.
8. Rejet des imports vides, invalides ou concurrents.
9. Protection de l'import par session et jeton.
10. Reprise d'un téléchargement avec vérification SHA-256 et préférences persistées.
11. Rejet d'un fichier de modèle corrompu.
12. Arrêt avec conservation du téléchargement partiel.
13. Sélection du moteur CPU sans détection CUDA.
14. Conservation du modèle du rapport précédent pendant une régénération.

Les tests de stockage, capture et API substituent la disponibilité des modèles.
Les tests du catalogue utilisent de petits fichiers de fixture ; ils vérifient
les mécanismes et ne téléchargent pas de poids.

## Essais réels

| Essai | Résultat |
| --- | --- |
| Vidéo d'environ 18 minutes, Whisper large-v3 GPU | 245 segments, détection de l'anglais ; transcription complète en 42 s lors du test d'import |
| Compte rendu de cette vidéo avec l'ancien Qwen2.5 14B | Rapport en français produit ; pipeline complet d'environ 75 s lors du premier essai |
| Capture système + micro de 15,766 s | Deux pistes de même durée, signal présent, assemblage et traitement terminés |
| Extrait de 20 s, CPU uniquement | Whisper int8 CPU en 15 s, Qwen3.5 4B CPU en 18 s ; trois segments et un rapport français |
| Même transcription avec Gemma 4 E2B GPU | Régénération terminée en 11 s, sans modification des trois segments CPU |
| Catalogue | Qwen3.5 4B téléchargé, hash vérifié ; Gemma 4 E2B arrêté vers 1,72 Go, repris et vérifié |
| Redémarrage | Préférences modèle/matériel conservées ; API, exports et lecture audio opérationnels |

Les temps sont ceux de ce matériel et de ces exemples, pas des garanties de
performance. Les contrôles de session, jeton, hôte et origine ainsi que les
exports autorisés et la lecture audio par plages ont aussi été exercés via API.

## Portée et limites

Qwen3.5 4B et Gemma 4 E2B ont réellement produit un rapport. Les cinq autres
modèles du catalogue 2026 sont disponibles au téléchargement, mais n'ont pas
tous été téléchargés ni évalués sur ce PC. Le test CPU porte sur un extrait de
20 secondes, pas sur une réunion complète de 18 minutes. La répartition GPU/RAM
est configurée, mais le modèle Qwen3.8 27B n'a pas été chargé lors de ces essais.

La capture des périphériques a été testée ; une réunion Teams complète en direct
n'a pas été enregistrée pour cette validation. La diarisation est absente.
Les sorties ont été contrôlées pour leur structure et leur couverture, sans
validation humaine exhaustive de chaque propos contre l'audio.
