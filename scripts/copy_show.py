import os
import shutil
from pathlib import Path


def print_file_tree(directory, prefix="", ignore_items=None):
    """
    Prints the file tree structure of the given directory.

    Args:
        directory (str): The path to the directory.
        prefix (str): Prefix for the current line (used for recursion).
        ignore_items (list): List of items (files/folders) to ignore.
    """
    if ignore_items is None:
        ignore_items = []

    directory_path = Path(directory)

    # Get all items in the directory
    items = sorted(os.listdir(directory))

    # Process each item
    for i, item in enumerate(items):
        # Skip if item is in ignore list
        if item in ignore_items:
            continue

        # Construct the full path
        item_path = directory_path / item

        # Check if it's the last item
        is_last = i == len(items) - 1 or all(next_item in ignore_items for next_item in items[i + 1:])

        # Print the current item
        if is_last:
            print(f"{prefix}└── {item}")
            new_prefix = prefix + "    "
        else:
            print(f"{prefix}├── {item}")
            new_prefix = prefix + "│   "

        # If it's a directory, recursively print its contents
        if item_path.is_dir():
            print_file_tree(item_path, new_prefix, ignore_items)


def copy_files_flat(source_dir, output_dir="outputs", include_subfolders=True, ignore_items=None):
    """
    Copies all files from source_dir to output_dir as a flat structure (no subdirectories).

    Args:
        source_dir (str): The source directory path.
        output_dir (str): The output directory path (default: "outputs").
        include_subfolders (bool): Whether to include files in subfolders (default: True).
        ignore_items (list): List of items (files/folders) to ignore (default: None).

    Returns:
        int: The number of files copied.
    """
    if ignore_items is None:
        ignore_items = []

    source_path = Path(source_dir)
    output_path = Path(output_dir)

    # Create the output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    files_copied = 0

    # Walk through the source directory
    for root, dirs, files in os.walk(source_path):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_items]

        # If not including subfolders and we're not at the root, skip
        if not include_subfolders and root != str(source_path):
            continue

        # Copy each file to the flat output directory
        for file in files:
            if file in ignore_items:
                continue

            source_file = Path(root) / file

            # Handle duplicate filenames by adding the parent folder name as prefix if needed
            if (output_path / file).exists():
                # Get parent folder name
                parent_folder = os.path.basename(root)
                output_file = output_path / f"{parent_folder}_{file}"
            else:
                output_file = output_path / file

            shutil.copy2(source_file, output_file)
            files_copied += 1
            print(f"Copied: {source_file} -> {output_file}")

    return files_copied


def folder_copy(source_dir, output_dir="outputs", include_subfolders=True, ignore_items=None):
    """
    Main function to copy files to a flat structure and display the original file tree.

    Args:
        source_dir (str): Source directory path.
        output_dir (str): Output directory path (default: "outputs").
        include_subfolders (bool): Whether to include files in subfolders (default: True).
        ignore_items (list): List of items (files/folders) to ignore (default: None).

    Returns:
        int: The number of files copied.
    """
    if ignore_items is None:
        ignore_items = []

    # Check if source directory exists
    if not os.path.isdir(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist.")
        return 0

    # Print the original file tree
    print("\nOriginal File Structure:")
    print(f"{source_dir}")
    print_file_tree(source_dir, ignore_items=ignore_items)

    # Copy files to flat structure
    print("\nCopying files...")
    files_copied = copy_files_flat(source_dir, output_dir, include_subfolders, ignore_items)

    print(f"\nOperation complete! {files_copied} files copied to '{output_dir}'")

    return files_copied


# Example usage
if __name__ == "__main__":
    # You can call the function directly without argparse
    # folder_copy("path/to/source_folder")
    folder_copy("D:/Sundries/Workspace/TypeScript/InteractiveSeg3D", "D:/Sundries/Workspace/TypeScript/TMP", True,
                ["node_modules", ".git", "data", ".idea", ".DS_Store", "package-lock.json", "public", "src/backend/.idea", "agile3d", "src/backend/object_views", "src/backend/.gitignore",
                 "node_modules", ".gitignore", "object_views", "assets", "README.md", "outputs"])

    # Quick test with current directory
    # folder_copy(".", "test_output", True, [".git", "__pycache__"])
    pass