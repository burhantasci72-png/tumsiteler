name: Super Spor Botu Guncelle

on:
  schedule:
    - cron: '*/30 * * * *'
  workflow_dispatch:
  push:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Depoyu cek
        uses: actions/checkout@v3

      - name: Python Kur
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Kutuphaneleri Yukle
        run: pip install requests beautifulsoup4

      - name: Botu Calistir
        run: python main.py

      - name: Kaydet ve Yukle
        run: |
          git config --local user.email "actions@github.com"
          git config --local user.name "GitHub Action"
          git add Canli_Spor_Hepsi.m3u
          git commit -m "Tum Liste Guncellendi: $(date)" || exit 0
          git push
