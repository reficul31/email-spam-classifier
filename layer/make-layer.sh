mkdir -p python/lib/python3.9/site-packages
pip install -r requirements.txt --target python/lib/python3.9/site-packages
zip python layer.zip
rm -rf python/