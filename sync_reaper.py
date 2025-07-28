import os
import shutil
from datetime import datetime
import sys

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
    "REAPER.ini",
    "reaper-fxfolders.ini",  
    "reaper-fxtags.ini",
    "reaper-recentfx.ini",
    "reaper-screensets.ini",
    "reaper-themeconfig.ini",
    "reaper-vkbmap.txt"
]

REAPER_INI_SECTIONS = ["Recent", "RecentFX"]
LOG_FILEPATH = "sync_reaper.log"
VERBOSE = False
TEST_MODE = any(arg in ("--test", "-t") for arg in sys.argv)
if any(arg in ("-v", "--verbose") for arg in sys.argv):
    VERBOSE = True

def log_print(*args, **kwargs):
    """
    Print to console (if VERBOSE) and append to log file, with date and time.
    """
    from datetime import datetime
    msg = " ".join(str(a) for a in args)
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_line = f"{timestamp} {msg}"
    if VERBOSE:
        print(log_line, **kwargs)
    with open(LOG_FILEPATH, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

def print_headline(text):
    """
    Print a headline with a specific format.

    Args:
        text (str): The text to print as a headline.
    """
    log_print("\n" + "=" * 80)
    log_print(text)
    log_print("=" * 80 + "\n")


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

def collect_files_in_folder(folder, paths, root_files=None):
    """
    Collect files in the given folder for all paths.
    If folder is '', only files in root_files are considered.
    Returns a dict: {relative_path: [(full_path, file_properties), ...]}
    """
    file_versions = {}
    for path in paths:
        folder_path = os.path.join(path["path"], folder)
        if not os.path.isdir(folder_path):
            continue
        if folder == "" and root_files:
            for fname in root_files:
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
    return file_versions

def log_or_write(action, src, dst):
    if TEST_MODE:
        log_print(f"[TEST MODE] Would {action}: {src} -> {dst}")
    else:
        if action == "copy":
            shutil.copy2(src, dst)
        elif action == "update":
            shutil.copy2(src, dst)
        log_print(f"{action.capitalize()}d {src} to {dst}")

def sync_file_versions(fname, versions, folder, paths, root_files=None, reaper_ini_sections=None):
    """
    Handle syncing logic for a single file across all paths.
    Only prompt user if versions differ in modification date or size.
    """
    # If only one version exists, handle new file copy
    if len(versions) < 2:
        only_path, only_props = versions[0]
        config, base_path = find_config_for_path(only_path, folder, paths)
        for path in paths:
            folder_path = os.path.join(path["path"], folder)
            target_path = os.path.join(folder_path, fname)
            target_config, target_base = find_config_for_path(target_path, folder, paths)
            if not os.path.exists(target_path):
                log_print(f"\nNew file detected: {fname}")
                log_print(f"  [config]: {config} | [path]: {base_path}")
                log_print(f"  Size: {only_props['size']} bytes | Modified: {datetime.fromtimestamp(only_props['mtime'])}")
                resp = input(f"Copy new file '{fname}' to '{target_config}'? (y/n): ")
                log_print(f"User response for copying new file '{fname}' to '{target_config}': {resp}")
                if resp.lower() == 'y':
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    log_or_write("copy", only_path, target_path)
        return True
    # If all versions have the same modification date AND size, skip prompt and do not log
    mtimes = set([props['mtime'] for _, props in versions])
    sizes = set([props['size'] for _, props in versions])
    if len(mtimes) == 1 and len(sizes) == 1:
        return False
    # Multiple versions found, ask user which to keep
    versions.sort(key=lambda x: x[1]['mtime'], reverse=True)
    log_print(f"\nMultiple versions found for file: {fname}")
    for idx, (path, props) in enumerate(versions):
        config, base_path = find_config_for_path(path, folder, paths)
        log_print(f"[{idx+1}] {path} | [config]: {config} | [path]: {base_path} | Size: {props['size']} | Modified: {datetime.fromtimestamp(props['mtime'])}")
    choice = input(f"Which version of '{fname}' do you want to keep? Enter number (1-{len(versions)}): ")
    log_print(f"User chose version {choice} for file '{fname}'")
    try:
        keep_idx = int(choice) - 1
        keep_path, keep_props = versions[keep_idx]
        for idx, (path, _) in enumerate(versions):
            if idx != keep_idx:
                log_or_write("update", keep_path, path)
        return True
    except Exception as e:
        log_print(f"Invalid choice or error: {e}")
        return False

def update_reaper_ini_sections(old_path, newest_path, old_config, newest_config, sections):
    """
    Update specified sections in reaper.ini from newest_path to old_path.
    """
    from_ini = ReaperIni(newest_path)
    to_ini = ReaperIni(old_path)
    for section in sections:
        log_print(f"Updating [{section}] section in '{old_config}' from '{newest_config}'...")
        section_content = from_ini.get_section(section)
        if section_content:
            if TEST_MODE:
                log_print(f"[TEST MODE] Would update [{section}] section in {old_path} from {newest_path}")
            else:
                to_ini.overwrite_section(section, section_content)
            log_print(f"[{section}] section updated in {old_path}")
        else:
            log_print(f"No [{section}] section found in {newest_path}")

def auto_update_root_files(paths, root_files):
    """
    Automatically update root files (except reaper.ini) without user confirmation.
    Only replace if file properties (size or mtime) differ.
    """
    for fname in root_files:
        if fname.lower() == "reaper.ini":
            continue  # Handled separately
        file_versions = collect_files_in_folder("", paths, root_files=[fname])
        for _, versions in file_versions.items():
            if len(versions) < 2:
                only_path, only_props = versions[0]
                for path in paths:
                    target_path = os.path.join(path["path"], fname)
                    if not os.path.exists(target_path):
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.copy2(only_path, target_path)
                        log_print(f"[AUTO] Copied {only_path} to {target_path}")
            else:
                versions.sort(key=lambda x: x[1]['mtime'], reverse=True)
                newest_path, newest_props = versions[0]
                for old_path, old_props in versions[1:]:
                    if os.path.abspath(newest_path) != os.path.abspath(old_path):
                        # Only replace if file properties differ
                        if (newest_props['size'] != old_props['size'] or
                            newest_props['mtime'] != old_props['mtime']):
                            shutil.copy2(newest_path, old_path)
                            log_print(f"[AUTO] Updated {old_path} with {newest_path}")

def auto_update_reaper_ini_sections(paths, sections):
    """
    Automatically update specified sections in reaper.ini without user confirmation.
    """
    file_versions = collect_files_in_folder("", paths, root_files=["reaper.ini"])
    for fname, versions in file_versions.items():
        if len(versions) < 2:
            continue
        versions.sort(key=lambda x: x[1]['mtime'], reverse=True)
        newest_path, _ = versions[0]
        for old_path, _ in versions[1:]:
            if os.path.abspath(newest_path) != os.path.abspath(old_path):
                update_reaper_ini_sections(old_path, newest_path, "", "", sections)

def compare_and_sync_with_confirmation(folders, paths, root_files=None, reaper_ini_sections=None):
    """
    For all folders except root, compare and sync files with user confirmation.
    """
    any_changes = False
    for folder in folders:
        if folder == "":
            continue  # Root handled separately
        file_versions = collect_files_in_folder(folder, paths, root_files=root_files)
        for fname, versions in file_versions.items():
            changed = sync_file_versions(
                fname, versions, folder, paths,
                root_files=root_files,
                reaper_ini_sections=reaper_ini_sections
            )
            if changed:
                any_changes = True
    return any_changes

class ReaperIni:
    """
    Class to read and modify sections in a .ini file (such as reaper.ini).
    """
    def __init__(self, filepath):
        self.filepath = filepath
        with open(filepath, 'r', encoding='utf-8') as f:
            self.lines = f.readlines()

    def get_section(self, section_name):
        """
        Return the content of a section (including the [section] header) as a string.
        Returns an empty string if not found.
        """
        start_idx = None
        end_idx = None
        section_lines = []
        in_section = False
        for idx, line in enumerate(self.lines):
            if line.strip().lower() == f'[{section_name.lower()}]':
                start_idx = idx
                in_section = True
                section_lines = [line]
                continue
            if in_section:
                if line.startswith('[') and line.strip().lower() != f'[{section_name.lower()}]':
                    end_idx = idx
                    break
                section_lines.append(line)
        if in_section and end_idx is None:
            end_idx = len(self.lines)
        if start_idx is not None:
            return ''.join(section_lines)
        return ''

    def overwrite_section(self, section_name, content):
        """
        Overwrite the given section with the provided content (string, including [section] header).
        If the section does not exist, append it at the end.
        """
        start_idx = None
        end_idx = None
        in_section = False
        for idx, line in enumerate(self.lines):
            if line.strip().lower() == f'[{section_name.lower()}]':
                start_idx = idx
                in_section = True
                continue
            if in_section:
                if line.startswith('[') and line.strip().lower() != f'[{section_name.lower()}]':
                    end_idx = idx
                    break
        if in_section and end_idx is None:
            end_idx = len(self.lines)
        content_lines = content if isinstance(content, list) else content.splitlines(keepends=True)
        if start_idx is not None:
            self.lines = self.lines[:start_idx] + content_lines + self.lines[end_idx:]
        else:
            # Append at end
            if not self.lines or self.lines[-1].endswith('\n'):
                self.lines += content_lines
            else:
                self.lines.append('\n')
                self.lines += content_lines
        #'''
        # Write changes back to file
        with open(self.filepath, 'w', encoding='utf-8') as f:
            f.writelines(self.lines)
        #'''
        #print(f"Section '{section_name}' overwritten in {self.filepath}")
        #print(f"New content:\n{content.strip()}\n")

if __name__ == "__main__":
    """
    Entry point for the script. Compares and synchronizes files in the specified subfolders and paths.
    """
    print_headline("Reaper Sync Tool: Check for changes in portable and main Reaper configurations")
    auto_update_root_files(COMPARE_PATHS, ROOT_FILES)
    auto_update_reaper_ini_sections(COMPARE_PATHS, REAPER_INI_SECTIONS)
    any_changes = compare_and_sync_with_confirmation(SUB_FOLDERS, COMPARE_PATHS, root_files=ROOT_FILES, reaper_ini_sections=REAPER_INI_SECTIONS)
    if any_changes:
        if VERBOSE: input("\nPress Enter to exit...")
    else:
        log_print("No changes detected.")