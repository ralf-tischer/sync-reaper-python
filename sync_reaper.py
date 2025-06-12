import os
import shutil
from datetime import datetime

SUB_FOLDERS = ["", 
               "FXChains", 
               "Configurations", 
               "KeyMaps", 
               "presets", 
               "ProjectTemplates", 
               "TrackTemplates", 
               "UserPlugins"]

COMPARE_PATHS = [{"config": "Notebook Config", "path": "D:/Sound/Reaper Notebook"},
                 {"config": "Main Config", "path": "C:/Users/ralft/AppData/Roaming/REAPER"}]  # Fixed typo here

ROOT_FILES = [
    "reaper-fxfolders.ini",  
    "reaper-fxtags.ini",
    "reaper-recentfx.ini",
    "reaper-screensets.ini",
    "reaper-themeconfig.ini",
    "reaper-vkbmap.txt"
]


def print_headline(text):
    """
    Print a headline with a specific format.

    Args:
        text (str): The text to print as a headline.
    """
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80 + "\n")


def get_file_properties(filepath):
    """
    Return file properties for the given file path.

    Args:
        filepath (str): Path to the file.

    Returns:
        dict: Dictionary with file size, modification time, and creation time.
    """
    stat = os.stat(filepath)
    return {
        'size': stat.st_size,
        'mtime': stat.st_mtime,
        'ctime': stat.st_ctime,
    }

def find_config_for_path(fpath, folder, paths):
    """
    Find the config name and base path for a given file path.

    Args:
        fpath (str): File path to check.
        folder (str): Subfolder name.
        paths (list): List of dicts with 'config' and 'path' keys.

    Returns:
        tuple: (config, base_path) if found, otherwise (None, None).
    """
    for p in paths:
        folder_path = os.path.join(p["path"], folder)
        try:
            if os.path.commonpath([os.path.abspath(fpath), os.path.abspath(folder_path)]) == os.path.abspath(folder_path):
                return p["config"], p["path"]
        except ValueError:
            continue
    return None, None

def compare_and_sync(folders, paths):
    """
    Compare and synchronize files across multiple folders and paths.

    For each file in the specified subfolders and paths:
    - If the file exists in only one location, offer to copy it to the others.
    - If the file exists in multiple locations, compare modification times and offer to update older versions.

    Args:
        folders (list): List of subfolder names to compare.
        paths (list): List of dicts with 'config' and 'path' keys.
    """
    any_changes = False

    for folder in folders:
        file_versions = {}
        # Collect all files in all paths for this folder
        for path in paths:
            folder_path = os.path.join(path["path"], folder)
            if not os.path.isdir(folder_path):
                continue
            if folder == "":
                # Only check specific files in root
                for fname in ROOT_FILES:
                    fpath = os.path.join(folder_path, fname)
                    if os.path.isfile(fpath):
                        props = get_file_properties(fpath)
                        file_versions.setdefault(fname, []).append((fpath, props))
            else:
                for root, _, files in os.walk(folder_path):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        rel_path = os.path.relpath(fpath, folder_path)
                        props = get_file_properties(fpath)
                        file_versions.setdefault(rel_path, []).append((fpath, props))

        # Compare versions and prompt if newer found
        for fname, versions in file_versions.items():
            if len(versions) < 2:
                # File exists only in one location, offer to copy to others
                only_path, only_props = versions[0]
                config, base_path = find_config_for_path(only_path, folder, paths)
                for path in paths:
                    folder_path = os.path.join(path["path"], folder)
                    target_path = os.path.join(folder_path, fname)
                    target_config, target_base = find_config_for_path(target_path, folder, paths)
                    if not os.path.exists(target_path):
                        any_changes = True
                        print(f"\nNew file detected: {fname}")
                        print(f"  [config]: {config} | [path]: {base_path}")
                        print(f"  Size: {only_props['size']} bytes | Modified: {datetime.fromtimestamp(only_props['mtime'])}")
                        resp = input(f"Copy new file '{fname}' to '{target_config}'? (y/n): ")
                        if resp.lower() == 'y':
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            shutil.copy2(only_path, target_path)
                            print(f"Copied {only_path} to {target_path}")

                continue  # Skip further comparison

            # Sort by mtime (modification time), descending
            versions.sort(key=lambda x: x[1]['mtime'], reverse=True)
            newest_path, newest_props = versions[0]
            newest_config, newest_base = find_config_for_path(newest_path, folder, paths)
            for old_path, old_props in versions[1:]:
                old_config, old_base = find_config_for_path(old_path, folder, paths)
                if newest_props['mtime'] > old_props['mtime']:
                    any_changes = True
                    print(f"\nFile: {fname}")
                    print(f"Newer version:")
                    print(f"  [config]: {newest_config} | [path]: {newest_base}")
                    print(f"  Size: {newest_props['size']} bytes | Modified: {datetime.fromtimestamp(newest_props['mtime'])}")

                    print(f"Older version:")
                    print(f"  [config]: {old_config} | [path]: {old_base}")
                    print(f"  Size: {old_props['size']} bytes | Modified: {datetime.fromtimestamp(old_props['mtime'])}")

                    resp = input(f"Replace older file '{fname}' in '{old_config}' with newer file from '{newest_config}'? (y/n): ")
                    if resp.lower() == 'y':
                        shutil.copy2(newest_path, old_path)
                        print(f"Replaced {old_path} with {newest_path}")
    return any_changes


if __name__ == "__main__":
    """
    Entry point for the script. Compares and synchronizes files in the specified subfolders and paths.
    """
    print_headline("Reaper Sync Tool: Check for changes in portable and main Reaper configurations")
    any_changes = compare_and_sync(SUB_FOLDERS, COMPARE_PATHS)
    if any_changes:
        input("\nPress Enter to exit...")
    else:
        print("No changes detected.")