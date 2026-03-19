import pytest
from docker_executor import DockerExecutor


@pytest.fixture
def executor(tmp_path):
    """Create executor with a temporary workspace."""
    return DockerExecutor(
        image="python:3.12-slim",
        workspace_dir=str(tmp_path),
        mem_limit="128m",
        timeout=10,
        idle_timeout=30,
    )


class TestRunCommand:
    def test_echo(self, executor):
        result = executor.run_command("echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["output"]

    def test_timeout(self, executor):
        result = executor.run_command("sleep 60")
        assert result["exit_code"] != 0
        assert "timeout" in result["output"].lower()

    def test_nonexistent_command(self, executor):
        result = executor.run_command("nonexistent_cmd_xyz")
        assert result["exit_code"] != 0


class TestFileOperations:
    def test_write_and_read_file(self, executor):
        executor.write_file("/workspace/test.txt", "hello world")
        content = executor.read_file("/workspace/test.txt")
        assert content == "hello world"

    def test_read_nonexistent_file(self, executor):
        with pytest.raises(FileNotFoundError):
            executor.read_file("/workspace/nonexistent.txt")

    def test_list_files(self, executor):
        executor.write_file("/workspace/a.txt", "a")
        executor.write_file("/workspace/b.txt", "b")
        files = executor.list_files("/workspace")
        assert "a.txt" in files
        assert "b.txt" in files

    def test_path_traversal_blocked(self, executor):
        with pytest.raises(ValueError, match="path traversal"):
            executor.read_file("/etc/passwd")

    def test_path_traversal_with_dotdot(self, executor):
        with pytest.raises(ValueError, match="path traversal"):
            executor.read_file("/workspace/../../etc/passwd")


class TestContainerLifecycle:
    def test_container_reuse(self, executor):
        executor.run_command("echo first")
        container_id_1 = executor._container.id
        executor.run_command("echo second")
        container_id_2 = executor._container.id
        assert container_id_1 == container_id_2

    def test_cleanup(self, executor):
        executor.run_command("echo test")
        assert executor._container is not None
        executor.cleanup()
        assert executor._container is None
