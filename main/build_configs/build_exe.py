import os
import subprocess
import sys
import shutil

def find_pyinstaller():
    # 1. Try python -m PyInstaller
    try:
        subprocess.check_call([sys.executable, "-m", "PyInstaller", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return [sys.executable, "-m", "PyInstaller"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 2. Try 'pyinstaller' in PATH
    pyinstaller_path = shutil.which("pyinstaller")
    if pyinstaller_path:
        return [pyinstaller_path]

    return None

def build():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    pyinstaller_cmd = find_pyinstaller()
    if not pyinstaller_cmd:
        print("\nError: PyInstaller not found!")
        print(f"Please install it using: {sys.executable} -m pip install pyinstaller")
        return

    # Define the base arguments
    args = [
        "--onefile",
        "--name", "FundTrailTool",
        "--add-data", f"templates{os.pathsep}templates",
        "--add-data", f"static{os.pathsep}static",
        "--add-data", f"Template for letter generation_suspect accounts.docx{os.pathsep}.",
        "--add-data", f"Template for letter generation_victim account.docx{os.pathsep}.",
        "--add-data", f"IFSC_CODES.xlsx{os.pathsep}.",
        "--add-data", f"ATM.txt{os.pathsep}.",
        "--add-data", f".env{os.pathsep}.",
        "--hidden-import", "flask_sqlalchemy",
        "--hidden-import", "flask_login",
        "--hidden-import", "flask_migrate",
        "--hidden-import", "pymysql",
        "--hidden-import", "cryptography",
        "--hidden-import", "openpyxl",
        "--hidden-import", "requests",
        "--hidden-import", "python-dotenv",
        "--hidden-import", "flask_wtf",
        "--hidden-import", "flask_limiter",
        "--hidden-import", "xhtml2pdf",
        "--hidden-import", "reportlab.graphics.barcode",
        "--hidden-import", "reportlab.graphics.barcode.code128",
        "--hidden-import", "reportlab.graphics.barcode.code39",
        "--hidden-import", "reportlab.graphics.barcode.code93",
        "--hidden-import", "reportlab.graphics.barcode.common",
        "--hidden-import", "reportlab.graphics.barcode.widgets",
        "--hidden-import", "reportlab.graphics.barcode.eanbc",
        "--hidden-import", "reportlab.graphics.barcode.usps",
        "--hidden-import", "reportlab.graphics.barcode.usps4s",
        "--hidden-import", "reportlab.graphics.barcode.qr",
        "--hidden-import", "reportlab.graphics.barcode.qrencoder",
        "--hidden-import", "reportlab.graphics.barcode.dmtx",
        "--hidden-import", "reportlab.graphics.barcode.ecc200datamatrix",
        "--hidden-import", "reportlab.graphics.barcode.fourstate",
        "--hidden-import", "reportlab.graphics.barcode.lto",
        "--hidden-import", "docx",
        "--clean",
        "--noconfirm",
        "app.py"
    ]
    
    command = pyinstaller_cmd + args
    
    print(f"Running build command in {project_dir}...")
    print(" ".join(command))
    
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Stream the output
    for line in process.stdout:
        print(line, end='')
        
    process.wait()
    
    if process.returncode == 0:
        print("\nBuild successful! Executable is in the 'dist' folder.")
    else:
        print(f"\nBuild failed with return code {process.returncode}")

if __name__ == "__main__":
    build()
