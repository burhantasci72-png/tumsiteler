name: Günlük Liste Güncelleme

on:
  schedule:
    - cron: '0 */3 * * *' # Her 3 saatte bir çalışır
  workflow_dispatch: # Elle çalıştırma butonu ekler

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Depoyu Çek (Checkout)
        uses: actions/checkout@v3

      - name: Python Kurulumu
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Kütüphaneleri Yükle
        run: |
          pip install -r requirements.txt

      - name: Betiği Çalıştır
        run: python main.py

      - name: Dosyayı Commit ve Push Yap
        run: |
          git config --global user.name "GitHub Action"
          git config --global user.email "action@github.com"
          git add Canli_Spor_Hepsi.m3u
          git commit -m "Listeyi Güncelle" || echo "Değişiklik yok"
          git push
