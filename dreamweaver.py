import subprocess
import asyncio
import aiohttp
import json
import os
from configparser import ConfigParser
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration settings
config = ConfigParser()
config.read('config.ini')

# Constants for file paths and credentials from config file
REPO_PATH = config.get('paths', 'REPO_PATH')
DOCKER_COMPOSE_PATH = os.path.join(REPO_PATH, 'docker-compose.yaml')  # Path to your docker-compose file
UPSTREAM_REPO_URL = config.get('git', 'UPSTREAM_REPO_URL')
LOCAL_REPO_PATH = config.get('paths', 'LOCAL_REPO_PATH')
UPSTREAM_BRANCH = config.get('git', 'UPSTREAM_BRANCH')

# Configure environment variables from config file
os.environ["AZURE_API_KEY"] = config.get('azure', 'AZURE_API_KEY')
os.environ["AZURE_API_BASE"] = config.get('azure', 'AZURE_API_BASE')
os.environ["AZURE_API_VERSION"] = config.get('azure', 'AZURE_API_VERSION')
os.environ["AZURE_OPENAI_ENDPOINT"] = config.get('azure', 'AZURE_OPENAI_ENDPOINT')
os.environ["AZURE_OPENAI_API_KEY"] = config.get('azure', 'AZURE_OPENAI_API_KEY')

def run_command(command):
    """ Utility function to run a shell command and return its result. """
    try:
        result = subprocess.run(command, shell=True, text=True, capture_output=True, check=True)
        logging.info(result.stdout)
        if result.stderr:
            logging.error(result.stderr)
        result.check_returncode()  # Ensure no error occurred
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e.stderr}")
        raise

async def sync_with_upstream():
    """ Syncs the local repository with the upstream repository asynchronously. """
    if not os.path.exists(LOCAL_REPO_PATH):
        logging.error(f"Directory not found: {LOCAL_REPO_PATH}")
        raise FileNotFoundError(f"Directory not found: {LOCAL_REPO_PATH}")
    await asyncio.to_thread(run_command, f'git fetch {UPSTREAM_REPO_URL} -C {LOCAL_REPO_PATH}')
    await asyncio.to_thread(run_command, f'git rebase {UPSTREAM_REPO_URL}/{UPSTREAM_BRANCH} -C {LOCAL_REPO_PATH}')
    await asyncio.to_thread(run_command, f'git push origin main -C {LOCAL_REPO_PATH}')

async def setup_repo():
    """ Clones the repo and installs requirements asynchronously. """
    if not os.path.exists(LOCAL_REPO_PATH):
        await asyncio.to_thread(run_command, f'git clone {UPSTREAM_REPO_URL} {LOCAL_REPO_PATH}')
    if os.path.exists(os.path.join(LOCAL_REPO_PATH, 'requirements.txt')):
        await asyncio.to_thread(run_command, f'python3.10 -m pip install -r {os.path.join(LOCAL_REPO_PATH, "requirements.txt")}')
    else:
        logging.error('requirements.txt not found')

async def run_docker_compose():
    """ Use docker-compose to build and run containers. """
    if not os.path.exists(DOCKER_COMPOSE_PATH):
        logging.error(f"docker-compose.yaml not found at {DOCKER_COMPOSE_PATH}")
        raise FileNotFoundError(f"docker-compose.yaml not found at {DOCKER_COMPOSE_PATH}")
    logging.info("Running docker-compose up...")
    await asyncio.to_thread(run_command, f'docker-compose -f {DOCKER_COMPOSE_PATH} up --build -d')

async def execute_script(container_name):
    """ Execute a script inside a Docker container managed by docker-compose. """
    logging.info(f"Executing script inside the container {container_name}...")
    await asyncio.to_thread(run_command, f'docker-compose -f {DOCKER_COMPOSE_PATH} exec {container_name} python submission_formatting.py')

async def query_openai_api(session, index):
    """ Function to query OpenAI API using Azure configuration. """
    api_url = os.getenv('AZURE_OPENAI_ENDPOINT')
    headers = {'Authorization': f'Bearer {os.getenv("AZURE_OPENAI_API_KEY")}', 'Content-Type': 'application/json'}
    conversation = [{"role": "system", "content": "Assistant is a large language model trained by OpenAI."},
                    {"role": "user", "content": "What are the main benefits of using Azure OpenAI?"}]
    response = await session.post(f'{api_url}/completions', headers=headers, json={"model": "gpt-3.5-turbo", "messages": conversation})
    if response.status != 200:
        logging.error(f"API request failed with status {response.status}")
        response.raise_for_status()
    data = await response.json()
    metadata_dir = os.path.join(REPO_PATH, "dreamweavers", "metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    with open(os.path.join(metadata_dir, f"prompt{index}.json"), 'w') as f:
        json.dump(data, f)

    return data

async def main():
    """ Main asynchronous function to run tasks. """
    await setup_repo()
    await sync_with_upstream()
    await run_docker_compose()
    await execute_script("container_service_name")  # Replace 'container_service_name' with your service name defined in docker-compose

if __name__ == '__main__':
    asyncio.run(main())
