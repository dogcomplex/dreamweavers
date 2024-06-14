import pytest
from unittest.mock import patch, MagicMock
from dreamweaver import run_command, setup_repo, sync_with_upstream, run_docker

def test_run_command_success():
    with patch('subprocess.run') as mocked_run:
        mocked_run.return_value = MagicMock(stdout="success", stderr="", returncode=0)
        assert run_command("echo 'Hello'") == "success"

def test_run_command_fail():
    with patch('subprocess.run') as mocked_run:
        mocked_run.return_value = MagicMock(stdout="", stderr="error", returncode=1)
        with pytest.raises(Exception) as excinfo:
            run_command("exit 1")
        assert "Command failed" in str(excinfo.value)

@pytest.mark.asyncio
async def test_sync_with_upstream():
    with patch('dreamweaver.run_command', new_callable=MagicMock) as mocked_run:
        await sync_with_upstream()
        calls = [
            patch.mock.call('git fetch https://github.com/example-user/example-repo.git -C /path/to/local/repo'),
            patch.mock.call('git rebase https://github.com/example-user/example-repo.git/main -C /path/to/local/repo'),
            patch.mock.call('git push origin main -C /path/to/local/repo')
        ]
        mocked_run.assert_has_calls(calls, any_order=False)

@pytest.mark.asyncio
async def test_setup_repo_existing():
    with patch('os.path.exists', return_value=True), \
         patch('dreamweaver.run_command', new_callable=MagicMock) as mocked_run:
        await setup_repo()
        mocked_run.assert_called_once_with('pip install -r /path/to/local/repo/requirements.txt')

@pytest.mark.asyncio
async def test_run_docker():
    with patch('docker.from_env') as mocked_docker:
        mocked_client = MagicMock()
        mocked_docker.return_value = mocked_client
        mocked_client.images.build.return_value = ('image', 'log')
        mocked_client.containers.run.return_value = MagicMock()
        container = await run_docker()
        mocked_client.images.build.assert_called_once()
        mocked_client.containers.run.assert_called_once_with('example-image', detach=True)
        assert container is not None
