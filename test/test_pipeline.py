import subprocess
import sys

def test_pipeline_runs():
    result = subprocess.run(
        [sys.executable, '-m', 'src.pipeline', '--epochs', '1'],
        capture_output= True,
        text= True,
    )
    assert result.returncode == 0, result.stderr