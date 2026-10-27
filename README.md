# Infografies de YouTube

1. Cada matí, GitHub Actions llegeix `canals.txt`, detecta els vídeos publicats en les últimes 36 hores i en desa la transcripció a `transcripcions/AAAA-MM-DD/`.
2. Una tasca programada de Claude al núvol llegeix les transcripcions noves i fa una infografia d'una pàgina per vídeo.

## Afegir o treure canals
Edita `canals.txt` (es pot fer des del web o l'app de GitHub): un `@handle` per línia.

## Si YouTube bloqueja les descàrregues
Exporta les galetes de YouTube en format Netscape (`cookies.txt`) i desa'n el contingut com a secret del repositori amb el nom `YT_COOKIES` (Settings → Secrets and variables → Actions).
