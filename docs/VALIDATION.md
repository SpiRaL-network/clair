# Validation — 5 octobre 2026

Essais effectués sur Windows, avec 32 Go de RAM et une NVIDIA RTX 5080 de 16 Go.
Les enregistrements, transcriptions, noms de réunions et chemins personnels ne
sont pas inclus dans le dépôt.

## Tests automatisés

**41 tests passent** sans modèles réels ni GPU :

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

Les tests supplémentaires couvrent la découverte distante, les licences, les
révisions et empreintes obligatoires, les chemins interdits, les caches hors
ligne et leur conservation après échec, l’équilibre des éditeurs, l’attribution
conservatrice par chevauchement, le découpage par mots, les correspondances
voix/prénom, les corrections prioritaires, l’annulation, les instantanés de
participants et la protection des nouvelles routes par session/jeton.

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
| Catalogue dynamique | Requêtes réelles vers les trois éditeurs ; nouveautés datées jusqu’au 2 octobre 2026, cache chargé après redémarrage, modèle par défaut conservé |
| Granite 4.2 3B découvert | GGUF de 2,24 Go téléchargé et SHA-256 vérifié ; rapport français produit sur GPU en 4 s sur l’extrait de validation |
| Échantillon officiel de deux voix, 16 s | Deux groupes détectés sur CPU en environ 0,5 s, découpage par mots, association des deux noms, régénération et présence des noms dans les quatre exports |
| Enregistrement complet de 17 min 52 s | Whisper avec mots horodatés en 41 s ; analyse CPU des voix en environ 70 s. Avec le regroupement prudent, 13 groupes estimés et 508 passages ; ces groupes ne sont pas une mesure du nombre réel de personnes |
| Réinstallation des modèles de voix | Tailles et SHA-256 des deux ONNX vérifiés ; archive lue pour le membre connu |
| Thème sombre | Choix conservé après rechargement ; catalogue, participants, voix et transcription inspectés dans le navigateur |
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
n’a pas été enregistrée pour cette validation. La diarisation a été testée sur
l’échantillon anglais de deux voix et sur l’enregistrement complet ; elle ne
constitue pas une identification des personnes. Les noms de démonstration ont
été attribués manuellement uniquement sur la réunion de test, conservée hors du
dépôt. La qualité de séparation peut varier avec les conditions et les langues.
Les sorties ont été contrôlées pour leur structure et leur couverture, sans
validation humaine exhaustive de chaque propos contre l'audio.

Échantillon public de validation : [1-two-speakers-en.wav, sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-segmentation-models).
Les groupes et les mots non attribués ont été inspectés ; la détection laisse
volontairement des débuts/fins de phrases incertains sans prénom. Une correction
dans une transcription filtrée a été vérifiée sur le passage original.

Le seuil automatique de regroupement a été relevé à 0,9 après avoir observé
une fragmentation excessive (37 groupes au seuil initial 0,5) sur le long
enregistrement. La même modification conserve deux groupes sur l’échantillon
connu de deux voix. Le résultat automatique de 13 groupes sur la vidéo longue
n’a pas de vérité terrain annotée : il peut encore sur-segmenter ou fusionner
des personnes. Pour une réunion dont le nombre de personnes qui parlent est
connu, renseigner ce nombre et vérifier les extraits avant attribution.
