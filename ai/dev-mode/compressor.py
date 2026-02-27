#!/usr/bin/env python3
"""
OMEGA COMPRESSOR — Repo-to-Markdown Tool

This script reads an entire directory structure and compiles it into a single 
markdown file, formatted specifically for LLM context ingestion (like NotebookLM or Claude).

Usage:
  python3 compressor.py /path/to/project /path/to/output.md
"""

import os
import sys
import fnmatch

# Folders and files to completely ignore during compression
IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', 'venv', 'env', '.venv', 'build', 'dist', '.next'}
IGNORE_FILES = {'.DS_Store', '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dylib', '*.dll', 
                'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', '*.log'}
# Common binary extensions to skip
BINARY_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz', 
                '.mp4', '.mp3', '.wav', '.exe', '.bin', '.ttf', '.woff', '.woff2'}

def should_ignore(path, is_dir=False):
    name = os.path.basename(path)
    if is_dir:
        return name in IGNORE_DIRS
    
    # Check exact file matches and glob patterns
    if any(fnmatch.fnmatch(name, pattern) for pattern in IGNORE_FILES):
        return True
        
    # Skip binaries
    ext = os.path.splitext(name)[1].lower()
    if ext in BINARY_EXTS:
        return True
        
    return False

def generate_tree(dir_path, prefix=""):
    """Generate a string representation of the directory tree."""
    tree_str = ""
    try:
        items = sorted(os.listdir(dir_path))
    except PermissionError:
        return ""
        
    # Filter out ignored items
    items = [item for item in items if not should_ignore(os.path.join(dir_path, item), 
             os.path.isdir(os.path.join(dir_path, item)))]
             
    for i, item in enumerate(items):
        path = os.path.join(dir_path, item)
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        
        tree_str += f"{prefix}{connector}{item}\n"
        
        if os.path.isdir(path):
            extension = "    " if is_last else "│   "
            tree_str += generate_tree(path, prefix + extension)
            
    return tree_str

def compress_repo(source_dir, output_file):
    source_dir = os.path.abspath(source_dir)
    
    if not os.path.exists(source_dir):
        print(f"Error: Source directory {source_dir} does not exist.")
        sys.exit(1)
        
    print(f"Compressing repository: {source_dir}")
    print(f"Outputting to: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(f"# Repository Context: {os.path.basename(source_dir)}\n\n")
        
        # 1. Write Directory Tree
        out.write("## Directory Structure\n```text\n")
        out.write(f"{os.path.basename(source_dir)}/\n")
        out.write(generate_tree(source_dir))
        out.write("```\n\n")
        
        # 2. Write File Contents
        out.write("## File Contents\n\n")
        
        processed_count = 0
        for root, dirs, files in os.walk(source_dir):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), is_dir=True)]
            
            for file in sorted(files):
                file_path = os.path.join(root, file)
                if should_ignore(file_path, is_dir=False):
                    continue
                    
                rel_path = os.path.relpath(file_path, source_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    ext = os.path.splitext(file)[1][1:] # Get extension without dot
                    if not ext:
                        ext = 'text'
                        
                    out.write(f"### File: `{rel_path}`\n\n")
                    out.write(f"```{ext}\n")
                    out.write(content)
                    if not content.endswith('\n'):
                        out.write("\n")
                    out.write("```\n\n")
                    processed_count += 1
                    
                except UnicodeDecodeError:
                    print(f"Skipped binary/unreadable file: {rel_path}")
                except Exception as e:
                    print(f"Error reading {rel_path}: {e}")
                    
    print(f"\nCompression complete! Processed {processed_count} files.")
    print(f"Saved to: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compressor.py <source_directory> <output_file.md>")
        sys.exit(1)
        
    source = sys.argv[1]
    dest = sys.argv[2]
    compress_repo(source, dest)
