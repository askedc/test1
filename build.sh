cd code

pyinstaller -F main.py

mv dist/main ../progress/

cd ..

tar -zcvf progress.tar.gz progress

