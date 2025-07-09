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

def log_print(*args, **kwargs):
    """
    Print to console and append to log file, with date and time.
    """
    from datetime import datetime
    msg = " ".join(str(a) for a in args)
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_line = f"{timestamp} {msg}"
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
            to_ini.overwrite_section(section, section_content)
            log_print(f"[{section}] section updated in {old_path}")
        else:
            log_print(f"No [{section}] section found in {newest_path}")

def sync_file_versions(fname, versions, folder, paths, root_files=None, reaper_ini_sections=None):
    """
    Handle syncing logic for a single file across all paths.
    """
    if len(versions) < 2:
        # File exists only in one location, offer to copy to others
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
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(only_path, target_path)
                log_print(f"Copied {only_path} to {target_path}")
        return True

    # Sort by mtime (modification time), descending
    versions.sort(key=lambda x: x[1]['mtime'], reverse=True)
    newest_path, newest_props = versions[0]
    newest_config, newest_base = find_config_for_path(newest_path, folder, paths)
    any_changes = False
    for old_path, old_props in versions[1:]:
        old_config, old_base = find_config_for_path(old_path, folder, paths)
        if newest_props['mtime'] > old_props['mtime']:
            log_print(f"\nFile: {fname}")
            log_print(f"Newer version:")
            log_print(f"  [config]: {newest_config} | [path]: {newest_base}")
            log_print(f"  Size: {newest_props['size']} bytes | Modified: {datetime.fromtimestamp(newest_props['mtime'])}")
            log_print(f"Older version:")
            log_print(f"  [config]: {old_config} | [path]: {old_base}")
            log_print(f"  Size: {old_props['size']} bytes | Modified: {datetime.fromtimestamp(old_props['mtime'])}")
            if fname == "reaper.ini" and folder == "" and reaper_ini_sections:
                update_reaper_ini_sections(old_path, newest_path, old_config, newest_config, reaper_ini_sections)
                any_changes = True
                continue
            resp = input(f"Replace older file '{fname}' in '{old_config}' with newer file from '{newest_config}'? (y/n): ")
            if resp.lower() == 'y':
                shutil.copy2(newest_path, old_path)
                log_print(f"Replaced {old_path} with {newest_path}")
                any_changes = True
    return any_changes

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
        input("\nPress Enter to exit...")
    else:
        log_print("No changes detected.")
        input("\nPress Enter to exit...")