sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update



sudo apt install python3.10
python3.10 --version

echo "alias python=python3.10" >> ~/.bashrc
source ~/.bashrc

curl -O https://bootstrap.pypa.io/get-pip.py
python3.10 get-pip.py
python3.10 -m pip --version

python3.10 -m pip install paramiko docker asyncio aiohttp litellm pytest
