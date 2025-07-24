import os

def patch_squeeze_pro(venv_path):
    file_path = os.path.join(venv_path, "Lib", "site-packages", "pandas_ta", "momentum", "squeeze_pro.py")
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    patched = False
    with open(file_path, "w", encoding="utf-8") as f:
        for line in lines:
            # Replace incorrect import line
            if 'from numpy import NaN as npNaN' in line:
                f.write("from numpy import nan as npNaN\n")
                patched = True
            else:
                f.write(line)

    if patched:
        print(f"Patched numpy import in {file_path}")
    else:
        print(f"No changes needed in {file_path}")

if __name__ == "__main__":
    # Change this path to your venv folder location if different
    venv_folder = r".venv"
    patch_squeeze_pro(venv_folder)
