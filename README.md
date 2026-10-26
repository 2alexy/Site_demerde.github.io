Setup:
- Créer un compte sur le portail pour dev de spotify ( https://developer.spotify.com )
- créer une appli
- récupérer le client id et client secret + les ajouter dans le code (respectivement lignes 23 et 24 de hitster.py)
- toujours sur le portail dev de spotify, cocher "Web API", "Web playback SDK" et "Android"
- ajouter comme url de redirect "http://127.0.0.1:8888/callback
- valider les changements
- Lancer spotify un peu sur l'appareil qui servira a la lecture des extraits
- lancer le script gui.py (attention, faut que hitster.py et gui.py soient dans le même dossier)
