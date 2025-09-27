import os
import sys
from pathlib import Path

def write_directory_tree(directory, output_file, prefix="", level=0, max_depth=None, ignore=None):
    """
    Recursively write the directory tree structure to a file.
    - Displays only `.py` file contents.
    - Other file types are listed by name only.

    Args:
        directory (Path or str): Root directory to explore.
        output_file (file object): Output file to write the tree structure.
        prefix (str): Prefix used for formatting (used internally during recursion).
        level (int): Current level of depth in the tree.
        max_depth (int or None): Maximum levels to recurse (None = unlimited).
        ignore (list): Names of files/directories to skip.
    """
    if max_depth is not None and level > max_depth:
        return

    directory = Path(directory)

    # Default ignore list
    if ignore is None:
        ignore = ['__pycache__', '.git', 'node_modules', '.venv', 'venv']

    try:
        if not directory.exists():
            output_file.write(f"Error: Directory '{directory}' does not exist\n")
            return
        if not directory.is_dir():
            output_file.write(f"Error: '{directory}' is not a directory\n")
            return

        # Get all entries sorted: directories first, then files
        entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

        for index, entry in enumerate(entries):
            if entry.name in ignore:
                continue

            try:
                # Detect if this is the last item in the current directory
                is_last = index == len(entries) - 1

                # Format prefix for this item
                current_prefix = prefix + ("└── " if is_last else "├── ")
                output_file.write(f"{prefix}{current_prefix}{entry.name}{'/' if entry.is_dir() else ''}\n")

                if entry.is_file():
                    # Format indentation for file content display
                    file_prefix = prefix + ("    " if is_last else "│   ")

                    # Only process .py files for content display
                    if entry.suffix == '.py':
                        pass
                        try:
                            with open(entry, 'r', encoding='utf-8') as file:
                                content = file.read()
                                if content.strip():  # Only show non-empty files
                                    content_lines = content.splitlines()
                                    output_file.write(f"{file_prefix}└── [Content]\n")
                                    for line in content_lines:
                                        output_file.write(f"{file_prefix}    {line}\n")
                                else:
                                    output_file.write(f"{file_prefix}└── [Empty File]\n")
                        except UnicodeDecodeError:
                            output_file.write(f"{file_prefix}└── [Binary or Non-UTF-8 File]\n")
                        except PermissionError:
                            output_file.write(f"{file_prefix}└── [Permission Denied for File Content]\n")
                        except OSError as e:
                            output_file.write(f"{file_prefix}└── [Error Reading File: {str(e)}]\n")
                    # Skip content for non-.py files (already listed by name above)

                elif entry.is_dir():
                    # Recurse into subdirectory
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    write_directory_tree(
                        entry,
                        output_file,
                        next_prefix,
                        level + 1,
                        max_depth,
                        ignore
                    )

            except PermissionError:
                output_file.write(f"{prefix}{current_prefix}{entry.name} [Permission Denied]\n")
            except OSError as e:
                output_file.write(f"{prefix}{current_prefix}{entry.name} [Error: {str(e)}]\n")

    except PermissionError:
        output_file.write(f"Error: Permission denied accessing '{directory}'\n")
    except OSError as e:
        output_file.write(f"Error: Failed to access '{directory}' - {str(e)}\n")

def main():
    """
    Main entry point for the script. Handles argument parsing and output file creation.
    """
    # Default directory: current working directory
    directory = Path.cwd()
    directory = 'C:\\Users\\MikelKulla\\Downloads\\SampleApp_Src\\'
    output_path = Path("directory_tree.txt")  # Default output file

    # Parse command-line arguments (optional)
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])

    # Optional settings
    max_depth = None
    ignore = ['__pycache__', '.git', 'node_modules', '.venv', 'venv', 'Default','hyphen-data','IwaKeyDistribution','locales','resources','MEIPreload','pluggable_transports']

    try:
        with open(output_path, 'w', encoding='utf-8') as output_file:
            output_file.write(f"Directory structure for: {directory}\n")
            write_directory_tree(directory, output_file, max_depth=max_depth, ignore=ignore)
        print(f"Directory tree written to: {output_path}")
    except Exception as e:
        print(f"Error: An unexpected error occurred - {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
