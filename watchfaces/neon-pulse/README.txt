Neon Pulse - quadrante per Mi Smart Band 6 (152x486)

NeonPulse.bin         il quadrante da installare (si apre con l'app Aurora: Dispositivi > installa file)
NeonPulse-preview.png anteprima (ore 10:09, 7:45 con batteria bassa, 23:58 a obiettivi pieni)
make_face.py          disegna le immagini e il layout (Python + Pillow)
pack_face.py          impacchetta le immagini nel file .bin e lo rilegge per controllarlo

Per rigenerare: npm i watchface-js --ignore-scripts (serve solo il file dei nomi
node_modules/watchface-js/src/watchFaceBinTools/models/fileTypes/UIHH_MIBAND.json), poi
python make_face.py && python pack_face.py
