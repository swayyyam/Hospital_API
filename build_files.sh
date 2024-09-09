echo "BUILD START"
python3.9 -m pip install --upgrade pip
python3.9 -m pip install -r requirements.txt
python3.9 manage.py collectstatic --noinput --clear --settings=hospital_management.settings.production
echo "BUILD END"