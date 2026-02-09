"""
Run Repricer - Cross-platform runner
"""

import sys
import subprocess
from pathlib import Path

project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

def main():
    args = sys.argv[1:]
    cmd = [sys.executable, "-m", "app.main"] + args
    
    print("="*60)
    print("Starting Furniture Repricer")
    print("="*60)
    
    try:
        result = subprocess.run(cmd, cwd=str(project_dir), check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\n [!] Interrupted")
        return 1

if __name__ == "__main__":
    sys.exit(main())
