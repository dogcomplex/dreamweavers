import pytest
from unittest.mock import patch, MagicMock
from dreamweaver import run_command, setup_repo, sync_with_upstream, run_docker_compose, execute_script

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
async def test_run_docker_compose():
    with patch('dreamweaver.run_command', new_callable=MagicMock) as mocked_run:
        await run_docker_compose()
        mocked_run.assert_called_once_with(f'docker-compose -f {DOCKER_COMPOSE_PATH} up --build -d')

@pytest.mark.asyncio
async def test_execute_script():
    with patch('dreamweaver.run_command', new_callable=MagicMock) as mocked_run:
        await execute_script("service_name")
        mocked_run.assert_called_once_with(f'docker-compose -f {DOCKER_COMPOSE_PATH} exec service_name python submission_formatting.py')
