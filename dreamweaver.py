import subprocess
import docker
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
DOCKER_IMAGE_NAME = config.get('docker', 'DOCKER_IMAGE_NAME')
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
        result = subprocess.run(command, text=True, capture_output=True, check=True)
        return result.stdout
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
    if not os.path.exists(os.path.join(LOCAL_REPO_PATH, 'requirements.txt')):
        logging.error('requirements.txt not found')
        raise FileNotFoundError('requirements.txt not found')
    await asyncio.to_thread(run_command, f'pip install -r {os.path.join(LOCAL_REPO_PATH, "requirements.txt")}')

async def run_docker():
    """ Build and run Docker container asynchronously. """
    client = docker.from_env()
    logging.info("Building Docker image...")
    image, logs = await asyncio.to_thread(client.images.build, path=REPO_PATH, tag=DOCKER_IMAGE_NAME)
    logging.info("Running Docker container...")
    container = await asyncio.to_thread(client.containers.run, DOCKER_IMAGE_NAME, detach=True)
    return container

async def execute_script(container):
    """ Execute script inside Docker asynchronously. """
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(query_openai_api(session, i)) for i in range(3)]
        await asyncio.gather(*tasks)
    await asyncio.to_thread(container.exec_run, f'python {os.path.join(REPO_PATH, "submission_formatting.py")}')

async def query_openai_api(session, index):
    """ Function to query OpenAI API using Azure configuration. """
    # Define the API endpoint and headers
    api_url = os.getenv('AZURE_OPENAI_ENDPOINT')
    headers = {
        'Authorization': f'Bearer {os.getenv("AZURE_OPENAI_API_KEY")}',
        'Content-Type': 'application/json'
    }

    # Define the conversation with initial system context and user prompt
    conversation = [
        {"role": "system", "content": "Assistant is a large language model trained by OpenAI."},
        {"role": "user", "content": "What are the main benefits of using Azure OpenAI?"}
    ]

    # Make the API request
    response = await session.post(
        f'{api_url}/completions',
        headers=headers,
        json={"model": "gpt-3.5-turbo", "messages": conversation}
    )

    # Check response status
    if response.status != 200:
        logging.error(f"API request failed with status {response.status}")
        response.raise_for_status()

    # Process the response
    data = await response.json()
    metadata_dir = os.path.join(REPO_PATH, "dreamweaver", "metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    with open(os.path.join(metadata_dir, f"prompt{index}.json"), 'w') as f:
        json.dump(data, f)

    return data

async def main():
    """ Main asynchronous function to run tasks. """
    await setup_repo()
    await sync_with_upstream()
    container = await run_docker()
    await execute_script(container)

if __name__ == '__main__':
    asyncio.run(main())
